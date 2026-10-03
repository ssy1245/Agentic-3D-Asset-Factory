import asyncio
import json
from typing import Literal

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .models import Region
from .provider import ProviderError
from .storage import identity, now
from .tripo import crop_reference


class GeometryRequest(BaseModel):
    stage: Literal["head", "body", "hair"]
    source_revision: str
    crop: Region
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9-]+$")


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
            path = store.root / op["project_id"] / (op["id"] + ".glb")
            await tripo.download(data.get("output", {}), path)
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
            token = await tripo.upload(
                (store.root / op["project_id"] / (op["input_id"] + ".png")).read_bytes()
            )
            phase = "submit"
            op["provider_task_id"] = await tripo.submit(token)
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
                if active(pid, db):
                    raise HTTPException(409, "请先处理当前操作")
                if sum(o.get("kind") == "geometry" for o in store.operations(pid, db)) >= 2:
                    raise HTTPException(409, "首版每个角色最多提交两个几何候选，避免批量支出")
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
                cropped = crop_reference((store.root / pid / (source["id"] + ".png")).read_bytes(), req.crop)
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
                    "request": req.model_dump(mode="json"),
                    "texture": False,
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
            if op["status"] == "succeeded" and (store.root / pid / (oid + ".glb")).is_file():
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

    @app.get("/api/projects/{pid}/geometry/{oid}/download")
    def download(pid: str, oid: str):
        try:
            op = store.operation(oid)
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error
        if op["project_id"] != pid or op.get("kind") != "geometry" or op["status"] != "succeeded":
            raise HTTPException(404, "模型尚未就绪")
        return FileResponse(store.root / pid / (oid + ".glb"), filename=op["stage"] + "-geometry.glb")
