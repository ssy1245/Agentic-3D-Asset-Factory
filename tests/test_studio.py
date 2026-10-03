import asyncio
import base64
import io
import json
import time
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from asset_factory.models import Region
from asset_factory.provider import OpenAIProvider, ProviderError, Result, region_mask
from asset_factory.studio import create_app


def png():
    out = io.BytesIO()
    Image.new("RGBA", (100, 100), "white").save(out, format="PNG")
    return out.getvalue()


def grid_png():
    out = io.BytesIO()
    image = Image.new("RGB", (100, 150), "white")
    draw = ImageDraw.Draw(image)
    for x, y in ((10, 10), (65, 10), (10, 85), (65, 85)):
        draw.rectangle((x, y, x + 20, y + 50), fill="black")
    image.save(out, format="PNG")
    return out.getvalue()


class FakeProvider:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    async def generate(self, *args):
        self.calls += 1
        if self.error:
            raise self.error
        return Result(png() if args[0] == "design" else grid_png(), {"total_tokens": 20}, "req-test", "test")


@pytest.fixture
def client(tmp_path):
    provider = FakeProvider()
    with TestClient(create_app(tmp_path, {"demo": provider})) as c:
        c.provider = provider
        yield c


def project(c, max_calls=12):
    return c.post(
        "/api/projects",
        data={"name": "test", "brief": "white hair", "provider": "demo", "max_calls": max_calls},
    ).json()["id"]


def submit(c, pid, stage="design", **fields):
    return c.post(
        f"/api/projects/{pid}/generate",
        json={"stage": stage, "request_id": fields.pop("request_id", f"request-{time.time_ns()}"), **fields},
    )


def finished(c, pid):
    for _ in range(100):
        p = c.get(f"/api/projects/{pid}").json()
        if not any(o["status"] in ("queued", "running") for o in p["operations"]):
            return p
        time.sleep(0.01)
    pytest.fail("background operation did not finish")


def approve(c, pid, stage):
    p = finished(c, pid)
    assert c.post(f"/api/projects/{pid}/approve/{p['current'][stage]}").status_code == 200


def test_project_visual_memory_and_component_context(client):
    pid = project(client)
    other = project(client)
    for stage in ("design", "turnaround", "head", "body"):
        assert submit(client, pid, stage).status_code == 202
        approve(client, pid, stage)
    p = finished(client, pid)
    authority = p["current"]["turnaround"]
    assert p["memory"]["authoritative_turnaround"]["revision_id"] == authority
    body = p["operations"][-1]
    assert body["reference_ids"] == [authority]
    assert body["context_snapshot"]["reference_roles"][0]["role"] == "authoritative_turnaround"
    assert client.get(f"/api/projects/{other}").json()["memory"]["authoritative_turnaround"] is None
    source = p["current"]["head"]
    assert submit(client, pid, "head", source_revision=source, feedback="adjust ears").status_code == 202
    p = finished(client, pid)
    op = p["operations"][-1]
    assert op["reference_ids"] == [source, authority]
    assert [r["role"] for r in op["context_snapshot"]["reference_roles"]] == [
        "edit_source",
        "authoritative_turnaround",
    ]
    assert p["revisions"][-1]["context_snapshot"] == op["context_snapshot"]
    assert (
        submit(client, pid, "turnaround", source_revision=authority, feedback="change outfit").status_code
        == 202
    )
    p = finished(client, pid)
    assert p["memory"]["authoritative_turnaround"] is None
    assert submit(client, pid, "head").status_code == 400
    approve(client, pid, "turnaround")
    assert submit(client, pid, "head").status_code == 202
    p = finished(client, pid)
    assert p["operations"][-1]["reference_ids"] == [p["current"]["turnaround"]]


def test_view_split_assets_and_confirmation_gate(client):
    pid = project(client)
    submit(client, pid)
    approve(client, pid, "design")
    response = client.post(
        f"/api/projects/{pid}/upload",
        data={"stage": "turnaround"},
        files={"image": ("blank.png", png(), "image/png")},
    )
    assert response.status_code == 200
    p = finished(client, pid)
    rid = p["current"]["turnaround"]
    assert p["revisions"][-1]["view_split"]["status"] == "needs_review"
    assert client.post(f"/api/projects/{pid}/approve/{rid}").status_code == 400
    assert submit(client, pid, "turnaround").status_code == 202
    p = finished(client, pid)
    r = p["revisions"][-1]
    assert [v["view"] for v in r["views"]] == ["front", "left", "back", "right"]
    original_ids = [v["id"] for v in r["views"]]
    repeat = client.post(f"/api/projects/{pid}/revisions/{r['id']}/split").json()
    assert [v["id"] for v in repeat["views"]] == original_ids
    for view in r["views"]:
        assert client.get(view["image_url"]).status_code == 200
        assert view["source_revision"] == r["id"]
    other = project(client)
    assert client.get(f"/api/projects/{other}/images/{original_ids[0]}").status_code == 404
    approve(client, pid, "turnaround")


def test_approval_dependency_and_successful_edit_invalidation(client):
    pid = project(client)
    assert submit(client, pid, "turnaround").status_code == 400
    assert submit(client, pid).status_code == 202
    approve(client, pid, "design")
    assert submit(client, pid, "turnaround").status_code == 202
    approve(client, pid, "turnaround")
    p = finished(client, pid)
    source = p["current"]["design"]
    assert (
        submit(
            client,
            pid,
            source_revision=source,
            feedback="change sleeve",
            region={"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.3},
        ).status_code
        == 202
    )
    p = finished(client, pid)
    assert len(p["revisions"]) == 3
    assert p["current"]["design"] != source
    assert next(r for r in p["revisions"] if r["stage"] == "turnaround")["stale"]
    assert submit(client, pid, "head").status_code == 400
    approve(client, pid, "design")
    # Stale downstream references can be regenerated from newly approved parents.
    assert submit(client, pid, "turnaround").status_code == 202
    approve(client, pid, "turnaround")


def test_duplicate_and_unlimited_development_calls(client):
    pid = project(client, max_calls=1)
    first = submit(client, pid, request_id="same-request").json()
    finished(client, pid)
    second = submit(client, pid, request_id="same-request").json()
    assert first["id"] == second["id"]
    assert client.provider.calls == 1
    assert submit(client, pid).status_code == 202
    finished(client, pid)
    assert client.provider.calls == 2
    assert client.get(f"/api/projects/{pid}").json()["max_calls"] is None


def test_unknown_failure_keeps_original_and_blocks_retry(client):
    pid = project(client)
    submit(client, pid)
    p = finished(client, pid)
    source = p["current"]["design"]
    client.provider.error = ProviderError("结果未知", unknown=True, request_id="req-unknown")
    submit(client, pid, source_revision=source, feedback="fix")
    p = finished(client, pid)
    assert p["current"]["design"] == source
    assert len(p["revisions"]) == 1
    op = p["operations"][-1]
    assert op["status"] == "unknown"
    assert submit(client, pid).status_code == 409
    url = f"/api/projects/{pid}/operations/{op['id']}/acknowledge"
    assert client.post(url, json={"checked_provider_records": False, "note": "check"}).status_code == 400
    assert client.post(url, json={"checked_provider_records": True, "note": "checked"}).status_code == 200
    assert client.provider.calls == 2  # Acknowledge never sends another request.


def test_upload_export_and_restart(tmp_path):
    app = create_app(tmp_path, {"demo": FakeProvider()})
    with TestClient(app) as c:
        pid = project(c)
        assert (
            c.post(
                f"/api/projects/{pid}/upload",
                data={"stage": "design"},
                files={"image": ("bad.png", b"bad", "image/png")},
            ).status_code
            == 400
        )
        for stage in ["design", "turnaround", "head", "body", "hair"]:
            assert (
                c.post(
                    f"/api/projects/{pid}/upload",
                    data={"stage": stage},
                    files={"image": ("ref.png", grid_png(), "image/png")},
                ).status_code
                == 200
            )
            approve(c, pid, stage)
        pack = c.get(f"/api/projects/{pid}/export")
        with zipfile.ZipFile(io.BytesIO(pack.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["reference_pack_complete"]
            assert len(archive.namelist()) == 22
            assert len(manifest["revisions"][-1]["views"]) == 4
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()})) as c:
        assert len(c.get(f"/api/projects/{pid}").json()["revisions"]) == 5


def test_restart_does_not_retry_inflight(client):
    pid = project(client)
    store = client.app.state.store
    op = {"id": "interrupted", "project_id": pid, "request_id": "interrupted-request", "status": "running"}
    with store.connect() as db:
        db.execute(
            "INSERT INTO operations VALUES (?,?,?,?,?)",
            (op["id"], pid, op["request_id"], op["status"], json.dumps(op)),
        )
    store.recover()
    assert store.operation(op["id"])["status"] == "unknown"
    assert client.provider.calls == 0


def test_mask_matches_reference():
    mask = region_mask(png(), Region(x=0.2, y=0.2, width=0.3, height=0.3))
    with Image.open(io.BytesIO(mask)) as image:
        assert image.size == (100, 100)
        assert image.getpixel((30, 30))[3] == 0
        assert image.getpixel((0, 0))[3] == 255


def test_openai_generation_and_masked_edit_contract():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            headers={"x-request-id": "req-mock"},
            json={"data": [{"b64_json": base64.b64encode(png()).decode()}], "usage": {"total_tokens": 30}},
        )

    provider = OpenAIProvider("test-only", "test-model", httpx.MockTransport(handler))
    first = asyncio.run(provider.generate("design", "prompt", []))
    asyncio.run(
        provider.generate("body", "edit", [png(), png()], Region(x=0.1, y=0.1, width=0.2, height=0.2))
    )
    assert first.request_id == "req-mock"
    assert requests[0].url.path == "/v1/images/generations"
    assert json.loads(requests[0].content)["n"] == 1
    assert requests[1].url.path == "/v1/images/edits"
    assert requests[1].content.count(b'name="image[]"') == 2
    assert b'name="mask"' in requests[1].content


def test_openai_timeout_is_unknown_and_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-vendor-data")

    provider = OpenAIProvider("test-only", "test-model", httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.generate("design", "prompt", []))
    assert caught.value.unknown
    assert "secret" not in str(caught.value)
    assert len(calls) == 1


def attachment(c, pid, purpose="feedback"):
    return c.post(
        f"/api/projects/{pid}/references",
        data={"purpose": purpose},
        files={"image": ("detail.png", png(), "image/png")},
    ).json()


def test_design_modes_and_feedback_attachments(client):
    pid = project(client)
    base = attachment(client, pid, "base")
    detail = attachment(client, pid)
    assert finished(client, pid)["current"] == {}  # Uploading guidance is not a completed design.
    assert submit(client, pid, design_mode="image").status_code == 400
    assert submit(client, pid, design_mode="text", input_image_id=base["id"]).status_code == 400
    assert (
        submit(
            client,
            pid,
            design_mode="image",
            input_image_id=base["id"],
            feedback_image_ids=[detail["id"]],
            feedback="use the sleeve",
        ).status_code
        == 202
    )
    p = finished(client, pid)
    op = p["operations"][-1]
    assert op["reference_ids"] == [base["id"], detail["id"]]
    assert "LAST 1 input images" in op["prompt"]
    assert p["revisions"][-1]["feedback_image_ids"] == [detail["id"]]
    assert (
        submit(
            client,
            pid,
            design_mode="image",
            source_revision=p["current"]["design"],
            feedback_image_ids=[detail["id"]],
        ).status_code
        == 202
    )
    finished(client, pid)
    assert submit(client, pid, design_mode="text", feedback="new outfit").status_code == 202
    p = finished(client, pid)
    assert p["operations"][-1]["reference_ids"] == []
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{pid}/export").content)) as archive:
        assert f"input-references/{detail['id']}.png" in archive.namelist()


def test_attachment_ownership_and_limits(client):
    pid = project(client)
    other = project(client)
    foreign = attachment(client, other)
    assert submit(client, pid, feedback_image_ids=[foreign["id"]]).status_code == 400
    assert submit(client, pid, feedback_image_ids=["missing"] * 4).status_code == 422
    assert client.get(f"/api/projects/{pid}/images/{foreign['id']}").status_code == 404
    assert (
        client.post(
            f"/api/projects/{pid}/references", files={"image": ("bad.png", b"bad", "image/png")}
        ).status_code
        == 400
    )
    assert client.provider.calls == 0


def test_brush_annotation_sent_with_clean_source_and_feedback(client):
    pid = project(client)
    submit(client, pid)
    p = finished(client, pid)
    rid = p["current"]["design"]
    original = client.get(f"/api/projects/{pid}/images/{rid}").content
    detail = attachment(client, pid)
    strokes = [{"points": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}], "width": 0.03}]
    assert (
        submit(
            client,
            pid,
            design_mode="image",
            source_revision=rid,
            feedback="repair the marked hair",
            brush_strokes=strokes,
            feedback_image_ids=[detail["id"]],
        ).status_code
        == 202
    )
    p = finished(client, pid)
    op = p["operations"][-1]
    marked_id = op["annotation_image_id"]
    assert op["reference_ids"] == [rid, marked_id, detail["id"]]
    assert "SECOND input image" in op["prompt"]
    assert "Do not reproduce the red marks" in op["prompt"]
    assert p["revisions"][-1]["annotation_image_id"] == marked_id
    assert p["revisions"][-1]["brush_strokes"] == strokes
    assert client.get(f"/api/projects/{pid}/images/{rid}").content == original
    marked = client.get(f"/api/projects/{pid}/images/{marked_id}").content
    with Image.open(io.BytesIO(marked)) as image:
        assert image.size == (100, 100)
        assert image.getpixel((40, 20)) == (239, 68, 68, 255)
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)


def test_brush_requires_current_source_and_valid_coordinates(client):
    pid = project(client)
    strokes = [{"points": [{"x": 0.5, "y": 0.5}]}]
    assert submit(client, pid, brush_strokes=strokes, feedback="fix").status_code == 400
    assert submit(client, pid, brush_strokes=strokes, design_mode="text").status_code == 400
    assert submit(client, pid, brush_strokes=[{"points": [{"x": 2, "y": 0.5}]}]).status_code == 422
    assert submit(client, pid, brush_strokes=[{"points": [{"x": 0.5, "y": 0.5}] * 2001}]).status_code == 422
    assert client.provider.calls == 0


def test_parallel_components_dependencies_and_isolated_edits(client):
    pid = project(client)
    for part in ("head", "body", "hair"):
        assert submit(client, pid, part).status_code == 400
    for stage in ("design", "turnaround"):
        submit(client, pid, stage)
        approve(client, pid, stage)
    for stage in ("head", "body", "hair"):
        submit(client, pid, stage)
        approve(client, pid, stage)
    p = finished(client, pid)
    assert (
        submit(client, pid, "head", source_revision=p["current"]["head"], feedback="fix ears").status_code
        == 202
    )
    p = finished(client, pid)
    assert all(not r["stale"] and r["approved"] for r in p["revisions"] if r["stage"] in ("body", "hair"))
    assert (
        submit(
            client, pid, "turnaround", source_revision=p["current"]["turnaround"], feedback="change design"
        ).status_code
        == 202
    )
    p = finished(client, pid)
    assert all(r["stale"] for r in p["revisions"] if r["stage"] in ("head", "body", "hair"))


def test_component_batch_is_concurrent_and_idempotent(tmp_path):
    class Concurrent(FakeProvider):
        def __init__(self):
            super().__init__()
            self.running = self.maximum = 0

        async def generate(self, *args):
            self.running += 1
            self.maximum = max(self.maximum, self.running)
            await asyncio.sleep(0.05)
            result = await super().generate(*args)
            self.running -= 1
            return result

    provider = Concurrent()
    with TestClient(create_app(tmp_path, {"demo": provider})) as c:
        pid = project(c)
        for stage in ("design", "turnaround"):
            submit(c, pid, stage)
            approve(c, pid, stage)
        p = finished(c, pid)
        authority = p["current"]["turnaround"]
        payload = {"turnaround_revision": authority}
        first = c.post(f"/api/projects/{pid}/generate-components", json=payload)
        assert first.status_code == 202
        assert all("operation" in r for r in first.json()["results"])
        second = c.post(f"/api/projects/{pid}/generate-components", json=payload)
        assert [r["operation"]["id"] for r in first.json()["results"]] == [
            r["operation"]["id"] for r in second.json()["results"]
        ]
        p = finished(c, pid)
        assert provider.maximum == 3 and provider.calls == 5
        assert all(o["reference_ids"] == [authority] for o in p["operations"][-3:])


def test_review_failure_keeps_generated_component(tmp_path):
    class BrokenReview:
        async def review(self, *args):
            raise ValueError("mock review failure")

    with TestClient(create_app(tmp_path, {"openai": FakeProvider()}, reviewer=BrokenReview())) as c:
        pid = c.post("/api/projects", data={"name": "review", "provider": "openai"}).json()["id"]
        for stage in ("design", "turnaround"):
            submit(c, pid, stage)
            approve(c, pid, stage)
        submit(c, pid, "hair")
        for _ in range(100):
            p = finished(c, pid)
            r = p["revisions"][-1]
            if r.get("quality_review", {}).get("status") == "unavailable":
                break
            time.sleep(0.01)
        assert p["operations"][-1]["status"] == "succeeded"
        assert r["quality_review"]["status"] == "unavailable"
        assert not r["approved"]
        assert c.get(r["image_url"]).status_code == 200


def test_visual_review_schema_and_image_inputs():
    from asset_factory.review import VisualReviewer

    async def handler(request):
        payload = json.loads(request.content)
        assert payload["text"]["format"]["type"] == "json_schema"
        assert len(payload["input"][0]["content"]) == 3
        assert payload["store"] is False
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "verdict": "pass",
                                        "summary": "Face left in hair",
                                        "findings": [
                                            {
                                                "view": "front",
                                                "severity": "error",
                                                "description": "Face remains",
                                                "suggested_change": "Remove face",
                                            }
                                        ],
                                    }
                                ),
                            }
                        ]
                    }
                ],
                "usage": {"total_tokens": 20},
            },
        )

    result = asyncio.run(
        VisualReviewer("test-key", transport=httpx.MockTransport(handler)).review("hair", png(), png())
    )
    assert result["verdict"] == "needs_review" and result["human_review_required"]


class FakeTripo:
    model = "test-tripo"

    def __init__(self, balance=100):
        self.credits = balance
        self.submissions = 0

    async def balance(self):
        return {"balance": self.credits, "frozen": 0}

    async def upload(self, image):
        return "uploaded-token"

    async def submit(self, token, **settings):
        self.submissions += 1
        return "vendor-task"

    async def task(self, task_id):
        return {"status": "success", "progress": 100, "consumed_credit": 40, "output": {}}

    async def download(self, output, path):
        path.write_bytes(b"; FBX 7.4.0 project file\n; mock fixture")


def test_geometry_pipeline_duplicate_and_saved_task(tmp_path):
    tripo = FakeTripo()
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()}, tripo=tripo)) as c:
        pid = project(c)
        for stage in ["design", "turnaround", "head"]:
            submit(c, pid, stage)
            approve(c, pid, stage)
        p = finished(c, pid)
        payload = {
            "stage": "head",
            "source_revision": p["current"]["head"],
            "crop": {"x": 0, "y": 0, "width": 0.5, "height": 1},
            "request_id": "geometry-once",
        }
        assert c.post(f"/api/projects/{pid}/geometry", json=payload).status_code == 202
        p = finished(c, pid)
        op = p["operations"][-1]
        assert op["status"] == "succeeded"
        assert op["provider_task_id"] == "vendor-task"
        assert not op["texture"] and not op["pbr"]
        assert c.get(op["download_url"]).content == b"; FBX 7.4.0 project file\n; mock fixture"
        assert c.post(f"/api/projects/{pid}/geometry", json=payload).json()["id"] == op["id"]
        assert tripo.submissions == 1


def test_geometry_zero_balance_never_submits(tmp_path):
    tripo = FakeTripo(0)
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()}, tripo=tripo)) as c:
        pid = project(c)
        response = c.post(
            f"/api/projects/{pid}/geometry",
            json={
                "stage": "head",
                "source_revision": "unused",
                "crop": {"x": 0, "y": 0, "width": 1, "height": 1},
                "request_id": "zero-balance-test",
            },
        )
        assert response.status_code == 402
        assert not c.get(f"/api/projects/{pid}").json()["operations"]
        assert tripo.submissions == 0


def test_tripo_http_contract_without_paid_calls(tmp_path):
    from asset_factory.tripo import TripoProvider

    calls = []
    glb = b"glTF" + (2).to_bytes(4, "little") + (12).to_bytes(4, "little")

    def handler(req):
        calls.append(req)
        if req.url.host == "cdn.tripo3d.ai":
            assert "authorization" not in req.headers
            return httpx.Response(200, content=glb)
        if req.url.path.endswith("/upload"):
            return httpx.Response(200, json={"code": 0, "data": {"image_token": "image-token"}})
        if req.url.path.endswith("/task"):
            payload = json.loads(req.content)
            assert payload["file"]["file_token"] == "image-token"
            assert payload["quad"] is True
            assert payload["texture"] is False and payload["pbr"] is False
            return httpx.Response(200, json={"code": 0, "data": {"task_id": "task-id"}})
        return httpx.Response(200, json={"code": 0, "data": {"balance": 100}})

    provider = TripoProvider("test-only", transport=httpx.MockTransport(handler))
    token = asyncio.run(provider.upload(png()))
    assert asyncio.run(provider.submit(token)) == "task-id"
    path = tmp_path / "model.glb"
    asyncio.run(provider.download({"model": "https://cdn.tripo3d.ai/model.glb"}, path))
    assert path.read_bytes() == glb
    assert len(calls) == 3


def test_default_app_disables_3d_even_with_key(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIPO_API_KEY", "test-only-not-used")
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()})) as c:
        assert c.get("/api/config").json()["tripo_configured"] is False
        assert c.get("/api/services/tripo/balance").json() == {"configured": False}
        assert (
            c.post(
                "/api/projects/unused/geometry",
                json={
                    "stage": "head",
                    "source_revision": "unused",
                    "crop": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "request_id": "disabled-test",
                },
            ).status_code
            == 400
        )


def test_prompt_snapshot_is_recorded_and_visible(client):
    pid = project(client)
    template = client.get("/api/prompts").json()["design"]
    submit(client, pid)
    p = finished(client, pid)
    assert template["version"] == p["operations"][-1]["prompt_template_version"]
    assert template["version"] == p["revisions"][-1]["prompt_template_version"]
    assert template["common"] in p["operations"][-1]["prompt"]
    assert template["instructions"] in p["operations"][-1]["prompt"]


def test_revision_combines_current_visual_review_and_user_feedback(client):
    pid = project(client)
    for stage in ("design", "turnaround"):
        submit(client, pid, stage)
        approve(client, pid, stage)
    submit(client, pid, "hair")
    p = finished(client, pid)
    source = p["current"]["hair"]
    authority = p["current"]["turnaround"]
    report = {
        "status": "completed",
        "source_revision": source,
        "authority_revision": authority,
        "prompt_version": "review-test",
        "summary": "Ear remains in left view.",
        "findings": [
            {
                "view": "left",
                "severity": "error",
                "description": "Ear fragment",
                "suggested_change": "Remove the ear fragment, preserve bangs.",
            }
        ],
    }
    store = client.app.state.store
    with store.connect() as db:
        p = store.get(pid, db)
        next(r for r in p["revisions"] if r["id"] == source)["quality_review"] = report
        store.put(db, p)
    response = submit(
        client,
        pid,
        "hair",
        source_revision=source,
        feedback="Keep natural gaps.",
        request_id="review-combined-test",
    )
    assert response.status_code == 202
    p = finished(client, pid)
    op = p["operations"][-1]
    assert op["reference_ids"] == [source, authority]
    assert op["context_snapshot"]["edit_source_quality_review"]["findings"] == report["findings"]
    assert (
        "Remove the ear fragment" in op["prompt"] and "Requested changes: Keep natural gaps." in op["prompt"]
    )
    assert "User requests take priority" in op["prompt"]
    assert (
        submit(
            client,
            pid,
            "hair",
            source_revision=source,
            feedback="Keep natural gaps.",
            request_id="review-combined-test",
        ).json()["id"]
        == op["id"]
    )


@pytest.mark.parametrize(
    "status,report_source,expected",
    [
        ("completed", "current", 202),
        ("completed", "other", 400),
        ("unavailable", "current", 400),
        ("running", "current", 409),
    ],
)
def test_review_only_revision_requires_completed_matching_report(client, status, report_source, expected):
    pid = project(client)
    for stage in ("design", "turnaround"):
        submit(client, pid, stage)
        approve(client, pid, stage)
    submit(client, pid, "head")
    p = finished(client, pid)
    source = p["current"]["head"]
    store = client.app.state.store
    with store.connect() as db:
        p = store.get(pid, db)
        next(r for r in p["revisions"] if r["id"] == source)["quality_review"] = {
            "status": status,
            "source_revision": source if report_source == "current" else "other",
            "authority_revision": p["current"]["turnaround"],
            "findings": [
                {
                    "view": "right",
                    "description": "Mouth closed",
                    "suggested_change": "Match front mouth opening",
                }
            ],
        }
        store.put(db, p)
    assert submit(client, pid, "head", source_revision=source).status_code == expected
    if expected == 202:
        assert "Match front mouth opening" in finished(client, pid)["operations"][-1]["prompt"]


def test_model_preview_approval_and_blender_export(tmp_path):
    import struct

    document = {"asset": {"version": "2.0"}, "meshes": [{"primitives": [{"attributes": {}}]}]}
    chunk = json.dumps(document).encode()
    chunk += b" " * (-len(chunk) % 4)
    glb = b"glTF" + struct.pack("<II", 2, 20 + len(chunk)) + struct.pack("<I", len(chunk)) + b"JSON" + chunk

    class ModelTripo(FakeTripo):
        async def download(self, output, path):
            path.write_bytes(glb)

    with TestClient(create_app(tmp_path, {"demo": FakeProvider()}, tripo=ModelTripo())) as c:
        pid = project(c)
        other = project(c)
        for stage in ("design", "turnaround", "head"):
            submit(c, pid, stage)
            approve(c, pid, stage)
        source = finished(c, pid)["current"]["head"]
        response = c.post(
            f"/api/projects/{pid}/geometry",
            json={
                "stage": "head",
                "source_revision": source,
                "crop": {"x": 0, "y": 0, "width": 0.5, "height": 1},
                "request_id": "model-preview-test",
            },
        )
        assert response.status_code == 202
        op = finished(c, pid)["operations"][-1]
        # This existing GLB fixture covers legacy results alongside new FBX results.
        (tmp_path / pid / (op["id"] + ".fbx")).rename(tmp_path / pid / (op["id"] + ".glb"))
        op["model_format"] = "glb"
        with c.app.state.store.connect() as db:
            c.app.state.store.put_operation(db, op)
        base = f"/api/projects/{pid}/geometry/{op['id']}"
        assert c.get(base + "/preview").content == glb
        assert c.get(base + "/preview").headers["content-type"] == "model/gltf-binary"
        assert c.get(base + "/info").json()["meshes"] == 1
        assert c.get(base + "/blender-package").status_code == 409
        assert c.post(base + "/approve", json={"checked": False}).status_code == 422
        assert c.post(base + "/approve", json={"checked": True}).json()["visual_approved"]
        with zipfile.ZipFile(io.BytesIO(c.get(base + "/blender-package").content)) as archive:
            assert archive.read("head.glb") == glb
            assert json.loads(archive.read("manifest.json"))["models"][0]["source_revision"] == source
            assert "bpy.ops.import_scene.gltf" in archive.read("import_blender.py").decode()
        assert c.get(f"/api/projects/{other}/geometry/{op['id']}/preview").status_code == 404
        submit(c, pid, "head", source_revision=source, feedback="change head")
        finished(c, pid)
        assert c.post(base + "/approve", json={"checked": True}).status_code == 409
        assert c.get(base + "/blender-package").status_code == 409


def test_last_component_approval_starts_parallel_models_once(tmp_path):
    class ParallelTripo(FakeTripo):
        def __init__(self):
            super().__init__()
            self.running = 0
            self.maximum = 0

        async def upload(self, image):
            self.running += 1
            self.maximum = max(self.maximum, self.running)
            await asyncio.sleep(0.04)
            self.running -= 1
            return "test-token"

        async def submit(self, token, **settings):
            await asyncio.sleep(0.04)
            self.submissions += 1
            return f"test-task-{self.submissions}"

    tripo = ParallelTripo()
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()}, tripo=tripo)) as c:
        pid = project(c)
        for stage in ("design", "turnaround"):
            submit(c, pid, stage)
            approve(c, pid, stage)
        for part in ("head", "body", "hair"):
            submit(c, pid, part)
        p = finished(c, pid)
        refs = {part: p["current"][part] for part in ("head", "body", "hair")}
        assert (
            c.post(f"/api/projects/{pid}/generate-models", json={"component_revisions": refs}).status_code
            == 409
        )
        approve(c, pid, "hair")
        approve(c, pid, "head")
        assert tripo.submissions == 0
        response = c.post(f"/api/projects/{pid}/approve/{refs['body']}")
        assert response.status_code == 200
        assert len(response.json()["model_submission"]["results"]) == 3
        p = finished(c, pid)
        models = [o for o in p["operations"] if o.get("kind") == "geometry"]
        assert len(models) == 3 and tripo.maximum == 3 and tripo.submissions == 3
        for op in models:
            assert op["quad"] is True
            assert op["face_limit"] == (5000 if op["stage"] == "head" else 20000)
            assert op["model_format"] == "fbx"
            source = next(r for r in p["revisions"] if r["id"] == refs[op["stage"]])
            front = next(v for v in source["views"] if v["view"] == "front")
            assert op["source_view_id"] == front["id"] and op["source_view"] == "multiview"
            assert [v["view"] for v in op["input_views"]] == ["front", "left", "back", "right"]
            for v in op["input_views"]:
                assert (tmp_path / pid / (v["input_id"] + ".png")).read_bytes() == (
                    tmp_path / pid / (v["source_view_id"] + ".png")
                ).read_bytes()
            assert (tmp_path / pid / (op["input_id"] + ".png")).read_bytes() == (
                tmp_path / pid / (front["id"] + ".png")
            ).read_bytes()
        c.post(f"/api/projects/{pid}/approve/{refs['body']}")
        assert (
            c.post(f"/api/projects/{pid}/generate-models", json={"component_revisions": refs}).status_code
            == 202
        )
        assert tripo.submissions == 3


@pytest.mark.parametrize("face_limit", [5000, 20000])
def test_quad_request_and_fbx_download_contract(tmp_path, face_limit):
    from asset_factory.tripo import TripoProvider

    fbx = b"; FBX 7.4.0 project file\n; mock quad output"

    def handler(req):
        if req.url.host == "cdn.tripo3d.ai":
            assert "authorization" not in req.headers
            return httpx.Response(200, content=fbx)
        payload = json.loads(req.content)
        assert payload["quad"] is True and payload["face_limit"] == face_limit
        assert payload["smart_low_poly"] is False
        assert payload["texture"] is False and payload["pbr"] is False and payload["export_uv"] is False
        return httpx.Response(200, json={"code": 0, "data": {"task_id": "quad-test"}})

    provider = TripoProvider("not-real", transport=httpx.MockTransport(handler))
    assert asyncio.run(provider.submit("token", face_limit=face_limit, quad=True)) == "quad-test"
    path = tmp_path / "quad.fbx"
    asyncio.run(provider.download({"base_model": "https://cdn.tripo3d.ai/quad.fbx"}, path))
    assert path.read_bytes() == fbx


def test_fbx_without_blender_keeps_original_and_can_export(tmp_path, monkeypatch):
    async def unavailable(path):
        return {"status": "unavailable", "reason": "Blender not installed"}

    monkeypatch.setattr("asset_factory.geometry.prepare_fbx_preview", unavailable)
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()}, tripo=FakeTripo())) as c:
        pid = project(c)
        for stage in ("design", "turnaround", "head"):
            submit(c, pid, stage)
            approve(c, pid, stage)
        source = finished(c, pid)["current"]["head"]
        response = c.post(
            f"/api/projects/{pid}/geometry",
            json={"stage": "head", "source_revision": source, "request_id": "quad-fallback-test"},
        )
        assert response.status_code == 202
        op = finished(c, pid)["operations"][-1]
        base = f"/api/projects/{pid}/geometry/{op['id']}"
        assert op["status"] == "succeeded" and op["preview"]["status"] == "unavailable"
        preview = c.get(base + "/preview")
        assert preview.status_code == 200 and preview.headers["x-model-format"] == "fbx"
        assert preview.content == c.get(base + "/download").content
        assert c.get(base + "/info").json()["requested_face_limit"] == 5000
        original = c.get(base + "/download").content
        assert original.startswith(b"; FBX")
        assert c.post(base + "/prepare-preview").json()["preview"]["status"] == "unavailable"
        assert c.post(base + "/approve", json={"checked": True}).status_code == 200
        with zipfile.ZipFile(io.BytesIO(c.get(base + "/blender-package").content)) as archive:
            assert archive.read("head.fbx") == original
            assert "bpy.ops.import_scene.fbx" in archive.read("import_blender.py").decode()


def test_tripo_multiview_payload_order():
    from asset_factory.tripo import TripoProvider

    def handler(req):
        payload = json.loads(req.content)
        assert payload["type"] == "multiview_to_model" and "file" not in payload
        assert [v["file_token"] for v in payload["files"]] == [
            "front-token",
            "left-token",
            "back-token",
            "right-token",
        ]
        assert payload["quad"] is True and payload["face_limit"] == 5000
        assert payload["texture"] is False and payload["pbr"] is False
        return httpx.Response(200, json={"code": 0, "data": {"task_id": "multi-test"}})

    provider = TripoProvider("fake", transport=httpx.MockTransport(handler))
    assert (
        asyncio.run(
            provider.submit(
                ["front-token", "left-token", "back-token", "right-token"], face_limit=5000, quad=True
            )
        )
        == "multi-test"
    )
    with pytest.raises(ValueError):
        asyncio.run(provider.submit(["front-token"], quad=True))


def test_tripo_rejects_triangle_generation_before_network():
    from asset_factory.tripo import TripoProvider

    def handler(req):
        pytest.fail("triangle generation must never reach Tripo")

    provider = TripoProvider("fake", transport=httpx.MockTransport(handler))
    with pytest.raises(ValueError, match="四边形"):
        asyncio.run(provider.submit("token", quad=False))


def test_reopen_approved_component_preserves_images_and_siblings(client):
    pid = project(client)
    for stage in ("design", "turnaround", "head", "body", "hair"):
        submit(client, pid, stage)
        approve(client, pid, stage)
    before = finished(client, pid)
    rid = before["current"]["body"]
    image = client.get(f"/api/projects/{pid}/images/{rid}").content
    assert client.post(f"/api/projects/{pid}/reopen/{rid}").status_code == 200
    after = finished(client, pid)
    assert after["current"] == before["current"]
    assert len(after["revisions"]) == len(before["revisions"])
    assert next(r for r in after["revisions"] if r["id"] == rid)["approved"] is False
    for part in ("head", "hair"):
        assert next(r for r in after["revisions"] if r["id"] == after["current"][part])["approved"] is True
    assert client.get(f"/api/projects/{pid}/images/{rid}").content == image
    approve(client, pid, "body")
    assert len(finished(client, pid)["operations"]) == len(before["operations"])
