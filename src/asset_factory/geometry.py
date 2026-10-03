import asyncio
import io
import json
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .model_preview import prepare_fbx_preview
from .models import Region
from .provider import ProviderError
from .storage import identity, now
from .tripo import crop_reference


class GeometryRequest(BaseModel):
    stage: Literal["head", "body", "hair"]
    source_revision: str
    crop: Region | None = None
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9-]+$")


class GeometryApproval(BaseModel):
    checked: Literal[True]


def model_info(path):
    with path.open("rb") as file:
        header = file.read(20)
        if len(header) != 20 or header[:4] != b"glTF" or int.from_bytes(header[4:8], "little") != 2:
            raise ValueError("模型文件不是有效的 GLB")
        if int.from_bytes(header[8:12], "little") != path.stat().st_size or header[16:20] != b"JSON":
            raise ValueError("模型文件不是有效的 GLB")
        length = int.from_bytes(header[12:16], "little")
        if length > 16 * 1024 * 1024 or length > path.stat().st_size - 20:
            raise ValueError("模型文件不是有效的 GLB")
        data = json.loads(file.read(length))
    if not isinstance(data, dict) or not isinstance(data.get("meshes"), list) or not data["meshes"]:
        raise ValueError("模型没有可检查的网格")
    return {
        "meshes": len(data["meshes"]),
        "materials": len(data.get("materials", [])),
        "bytes": path.stat().st_size,
    }


def attach_geometry(app, store, tripo, tasks, required_refs, revision, active):
    def persist(op):
        with store.connect() as db:
            store.put_operation(db, op)

    async def query(op):
        data = await tripo.task(op["provider_task_id"])
        vendor_status = data.get("status")
        op.update(
            vendor_status=vendor_status,
            progress=data.get("progress", 0),
            consumed_credit=data.get("consumed_credit"),
            checked_at=now(),
        )
        if vendor_status == "success":
            path = store.root / op["project_id"] / (op["id"] + "." + op.get("model_format", "glb"))
            await tripo.download(data.get("output", {}), path)
            if op.get("model_format") == "fbx":
                persist(op)
                try:
                    op["preview"] = await prepare_fbx_preview(path)
                except Exception:  # noqa: BLE001 — original download is preserved
                    op["preview"] = {
                        "status": "unavailable",
                        "reason": "FBX 预览转换失败，原始四边形文件保留。",
                    }
            op.update(
                status="succeeded",
                finished_at=now(),
                error=None,
                download_url=f"/api/projects/{op['project_id']}/geometry/{op['id']}/download",
            )
        elif vendor_status in ("failed", "banned", "expired", "cancelled"):
            op.update(
                status="failed", error=f"Tripo 任务结束：{vendor_status}，没有自动重试。", finished_at=now()
            )
        elif vendor_status in ("queued", "running"):
            op.update(status="running", error=None)
        else:
            op.update(status="unknown", error="Tripo 任务结果未知，请核对原任务。")
        persist(op)
        return op

    async def execute(oid):
        with store.connect() as db:
            op = store.operation(oid, db)
            op.update(status="running", started_at=now())
            store.put_operation(db, op)
        phase = "upload"
        try:
            if op.get("input_views"):
                token = []
                for v in op["input_views"]:
                    token.append(
                        await tripo.upload(
                            (store.root / op["project_id"] / (v["input_id"] + ".png")).read_bytes()
                        )
                    )
            else:
                token = await tripo.upload(
                    (store.root / op["project_id"] / (op["input_id"] + ".png")).read_bytes()
                )
            phase = "submit"
            op["provider_task_id"] = await tripo.submit(token, face_limit=op["face_limit"], quad=op["quad"])
            persist(op)  # Save the vendor ID before any polling/download.
            phase = "query"
            for _ in range(120):
                await query(op)
                if op["status"] != "running":
                    return
                await asyncio.sleep(5)
            op.update(status="unknown", error="等待超时；可查询原任务，未重新生成。")
            persist(op)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 — durable operation must record local failures too
            unknown = phase != "upload" and (
                not isinstance(error, ProviderError) or error.unknown or phase == "query"
            )
            op.update(
                status="unknown" if unknown else "failed",
                error=str(error) if isinstance(error, ProviderError) else "三维处理失败，请核对原任务。",
            )
            persist(op)

    @app.get("/api/services/tripo/balance")
    async def balance():
        if tripo is None:
            return {"configured": False}
        try:
            return {"configured": True, **await tripo.balance()}
        except ProviderError as error:
            raise HTTPException(502, str(error)) from error

    @app.post("/api/projects/{pid}/geometry", status_code=202)
    async def generate(pid: str, req: GeometryRequest):
        if tripo is None:
            raise HTTPException(400, "Tripo 密钥未配置")
        # Recheck in transaction after the network check to handle concurrent submissions.
        with store.connect() as db:
            existing = next((o for o in store.operations(pid, db) if o["request_id"] == req.request_id), None)
            if existing:
                return existing
        try:
            wallet = await tripo.balance()
            if wallet["balance"] <= 0:
                raise HTTPException(402, "Tripo API 钱包余额为 0，请充值 API 积分后再试。")
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                p = store.get(pid, db)
                existing = next(
                    (o for o in store.operations(pid, db) if o["request_id"] == req.request_id), None
                )
                if existing:
                    return existing
                ongoing = [
                    o for o in store.operations(pid, db) if o["status"] in ("queued", "running", "unknown")
                ]
                if any(
                    o["status"] == "unknown" or o.get("kind") != "geometry" or o["stage"] == req.stage
                    for o in ongoing
                ):
                    raise HTTPException(409, "请先处理当前操作")
                required_refs(p, req.stage)
                source = revision(p, req.source_revision)
                if (
                    not source
                    or source["stage"] != req.stage
                    or source["stale"]
                    or not source["approved"]
                    or p["current"].get(req.stage) != source["id"]
                ):
                    raise ValueError("只能使用已确认的当前部件参考")
                input_views = []
                if req.crop:
                    cropped = crop_reference(
                        (store.root / pid / (source["id"] + ".png")).read_bytes(), req.crop
                    )
                    view_id = None
                else:
                    views = {v["view"]: v for v in source.get("views", [])}
                    order = ("front", "left", "back", "right")
                    if source.get("view_split", {}).get("status") != "ready" or not all(
                        v in views for v in order
                    ):
                        raise ValueError("请先完成全部四视图拆分并检查裁切预览")
                    # Persist immutable image snapshots in vendor order, not UI quadrant order.
                    for view in order:
                        asset = views[view]
                        data = (store.root / pid / (asset["id"] + ".png")).read_bytes()
                        input_id = identity()
                        (store.root / pid / (input_id + ".png")).write_bytes(data)
                        input_views.append(
                            {"view": view, "source_view_id": asset["id"], "input_id": input_id}
                        )
                    view_id = views["front"]["id"]
                    cropped = (store.root / pid / (view_id + ".png")).read_bytes()
                iid = identity()
                (store.root / pid / (iid + ".png")).write_bytes(cropped)
                op = {
                    "id": identity(),
                    "project_id": pid,
                    "request_id": req.request_id,
                    "kind": "geometry",
                    "stage": req.stage,
                    "provider": "tripo",
                    "model": tripo.model,
                    "status": "queued",
                    "created_at": now(),
                    "input_id": iid,
                    "source_view": "multiview" if not req.crop else "manual_crop",
                    "input_views": input_views,
                    "input_mode": "multiview_to_model" if not req.crop else "image_to_model",
                    "source_view_id": view_id,
                    "request": req.model_dump(mode="json"),
                    "texture": False,
                    "quad": True,
                    "face_limit": 5000 if req.stage == "head" else 20000,
                    "model_format": "fbx",
                    "profile_version": "quad-multiview-parts-v2",
                    "pbr": False,
                    "progress": 0,
                    "provider_task_id": None,
                    "error": None,
                }
                db.execute(
                    "INSERT INTO operations VALUES (?,?,?,?,?)",
                    (op["id"], pid, op["request_id"], op["status"], json.dumps(op)),
                )
            task = asyncio.create_task(execute(op["id"]))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            return op
        except KeyError as error:
            raise HTTPException(404, "角色不存在") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except ProviderError as error:
            raise HTTPException(502, str(error)) from error

    class GeometryBatch(BaseModel):
        component_revisions: dict[str, str]

    async def submit_batch(pid, component_revisions):
        if tripo is None:
            raise HTTPException(400, "Tripo 密钥未配置")
        try:
            p = store.get(pid)
        except KeyError as error:
            raise HTTPException(404, "角色不存在") from error
        parts = ("head", "body", "hair")
        if set(component_revisions) != set(parts):
            raise HTTPException(400, "请先确认三个当前部件参考")
        for part in parts:
            source = revision(p, component_revisions[part])
            if (
                not source
                or source["stage"] != part
                or source["stale"]
                or not source["approved"]
                or p["current"].get(part) != source["id"]
            ):
                raise HTTPException(409, "请先确认三个当前部件参考")
            if not {"front", "left", "back", "right"}.issubset({v["view"] for v in source.get("views", [])}):
                raise HTTPException(400, "请先完成四视图拆分并检查裁切预览")

        async def submit_part(part):
            try:
                op = await generate(
                    pid,
                    GeometryRequest(
                        stage=part,
                        source_revision=component_revisions[part],
                        request_id=f"geometry-quadmv2-{component_revisions[part]}-{part}",
                    ),
                )
                return {"stage": part, "operation": op}
            except HTTPException as error:
                return {"stage": part, "error": error.detail}

        return {"results": await asyncio.gather(*(submit_part(part) for part in parts))}

    @app.post("/api/projects/{pid}/generate-models", status_code=202)
    async def generate_models(pid: str, req: GeometryBatch):
        return await submit_batch(pid, req.component_revisions)

    @app.post("/api/projects/{pid}/geometry/{oid}/refresh")
    async def refresh(pid: str, oid: str):
        if tripo is None:
            raise HTTPException(400, "Tripo 未配置")
        try:
            op = store.operation(oid)
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error
        if op["project_id"] != pid or op.get("kind") != "geometry" or not op.get("provider_task_id"):
            raise HTTPException(400, "任务没有可查询的 Tripo 编号")
        if op["status"] == "running":
            raise HTTPException(409, "后台正在查询，请等待")
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            op = store.operation(oid, db)
            current = active(pid, db)
            if current and current["id"] != oid:
                raise HTTPException(409, "请先完成当前操作，再查询旧任务")
            if (
                op["status"] == "succeeded"
                and (store.root / pid / (oid + "." + op.get("model_format", "glb"))).is_file()
            ):
                return op
            if op["status"] == "running":
                raise HTTPException(409, "后台正在查询，请等待")
            op.update(status="running")
            store.put_operation(db, op)
        try:
            result = await query(op)
            if result["status"] == "running":
                result.update(status="unknown", error="原任务仍在进行，可稍后再次查询；不会重新生成。")
                persist(result)
            return result
        except ProviderError as error:
            op.update(status="unknown", error=str(error))
            persist(op)
            raise HTTPException(502, str(error)) from error

    def ready_model(pid, oid, db=None):
        try:
            op = store.operation(oid, db)
        except KeyError as error:
            raise HTTPException(404, "模型尚未就绪") from error
        path = store.root / pid / (oid + "." + op.get("model_format", "glb"))
        if (
            op["project_id"] != pid
            or op.get("kind") != "geometry"
            or op["status"] != "succeeded"
            or not path.is_file()
        ):
            raise HTTPException(404, "模型尚未就绪")
        return op, path

    def current_source(pid, op, db=None):
        p = store.get(pid, db)
        rid = op["request"]["source_revision"]
        source = revision(p, rid)
        if not source or source["stale"] or not source["approved"] or p["current"].get(op["stage"]) != rid:
            raise HTTPException(409, "模型参考已变更，请重新检查当前版本")

    @app.get("/api/projects/{pid}/geometry/{oid}/preview")
    def preview(pid: str, oid: str):
        op, path = ready_model(pid, oid)
        if op.get("model_format") == "fbx":
            if op.get("preview", {}).get("status") != "ready":
                return FileResponse(path, media_type="application/octet-stream", headers={"X-Model-Format": "fbx"})
            path = path.with_name(oid + "-preview.glb")
        return FileResponse(path, media_type="model/gltf-binary")

    pending_previews = set()

    @app.post("/api/projects/{pid}/geometry/{oid}/prepare-preview")
    async def prepare_preview(pid: str, oid: str):
        op, path = ready_model(pid, oid)
        if op.get("model_format") != "fbx":
            return op
        if oid in pending_previews:
            raise HTTPException(409, "预览正在准备，请稍候")
        pending_previews.add(oid)
        try:
            op["preview"] = await prepare_fbx_preview(path)
            # Reload after the worker so simultaneous approvals are preserved.
            with store.connect() as db:
                current = store.operation(oid, db)
                current["preview"] = op["preview"]
                store.put_operation(db, current)
            return current
        except Exception as error:
            raise HTTPException(500, "FBX 预览转换失败，原始四边形文件保留。") from error
        finally:
            pending_previews.discard(oid)

    @app.get("/api/projects/{pid}/geometry/{oid}/info")
    def info(pid: str, oid: str):
        op, path = ready_model(pid, oid)
        if op.get("model_format") == "fbx":
            return {
                "format": "FBX",
                "bytes": path.stat().st_size,
                "requested_face_limit": op.get("face_limit"),
                "quad_requested": op.get("quad"),
                "preview": op.get("preview", {}),
                **op.get("preview", {}).get("topology", {}),
            }
        try:
            return model_info(path)
        except (ValueError, OSError) as error:
            raise HTTPException(400, "模型文件无法读取") from error

    @app.post("/api/projects/{pid}/geometry/{oid}/approve")
    def approve_model(pid: str, oid: str, req: GeometryApproval):
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            op, path = ready_model(pid, oid, db)
            current_source(pid, op, db)
            try:
                if op.get("model_format") == "fbx":
                    with path.open("rb") as file:
                        header = file.read(64)
                    if not (
                        header.startswith(b"Kaydara FBX Binary  \x00\x1a\x00")
                        or header.lstrip().startswith(b"; FBX")
                    ):
                        raise ValueError("Invalid FBX")
                    metadata = {
                        "format": "FBX",
                        "bytes": path.stat().st_size,
                        **op.get("preview", {}).get("topology", {}),
                    }
                else:
                    metadata = model_info(path)
            except (ValueError, OSError) as error:
                raise HTTPException(400, "模型文件无法读取") from error
            op.update(
                visual_approved=True,
                visual_approved_at=op.get("visual_approved_at") or now(),
                model_info=metadata,
            )
            store.put_operation(db, op)
        return op

    @app.get("/api/projects/{pid}/geometry/{oid}/blender-package")
    def blender_package(pid: str, oid: str):
        op, path = ready_model(pid, oid)
        current_source(pid, op)
        if not op.get("visual_approved"):
            raise HTTPException(409, "请先检查并确认模型")
        out = io.BytesIO()
        name = op["stage"] + "." + op.get("model_format", "glb")
        manifest = {
            "schema_version": 1,
            "models": [
                {
                    "path": name,
                    "part": op["stage"],
                    "operation_id": oid,
                    "source_revision": op["request"]["source_revision"],
                }
            ],
        }
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(path, name)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            archive.write(
                Path(__file__).resolve().parents[2] / "scripts" / "import_blender.py", "import_blender.py"
            )
            archive.writestr(
                "README.txt",
                "Unzip this package. In Blender's Scripting workspace, open import_blender.py from the unzipped folder and run it, or run: blender --background --python import_blender.py\nThe script imports the model into a new collection in the current scene and saves a new file in this folder. It does not align, merge or rig the character.\n",
            )
        return Response(
            out.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{op["stage"]}-blender-{oid[:8]}.zip"'},
        )

    @app.get("/api/projects/{pid}/geometry/{oid}/download")
    def download(pid: str, oid: str):
        try:
            op = store.operation(oid)
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error
        if op["project_id"] != pid or op.get("kind") != "geometry" or op["status"] != "succeeded":
            raise HTTPException(404, "模型尚未就绪")
        suffix = "." + op.get("model_format", "glb")
        return FileResponse(store.root / pid / (oid + suffix), filename=op["stage"] + "-" + oid[:8] + suffix)

    return submit_batch
