"""Offline load-test providers. Synthetic outputs are never production assets."""
import asyncio
import io
import json
import math
import os
import random
import secrets
import struct
import time
from functools import lru_cache

from PIL import Image, ImageDraw

from .provider import ProviderError, Result


class MockSettings:
    def __init__(self):
        self.delay_ms = float(os.getenv("STUDIO_MOCK_DELAY_MS", "250"))
        self.failure_rate = float(os.getenv("STUDIO_MOCK_FAILURE_RATE", "0"))
        if not math.isfinite(self.delay_ms) or not 0 <= self.delay_ms <= 60000:
            raise ValueError("STUDIO_MOCK_DELAY_MS must be between 0 and 60000")
        if not math.isfinite(self.failure_rate) or not 0 <= self.failure_rate <= 1:
            raise ValueError("STUDIO_MOCK_FAILURE_RATE must be between 0 and 1")

    async def wait(self, fail=True):
        await asyncio.sleep(self.delay_ms / 1000)
        if fail and random.random() < self.failure_rate:
            raise ProviderError("Mock 模拟供应商失败；没有发出真实 API 请求。")


@lru_cache(maxsize=2)
def mock_image(sheet):
    image = Image.new("RGB", (512, 768), "white")
    draw = ImageDraw.Draw(image)
    for box in ([(48, 40, 200, 320), (310, 40, 460, 320),
                 (48, 430, 200, 730), (310, 430, 460, 730)]
                if sheet else [(120, 80, 390, 700)]):
        draw.rectangle(box, fill="#537b64")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class MockImageProvider:
    def __init__(self, settings):
        self.settings = settings

    async def generate(self, stage, prompt, references, region=None):
        await self.settings.wait()
        return Result(mock_image(stage != "design"), {"mock": True, "cost": 0},
                      "mock-" + secrets.token_hex(8), "mock-local-image")


class MockReviewer:
    def __init__(self, settings):
        self.settings = settings

    async def review(self, stage, image, authority):
        await self.settings.wait()
        return {"status": "completed", "verdict": "pass", "findings": [],
                "summary": "Mock 压测结果，不代表实际资产质量。", "mock": True,
                "model": "mock-local-review", "usage": {"mock": True, "cost": 0},
                "human_review_required": True}


VERTICES = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
QUADS = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (3, 7, 6, 2), (0, 4, 7, 3), (1, 2, 6, 5)]


@lru_cache(maxsize=1)
def mock_fbx():
    # ASCII FBX fixture retains six quads; native Blender export is disabled in this mode.
    vertices = ",".join(str(n) for vertex in VERTICES for n in vertex)
    indices = ",".join(str(n) for face in QUADS for n in (*face[:3], -face[3] - 1))
    return ("; FBX 7.4.0 project file - MOCK LOAD TEST ONLY\n"
            "FBXHeaderExtension: { FBXHeaderVersion: 1003\n FBXVersion: 7400 }\n"
            "Objects: {\n Geometry: 1, \"Geometry::MockCube\", \"Mesh\" {\n"
            f"Vertices: *24 {{ a: {vertices} }}\n"
            f"PolygonVertexIndex: *24 {{ a: {indices} }}\n"
            "}\n Model: 2, \"Model::MockCube\", \"Mesh\" { Version: 232 }\n}\n"
            "Connections: { C: \"OO\",1,2\n C: \"OO\",2,0\n}\n").encode()


@lru_cache(maxsize=1)
def mock_glb():
    # Triangles exist only in the derived browser preview, never the original FBX.
    positions = struct.pack("<24f", *(n for vertex in VERTICES for n in vertex))
    triangles = [n for a, b, c, d in QUADS for n in (a, b, c, a, c, d)]
    indices = struct.pack("<36H", *triangles)
    binary = positions + indices
    document = {"asset": {"version": "2.0", "generator": "Mock load test"},
                "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
                "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
                "buffers": [{"byteLength": len(binary)}],
                "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(positions), "target": 34962},
                                {"buffer": 0, "byteOffset": len(positions), "byteLength": len(indices), "target": 34963}],
                "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
                               "min": [-1, -1, -1], "max": [1, 1, 1]},
                              {"bufferView": 1, "componentType": 5123, "count": 36, "type": "SCALAR"}]}
    encoded = json.dumps(document).encode()
    encoded += b" " * (-len(encoded) % 4)
    return (struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(encoded) + 8 + len(binary))
            + struct.pack("<I4s", len(encoded), b"JSON") + encoded
            + struct.pack("<I4s", len(binary), b"BIN\x00") + binary)


class MockTripo:
    model = "mock-local-quad-cube"
    is_p2 = True
    is_mock = True

    def __init__(self, settings):
        self.settings = settings
        self.pending = {}  # Entries are removed after successful local download.

    async def balance(self):
        return {"balance": 1000000, "frozen": 0, "mock": True}

    async def upload(self, image):
        await self.settings.wait()
        return "mock-file-" + secrets.token_hex(8)

    async def upload_model(self, path):
        return await self.upload(path.read_bytes())

    def new_task(self):
        if len(self.pending) >= 10000:
            raise ProviderError("Mock 待处理任务达到上限，请降低并发。")
        task_id = "mock-task-" + secrets.token_hex(12)
        self.pending[task_id] = time.monotonic() + self.settings.delay_ms / 1000
        return task_id

    async def submit(self, token, *, face_limit, quad):
        if quad is not True or not 48 <= face_limit <= 25000:
            raise ValueError("Mock 也必须保持 quad=true 和合法面数目标")
        if isinstance(token, list) and (len(token) != 4 or not all(token)):
            raise ValueError("Mock 多视图也需要完整四张输入")
        await self.settings.wait()
        return self.new_task()

    async def texture(self, model_input, tokens):
        if len(tokens) != 4 or not all(tokens):
            raise ValueError("Mock 贴图需要四张部件参考图")
        await self.settings.wait()
        return self.new_task()

    async def task(self, task_id):
        if task_id not in self.pending:
            raise ProviderError("Mock 任务不存在或已结束；不会查询真实供应商。")
        ready = time.monotonic() >= self.pending[task_id]
        return {"status": "success" if ready else "running", "progress": 100 if ready else 50,
                "consumed_credit": 0, "output": {"mock_task_id": task_id}}

    async def download(self, output, path):
        if output.get("mock_task_id") not in self.pending:
            raise ProviderError("只允许下载本地 Mock 任务结果")
        path.write_bytes(mock_fbx())
        path.with_name(path.stem + "-preview.glb").write_bytes(mock_glb())
        self.pending.pop(output["mock_task_id"], None)

    def preview(self, path):
        return {"status": "ready", "file": path.stem + "-preview.glb", "mock": True,
                "topology": {"meshes": 1, "faces": 6, "quad_faces": 6,
                             "triangle_faces": 0, "other_faces": 0, "materials": 0}}
