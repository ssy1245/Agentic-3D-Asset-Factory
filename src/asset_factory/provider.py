import base64
import io
import json
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageOps

from .models import BrushStroke, Region


class ProviderError(Exception):
    def __init__(self, message, unknown=False, request_id=None):
        super().__init__(message)
        self.unknown = unknown
        self.request_id = request_id


@dataclass
class Result:
    image: bytes
    usage: dict | None
    request_id: str | None
    model: str


def normalize_image(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError("只支持 PNG、JPEG、WebP")
            if image.width * image.height > 20_000_000:
                raise ValueError("图片不能超过两千万像素")
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGBA")
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("图片文件无法读取") from error


def region_mask(image: bytes, region: Region) -> bytes:
    with Image.open(io.BytesIO(image)) as source:
        w, h = source.size
    mask = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    ImageDraw.Draw(mask).rectangle(
        (
            int(region.x * w),
            int(region.y * h),
            min(w - 1, int((region.x + region.width) * w)),
            min(h - 1, int((region.y + region.height) * h)),
        ),
        fill=(255, 255, 255, 0),
    )
    out = io.BytesIO()
    mask.save(out, format="PNG")
    return out.getvalue()


def annotated_reference(image: bytes, strokes: list[BrushStroke]) -> bytes:
    """Create a visual instruction; never overwrite the clean source image."""
    with Image.open(io.BytesIO(image)) as source:
        overlay = source.convert("RGBA")
    w, h = overlay.size
    draw = ImageDraw.Draw(overlay)
    for stroke in strokes:
        points = [(round(p.x * (w - 1)), round(p.y * (h - 1))) for p in stroke.points]
        width = max(2, round(stroke.width * min(w, h)))
        color = (239, 68, 68, 255)
        if len(points) > 1:
            draw.line(points, fill=color, width=width, joint="curve")
        for x, y in (points[0], points[-1]):
            radius = width / 2
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    out = io.BytesIO()
    overlay.save(out, format="PNG")
    return out.getvalue()


class DemoProvider:
    def __init__(self, fixtures: Path):
        self.fixtures = fixtures

    async def generate(self, stage, prompt, references, region=None):
        # Fixture playback only: deliberately no simulated AI edit.
        image = references[0] if region else (self.fixtures / f"{stage}.png").read_bytes()
        return Result(normalize_image(image), None, None, "local-fixture-no-generation")


class OpenAIProvider:
    def __init__(self, key, model, transport=None):
        self.key = key
        self.model = model
        self.transport = transport

    async def generate(self, stage, prompt, references, region=None):
        headers = {"Authorization": f"Bearer {self.key}"}
        request_id = None
        # No automatic retry: an image request can incur cost even on timeout.
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(300, connect=15), transport=self.transport
            ) as client:
                params = {
                    "model": self.model,
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1536",
                    "quality": "medium",
                    "output_format": "png",
                }
                if references:
                    files = [
                        ("image[]", (f"reference-{i}.png", image, "image/png"))
                        for i, image in enumerate(references)
                    ]
                    if region:
                        files.append(("mask", ("mask.png", region_mask(references[0], region), "image/png")))
                    response = await client.post(
                        "https://api.openai.com/v1/images/edits", headers=headers, data=params, files=files
                    )
                else:
                    response = await client.post(
                        "https://api.openai.com/v1/images/generations", headers=headers, json=params
                    )
            request_id = response.headers.get("x-request-id")
            if response.status_code >= 400:
                # Never return raw vendor errors which may contain request data or credentials.
                messages = {
                    401: "API 密钥无效，请检查服务端配置。",
                    403: "账号没有图片模型访问权限。",
                    429: "调用受限或余额不足，请检查账号。",
                    400: "图片请求参数或内容不被接受，请检查模型和输入。",
                }
                raise ProviderError(
                    messages.get(response.status_code, "图片服务返回错误，请核对调用记录。"),
                    unknown=response.status_code >= 500,
                    request_id=request_id,
                )
            body = response.json()
            data = base64.b64decode(body["data"][0]["b64_json"], validate=True)
            return Result(normalize_image(data), body.get("usage"), request_id, self.model)
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as error:
            raise ProviderError(
                "未取得可确认的图片结果，扣费可能已发生。请核对供应商记录后再继续。",
                unknown=True,
                request_id=request_id,
            ) from error
