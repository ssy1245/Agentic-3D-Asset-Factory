"""Export saved assets as a real, portable .blend without vendor calls."""
import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from .model_preview import blender_binary


async def build_blend(models, destination, project_name):
    binary = blender_binary()
    if not binary:
        raise RuntimeError("导出服务未找到 Blender,请配置 BLENDER_BINARY。")
    key = hashlib.sha256(json.dumps([
        "blend-export-v1", project_name,
        [(op["id"], path.stat().st_size, path.stat().st_mtime_ns) for op, path in models],
    ], ensure_ascii=False).encode()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / (key + ".blend")
    if output.is_file():
        return output
    script = Path(__file__).resolve().parents[2] / "scripts" / "export_blend.py"
    with tempfile.TemporaryDirectory(dir=destination) as folder:
        temporary = Path(folder) / "scene.blend"
        manifest = Path(folder) / "manifest.json"
        manifest.write_text(json.dumps({
            "project_name": project_name, "output": str(temporary.resolve()),
            "models": [{"path": str(path.resolve()), "part": op["stage"]} for op, path in models],
        }, ensure_ascii=False), encoding="utf-8")
        process = await asyncio.create_subprocess_exec(
            binary, "--background", "--factory-startup", "--disable-autoexec",
            "--python-exit-code", "1", "--python", str(script), "--", str(manifest.resolve()),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(process.wait(), 180)
        except (TimeoutError, asyncio.CancelledError):
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode or not temporary.is_file():
            raise RuntimeError("Blender 文件导出失败，原模型保留，请重试。")
        with temporary.open("rb") as file:
            if file.read(7) != b"BLENDER":
                raise RuntimeError("Blender 未生成有效文件。")
        temporary.replace(output)
    return output
