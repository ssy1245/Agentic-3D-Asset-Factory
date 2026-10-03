import io
import math
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

from .models import Region
from .provider import ProviderError


class TripoProvider:
    base = "https://api.tripo3d.ai/v2/openapi"

    def __init__(self, key, model="v3.1-20260211", transport=None):
        self.key, self.model, self.transport = key, model, transport
        self.is_p2 = model == "P2-20260801"
        if self.is_p2:
            self.base = "https://openapi.tripo3d.ai/v3"

    async def request(self, method, path, **kwargs):
        try:
            async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
                response = await client.request(
                    method, self.base + path, headers={"Authorization": f"Bearer {self.key}"}, **kwargs
                )
            if response.status_code >= 400:
                messages = {
                    401: "Tripo 密钥无效。",
                    403: "Tripo 账号无访问权限。",
                    402: "Tripo API 积分不足。",
                    429: "Tripo 请求受限，请稍后核对。",
                }
                raise ProviderError(
                    messages.get(response.status_code, "Tripo 请求失败，请核对任务记录。"),
                    unknown=method == "POST" and response.status_code >= 500,
                )
            body = response.json()
            if body.get("code") != 0:
                raise ProviderError("Tripo 拒绝了请求，请检查 API 余额和参数。")
            return body["data"]
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError) as error:
            raise ProviderError(
                "Tripo 未返回可确认的结果，请核对任务记录。", unknown=method == "POST"
            ) from error

    async def balance(self):
        data = await self.request("GET", "/account/balance" if self.is_p2 else "/user/balance")
        return {"balance": data.get("balance", 0), "frozen": data.get("frozen", 0)}

    async def upload(self, png):
        data = await self.request(
            "POST", "/files" if self.is_p2 else "/upload", files={"file": ("reference.png", png, "image/png")}
        )
        token = data.get("file_token" if self.is_p2 else "image_token")
        if not token:
            raise ProviderError("Tripo 上传未返回图片编号。")
        return token

    async def submit(self, token, *, face_limit=50000, quad=True):
        if quad is not True:
            raise ValueError("本项目只允许生成四边形模型，不能关闭 quad")
        if isinstance(token, list) and (len(token) != 4 or not all(token)):
            raise ValueError("多视图需要完整的 front、left、back、right 四张输入")
        if self.is_p2:
            if not 48 <= face_limit <= 25000:
                raise ValueError("P2.0 四边形面数必须在 48–25,000 之间")
            images = (
                {
                    "inputs": [
                        {view: t} for view, t in zip(("front", "left", "back", "right"), token, strict=True)
                    ]
                }
                if isinstance(token, list)
                else {"input": token}
            )
            data = await self.request(
                "POST",
                "/generation/multiview-to-model" if isinstance(token, list) else "/generation/image-to-model",
                json={
                    "model": self.model,
                    **images,
                    "texture": False,
                    "pbr": False,
                    "export_uv": False,
                    "face_limit": face_limit,
                    "quad": True,
                },
            )
        else:
            images = (
                {"files": [{"type": "png", "file_token": t} for t in token]}
                if isinstance(token, list)
                else {"file": {"type": "png", "file_token": token}}
            )
            data = await self.request(
                "POST",
                "/task",
                json={
                    "type": "multiview_to_model" if isinstance(token, list) else "image_to_model",
                    "model_version": self.model,
                    **images,
                    "texture": False,
                    "pbr": False,
                    "export_uv": False,
                    "face_limit": face_limit,
                    "quad": quad,
                    "smart_low_poly": False,
                },
            )
        task_id = data.get("task_id")
        if not task_id:
            raise ProviderError("Tripo 创建任务后未返回编号，请核对记录。", unknown=True)
        return task_id

    async def upload_model(self, path):
        if not self.is_p2:
            raise ValueError("模型上传需要 v3 接口")
        data = await self.request(
            "POST", "/files", files={"file": (path.name, path.read_bytes(), "application/octet-stream")}
        )
        token = data.get("file_token")
        if not token:
            raise ProviderError("模型副本上传未返回文件编号。")
        return token

    async def texture(self, model_input, tokens):
        if not self.is_p2:
            raise ValueError("纹理生成需要 P2.0 的 v3 接口配置")
        if len(tokens) != 4 or not all(tokens):
            raise ValueError("纹理生成需要四张部件参考图")
        data = await self.request(
            "POST",
            "/models/texture",
            json={
                "input": model_input,
                "model": "v3.5-20260815",
                "texture_prompt": {"images": [{"file_token": t} for t in tokens]},
                "texture_quality": "detailed",
                "pbr": True,
                "texture_alignment": "original_image",
                "quad": True,
            },
        )
        if not data.get("task_id"):
            raise ProviderError("纹理任务未返回编号，请核对记录。", unknown=True)
        return data["task_id"]

    async def task(self, task_id):
        return await self.request("GET", ("/tasks/" if self.is_p2 else "/task/") + task_id)

    async def download(self, output, path: Path):
        url = output.get("base_model") or output.get("model") or output.get("model_url")
        if isinstance(url, dict):
            url = url.get("url")
        if not isinstance(url, str) or urlparse(url).scheme != "https":
            raise ProviderError("Tripo 没有返回有效的模型下载地址。")
        # Download signed output without forwarding the API credential.
        temporary = path.with_suffix(".partial")
        try:
            size = 0
            async with (
                httpx.AsyncClient(timeout=120, transport=self.transport, follow_redirects=True) as client,
                client.stream("GET", url) as response,
            ):
                response.raise_for_status()
                with temporary.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 100 * 1024 * 1024:
                            raise ProviderError("模型超过当前 100 MB 下载上限。")
                        file.write(chunk)
            with temporary.open("rb") as file:
                header = file.read(64)
            if path.suffix.lower() == ".fbx":
                if not (
                    header.startswith(b"Kaydara FBX Binary  \x00\x1a\x00")
                    or header.lstrip().startswith(b"; FBX")
                ):
                    raise ProviderError("下载结果不是有效的 FBX 文件，请核对 Tripo 输出。")
            elif (
                len(header) < 12
                or header[:4] != b"glTF"
                or int.from_bytes(header[4:8], "little") != 2
                or int.from_bytes(header[8:12], "little") != size
            ):
                raise ProviderError("下载结果不是有效的 GLB 文件头，请核对 Tripo 输出。")
            temporary.replace(path)
        except httpx.HTTPError as error:
            raise ProviderError("模型下载失败，可以再次查询原任务下载；不要重新生成。") from error
        finally:
            temporary.unlink(missing_ok=True)


def crop_reference(image: bytes, crop: Region) -> bytes:
    with Image.open(io.BytesIO(image)) as source:
        w, h = source.size
        bounds = (
            int(crop.x * w),
            int(crop.y * h),
            min(w, math.ceil((crop.x + crop.width) * w)),
            min(h, math.ceil((crop.y + crop.height) * h)),
        )
        if bounds[2] - bounds[0] < 32 or bounds[3] - bounds[1] < 32:
            raise ValueError("请框选至少 32×32 像素的完整正面部件")
        cropped = source.crop(bounds).convert("RGBA")
        out = io.BytesIO()
        cropped.save(out, format="PNG")
        return out.getvalue()
