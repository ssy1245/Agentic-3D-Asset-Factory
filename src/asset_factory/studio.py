import asyncio
import hashlib
import io
import json
import os
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .geometry import attach_geometry
from .models import GenerateRequest, Stage
from .prompts import prompt_templates
from .provider import DemoProvider, OpenAIProvider, ProviderError, annotated_reference, normalize_image
from .storage import Store, identity, now
from .views import split_views

ROOT = Path(__file__).resolve().parents[2]
LABELS = {"design": "整体设计", "turnaround": "四视图", "head": "头部", "body": "身体与服装", "hair": "头发"}


def revision(project, rid):
    return next((r for r in project["revisions"] if r["id"] == rid), None)


def project_memory(project):
    """Derive authoritative memory from confirmed versions, never from history alone."""
    confirmed = {}
    for stage, rid in project["current"].items():
        r = revision(project, rid)
        if r and r["approved"] and not r["stale"]:
            confirmed[stage] = {"revision_id": rid, "sha256": r["sha256"], "image_url": r["image_url"]}
    return {
        "project_id": project["id"],
        "character_brief": project["brief"],
        "confirmed_references": confirmed,
        "authoritative_turnaround": confirmed.get("turnaround"),
    }


def required_refs(project, stage):
    names = list(LABELS)[: list(LABELS).index(stage)]
    result = []
    for name in names:
        rid = project["current"].get(name)
        r = revision(project, rid)
        if not r or not r["approved"] or r["stale"]:
            raise ValueError(f"请先确认有效的{LABELS[name]}")
        result.append(rid)
    return result


def invalidate(project, changed):
    impacted = set(list(LABELS)[list(LABELS).index(changed) + 1 :])
    for r in project["revisions"]:
        if r["stage"] in impacted:
            r.update(stale=True, approved=False)


def create_app(data_dir=None, providers=None, tripo=None):
    load_dotenv(ROOT / ".env")
    store = Store(Path(data_dir) if data_dir else ROOT / "data")
    if providers is None:
        providers = {"demo": DemoProvider(ROOT / "fixtures")}
        key = os.getenv("OPENAI_API_KEY") or os.getenv("ChatGPT_API_KEY") or os.getenv("CHATGPT_API_KEY")
        if key:
            providers["openai"] = OpenAIProvider(
                key, os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst")
            )
    tasks = set()

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Reference Studio", lifespan=lifespan)
    app.state.store = store
    app.state.providers = providers
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "web"), name="static")

    def get_project(pid):
        try:
            return store.get(pid)
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error

    def image_path(pid, rid):
        return store.root / pid / f"{rid}.png"

    def add_revision(project, stage, image, **details):
        rid = identity()
        path = image_path(project["id"], rid)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
        r = {
            "id": rid,
            "stage": stage,
            "created_at": now(),
            "approved": False,
            "stale": False,
            "sha256": hashlib.sha256(image).hexdigest(),
            "image_url": f"/api/projects/{project['id']}/images/{rid}",
            **details,
        }
        invalidate(project, stage)
        old = revision(project, project["current"].get(stage))
        if old:
            old["approved"] = False
        project["revisions"].append(r)
        project["current"][stage] = rid
        if stage != "design":
            add_views(project, r)
        return r

    def add_views(project, r):
        if r.get("view_split", {}).get("status") == "ready":
            return
        try:
            crops = split_views(image_path(project["id"], r["id"]).read_bytes())
        except ValueError as error:
            r["view_split"] = {"status": "needs_review", "error": str(error)}
            return
        r["views"] = []
        for crop in crops:
            raw = crop.pop("image")
            vid = identity()
            image_path(project["id"], vid).write_bytes(raw)
            asset = {
                "id": vid,
                "purpose": "view_crop",
                "source_revision": r["id"],
                "part": r["stage"],
                "name": f"{r['stage']}_{crop['view']}.png",
                "image_url": f"/api/projects/{project['id']}/images/{vid}",
                "sha256": hashlib.sha256(raw).hexdigest(),
                **crop,
            }
            project.setdefault("reference_images", []).append(asset)
            r["views"].append(asset)
        r["view_split"] = {
            "status": "ready",
            "method": "light-background-gutter-v1",
            "layout": "grid-2x2-v1",
            "human_review_required": True,
        }

    @app.post("/api/projects/{pid}/revisions/{rid}/split")
    def split_existing(pid: str, rid: str):
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            p = store.get(pid, db)
            if active(pid, db):
                raise HTTPException(409, "请先等待当前操作完成")
            r = revision(p, rid)
            if not r or r["stage"] == "design":
                raise HTTPException(400, "请选择四视图版本")
            add_views(p, r)
            store.put(db, p)
        return r

    def active(pid, db):
        return next(
            (o for o in store.operations(pid, db) if o["status"] in ("queued", "running", "unknown")), None
        )

    @app.get("/")
    def home():
        return FileResponse(Path(__file__).parent / "web" / "index.html")

    @app.get("/api/config")
    def config():
        return {
            "providers": list(providers),
            "default_provider": "openai" if "openai" in providers else "demo",
            "tripo_configured": tripo is not None,
            "tripo_model": tripo.model if tripo else None,
            "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2.5-sunburst"),
            "max_calls": 12,
            "stages": LABELS,
        }

    @app.get("/api/prompts")
    def prompts():
        return prompt_templates()

    @app.get("/api/projects")
    def projects():
        return [
            {"id": p["id"], "name": p["name"], "provider": p["provider"], "created_at": p["created_at"]}
            for p in store.projects()
        ]

    @app.post("/api/projects")
    def create(
        name: str = Form(..., min_length=1, max_length=100),
        brief: str = Form(..., min_length=1, max_length=6000),
        provider: str = Form("demo"),
        max_calls: int = Form(12, ge=1, le=30),
    ):
        if provider not in providers:
            raise HTTPException(400, "该出图服务尚未配置")
        project = {
            "id": identity(),
            "name": name,
            "brief": brief,
            "provider": provider,
            "created_at": now(),
            "max_calls": max_calls,
            "current": {},
            "revisions": [],
        }
        store.create(project)
        return project

    @app.get("/api/projects/{pid}")
    def project(pid: str):
        p = get_project(pid)
        p["memory"] = project_memory(p)
        p["operations"] = store.operations(pid)
        p["calls_used"] = sum(
            o["status"] not in ("failed",) or o.get("started_at") is not None
            for o in p["operations"]
            if o.get("kind") != "geometry"
        )
        return p

    @app.post("/api/projects/{pid}/upload")
    async def upload(pid: str, stage: Annotated[Stage, Form()], image: Annotated[UploadFile, File()]):
        raw = await image.read(15 * 1024 * 1024 + 1)
        if len(raw) > 15 * 1024 * 1024:
            raise HTTPException(413, "图片不能超过 15 MB")
        try:
            png = normalize_image(raw)
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                p = store.get(pid, db)
                if active(pid, db):
                    raise HTTPException(409, "请先等待或核对当前出图操作")
                deps = required_refs(p, stage)
                add_revision(
                    p,
                    stage,
                    png,
                    source="upload",
                    feedback="用户上传",
                    dependencies=deps,
                    parent_revision=None,
                    provider="upload",
                    prompt="",
                    region=None,
                    usage=None,
                )
                store.put(db, p)
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return p

    @app.post("/api/projects/{pid}/references")
    async def upload_reference(
        pid: str, image: Annotated[UploadFile, File()], purpose: Annotated[str, Form()] = "feedback"
    ):
        if purpose not in ("base", "feedback"):
            raise HTTPException(400, "参考图类型无效")
        raw = await image.read(15 * 1024 * 1024 + 1)
        if len(raw) > 15 * 1024 * 1024:
            raise HTTPException(413, "图片不能超过 15 MB")
        try:
            png = normalize_image(raw)
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                p = store.get(pid, db)
                rid = identity()
                path = image_path(pid, rid)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(png)
                asset = {
                    "id": rid,
                    "purpose": purpose,
                    "created_at": now(),
                    "name": Path(image.filename or "reference.png").name[:200],
                    "image_url": f"/api/projects/{pid}/images/{rid}",
                    "sha256": hashlib.sha256(png).hexdigest(),
                }
                p.setdefault("reference_images", []).append(asset)
                store.put(db, p)
            return asset
        except KeyError as error:
            raise HTTPException(404, "任务不存在") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    async def execute(oid):
        with store.connect() as db:
            op = store.operation(oid, db)
            op.update(status="running", started_at=now())
            store.put_operation(db, op)
            p = store.get(op["project_id"], db)
        try:
            references = [image_path(p["id"], rid).read_bytes() for rid in op["reference_ids"]]
            result = await providers[p["provider"]].generate(
                op["stage"], op["prompt"], references, GenerateRequest.model_validate(op["request"]).region
            )
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                p = store.get(p["id"], db)
                r = add_revision(
                    p,
                    op["stage"],
                    result.image,
                    source="generation",
                    feedback=op["request"]["feedback"],
                    dependencies=op["dependencies"],
                    parent_revision=op["request"]["source_revision"],
                    provider=p["provider"],
                    prompt=op["prompt"],
                    prompt_template_version=op.get("prompt_template_version"),
                    context_snapshot=op.get("context_snapshot"),
                    region=op["request"]["region"],
                    usage=result.usage,
                    model=result.model,
                    design_mode=op["request"].get("design_mode"),
                    input_image_id=op["request"].get("input_image_id"),
                    feedback_image_ids=op["request"].get("feedback_image_ids", []),
                    annotation_image_id=op.get("annotation_image_id"),
                    brush_strokes=op["request"].get("brush_strokes", []),
                )
                store.put(db, p)
                op.update(
                    status="succeeded",
                    finished_at=now(),
                    revision_id=r["id"],
                    usage=result.usage,
                    provider_request_id=result.request_id,
                )
                store.put_operation(db, op)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 — persist every background failure
            unknown = isinstance(error, ProviderError) and error.unknown
            message = (
                str(error) if isinstance(error, ProviderError) else "本地处理失败，原版本保留；请核对记录。"
            )
            # A local failure after starting a paid request is also potentially billed.
            if p["provider"] != "demo" and not isinstance(error, ProviderError):
                unknown = True
            with store.connect() as db:
                op.update(
                    status="unknown" if unknown else "failed",
                    error=message,
                    finished_at=now(),
                    provider_request_id=getattr(error, "request_id", None),
                )
                store.put_operation(db, op)

    @app.post("/api/projects/{pid}/generate", status_code=202)
    async def generate(pid: str, request: GenerateRequest):
        try:
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                p = store.get(pid, db)
                existing = next(
                    (o for o in store.operations(pid, db) if o["request_id"] == request.request_id), None
                )
                if existing:
                    return existing
                if active(pid, db):
                    raise HTTPException(409, "已有进行中或结果未知的操作，请先处理")
                used = sum(
                    bool(o.get("started_at")) or o["status"] == "queued"
                    for o in store.operations(pid, db)
                    if o.get("kind") != "geometry"
                )
                if used >= p["max_calls"]:
                    raise HTTPException(409, "已达到本任务的出图次数上限")
                deps = required_refs(p, request.stage)
                memory = project_memory(p)
                # Workflow prerequisites are distinct from visual inputs.
                if request.stage == "design":
                    refs = []
                elif request.stage == "turnaround":
                    refs = [memory["confirmed_references"]["design"]["revision_id"]]
                else:
                    refs = [memory["authoritative_turnaround"]["revision_id"]]
                assets = {a["id"] for a in p.get("reference_images", [])}
                if any(
                    rid not in assets
                    for rid in [
                        *request.feedback_image_ids,
                        *([request.input_image_id] if request.input_image_id else []),
                    ]
                ):
                    raise ValueError("参考图片不存在或不属于当前角色")
                if request.stage != "design" and (request.design_mode or request.input_image_id):
                    raise ValueError("生成模式与初始图片仅适用于整体设计")
                if request.design_mode == "text" and (
                    request.source_revision
                    or request.input_image_id
                    or request.feedback_image_ids
                    or request.region
                    or request.brush_strokes
                ):
                    raise ValueError("文字生成模式不使用图片，请切换已有图像生成")
                if request.design_mode == "image" and not (request.source_revision or request.input_image_id):
                    raise ValueError("请上传初始图片或选择当前整体设计")
                if request.input_image_id and request.source_revision:
                    raise ValueError("只能选择一张初始图片")
                if request.input_image_id:
                    if request.region:
                        raise ValueError("请先生成并显示初始图片，再进行框选修改")
                    refs.insert(0, request.input_image_id)
                if request.source_revision:
                    source = revision(p, request.source_revision)
                    if not source or source["stage"] != request.stage or source["stale"]:
                        raise ValueError("修改源版本不存在、步骤不匹配或已过期")
                    if request.source_revision != p["current"].get(request.stage):
                        raise ValueError("请基于当前版本修改，避免历史版本分支混淆")
                    refs.insert(0, source["id"])
                elif request.region:
                    raise ValueError("框选修改需要已有图片")
                if (
                    request.source_revision
                    and not request.feedback.strip()
                    and not request.feedback_image_ids
                ):
                    raise ValueError("请填写修改意见")
                annotation_id = None
                if request.brush_strokes:
                    if not request.source_revision:
                        raise ValueError("圈画修改需要当前有效版本作为原图")
                    marked = annotated_reference(
                        image_path(pid, request.source_revision).read_bytes(), request.brush_strokes
                    )
                    annotation_id = identity()
                    image_path(pid, annotation_id).write_bytes(marked)
                    p.setdefault("reference_images", []).append(
                        {
                            "id": annotation_id,
                            "purpose": "annotation",
                            "name": "圈画修改意见.png",
                            "source_revision": request.source_revision,
                            "created_at": now(),
                            "image_url": f"/api/projects/{pid}/images/{annotation_id}",
                            "sha256": hashlib.sha256(marked).hexdigest(),
                        }
                    )
                    store.put(db, p)
                    refs.insert(1, annotation_id)
                template = prompt_templates()[request.stage]
                prompt = f"{template['common']}\nCharacter brief: {p['brief']}\n{template['instructions']}"
                if request.source_revision or request.input_image_id:
                    prompt += "\nEdit the FIRST input image. Other images are identity references. Preserve the established identity, proportions, palette and all unrequested details."
                if annotation_id:
                    prompt += "\nThe SECOND input image is an annotated copy of the FIRST clean source image. The red freehand circles and lines are user instructions locating areas to change, NOT character features. Use them together with the requested changes. Do not reproduce the red marks in the output; preserve unrelated details from the clean source."
                if request.feedback_image_ids:
                    refs.extend(request.feedback_image_ids)
                    prompt += f"\nThe LAST {len(request.feedback_image_ids)} input images are user-uploaded change references. Use them to guide the requested details; do not replace the character identity or copy unrelated backgrounds."
                    if not request.feedback.strip():
                        prompt += "\nApply the relevant visual details from the change references to the character while preserving other details."
                if request.feedback.strip():
                    prompt += f"\nRequested changes: {request.feedback}"
                refs = list(dict.fromkeys(refs))
                authority = (
                    memory["authoritative_turnaround"] if request.stage in ("head", "body", "hair") else None
                )
                reference_roles = []
                for index, rid in enumerate(refs, 1):
                    if rid == request.source_revision or rid == request.input_image_id:
                        role = "edit_source"
                    elif rid == annotation_id:
                        role = "annotation"
                    elif authority and rid == authority["revision_id"]:
                        role = "authoritative_turnaround"
                    elif rid in request.feedback_image_ids:
                        role = "change_reference"
                    else:
                        role = "approved_design"
                    reference_roles.append({"image_number": index, "revision_id": rid, "role": role})
                    prompt += f"\nInput image {index} role: {role}."
                if authority:
                    prompt += "\nThe authoritative_turnaround is the approved whole-character visual authority. Derive this component from it, preserving identity, proportions, colors and visible details. Produce front, left profile, back and right profile views in that order. When editing a component, the edit_source is the target, while the authoritative_turnaround constrains consistency. Change references guide only requested details; do not silently redesign the character."
                if request.region:
                    prompt += "\nThe transparent mask region indicates the requested edit area. Preserve other areas as closely as possible."
                op = {
                    "id": identity(),
                    "project_id": pid,
                    "request_id": request.request_id,
                    "stage": request.stage,
                    "status": "queued",
                    "created_at": now(),
                    "request": request.model_dump(mode="json"),
                    "reference_ids": list(dict.fromkeys(refs)),
                    "annotation_image_id": annotation_id,
                    "dependencies": deps,
                    "prompt": prompt,
                    "prompt_template_version": template["version"],
                    "context_snapshot": {
                        "schema_version": 1,
                        "project_id": pid,
                        "character_brief": p["brief"],
                        "authoritative_turnaround": authority,
                        "reference_roles": reference_roles,
                        "prompt_template_version": template["version"],
                    },
                    "provider": p["provider"],
                    "usage": None,
                    "error": None,
                    "cost_usd": None,
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
            raise HTTPException(404, "任务不存在") from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error

    @app.post("/api/projects/{pid}/approve/{rid}")
    def approve(pid: str, rid: str):
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                p = store.get(pid, db)
            except KeyError as error:
                raise HTTPException(404, "任务不存在") from error
            if active(pid, db):
                raise HTTPException(409, "请先等待或核对当前操作")
            r = revision(p, rid)
            if not r or r["stale"] or p["current"].get(r["stage"]) != rid:
                raise HTTPException(400, "只能确认当前有效版本")
            if r["stage"] != "design" and r.get("view_split", {}).get("status") != "ready":
                raise HTTPException(400, "请先完成四视图拆分并检查裁切预览")
            try:
                required_refs(p, r["stage"])
            except ValueError as error:
                raise HTTPException(400, str(error)) from error
            r["approved"] = True
            r["approved_at"] = now()
            store.put(db, p)
        return p

    class Acknowledge(BaseModel):
        checked_provider_records: bool
        note: str = Field(min_length=1, max_length=1000)

    @app.post("/api/projects/{pid}/operations/{oid}/acknowledge")
    def acknowledge(pid: str, oid: str, req: Acknowledge):
        if not req.checked_provider_records:
            raise HTTPException(400, "请先核对供应商记录")
        with store.connect() as db:
            try:
                op = store.operation(oid, db)
            except KeyError as error:
                raise HTTPException(404, "操作不存在") from error
            if op["project_id"] != pid or op["status"] != "unknown":
                raise HTTPException(400, "操作状态不允许解除")
            op.update(status="acknowledged", acknowledgement=req.note, acknowledged_at=now())
            store.put_operation(db, op)
        return op

    @app.get("/api/projects/{pid}/images/{rid}")
    def image(pid: str, rid: str):
        p = get_project(pid)
        if (
            not (revision(p, rid) or any(a["id"] == rid for a in p.get("reference_images", [])))
            or not image_path(pid, rid).is_file()
        ):
            raise HTTPException(404, "图片不存在")
        return FileResponse(image_path(pid, rid), media_type="image/png")

    @app.get("/api/projects/{pid}/export")
    def export(pid: str):
        p = get_project(pid)
        complete = all(
            (r := revision(p, p["current"].get(s))) and r["approved"] and not r["stale"] for s in LABELS
        )
        manifest = {
            **p,
            "memory": project_memory(p),
            "operations": store.operations(pid),
            "reference_pack_complete": complete,
            "note": "参考图包，不包含三维模型；demo 来源图不是本软件生成的结果。",
        }
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for asset in p.get("reference_images", []):
                name = (
                    f"views/{asset['part']}/{asset['source_revision']}/{asset['view']}.png"
                    if asset.get("purpose") == "view_crop"
                    else f"input-references/{asset['id']}.png"
                )
                archive.write(image_path(pid, asset["id"]), name)
            for s, rid in p["current"].items():
                archive.write(image_path(pid, rid), f"{s}.png")
        return Response(
            out.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="references-{pid[:8]}.zip"'},
        )

    # 3D is paused: only explicit test injection registers these routes.
    if tripo is not None:
        attach_geometry(app, store, tripo, tasks, required_refs, revision, active)
    return app
