"""Keep quad FBX originals; convert only a separate browser preview with local Blender."""

import asyncio
import json
import os
import shutil
from pathlib import Path


def blender_binary():
    candidates = [os.getenv("BLENDER_BINARY", ""), shutil.which("blender") or ""]
    for root in (Path("/Applications"), Path.home() / "Applications"):
        candidates.extend(str(p) for p in root.glob("*lender*.app/Contents/MacOS/Blender"))
    candidates.extend(str(p) for p in (Path.home() / "Library/Application Support/Steam/steamapps/common").glob("*lender*/*.app/Contents/MacOS/Blender"))
    return next((p for p in candidates if p and Path(p).is_file()), None)


async def prepare_fbx_preview(source):
    binary = blender_binary()
    if not binary:
        return {
            "status": "unavailable",
            "reason": "未找到 Blender，原始四边形 FBX 已保留。可下载到 Blender 检查，或设置 BLENDER_BINARY 后重新准备预览。",
        }
    output = source.with_name(source.stem + "-preview.glb")
    metadata = source.with_name(source.stem + "-topology.json")
    script = Path(__file__).resolve().parents[2] / "scripts" / "prepare_model_preview.py"
    process = await asyncio.create_subprocess_exec(
        binary,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--python-exit-code",
        "1",
        "--python",
        str(script),
        "--",
        str(source),
        str(output),
        str(metadata),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.wait(), 180)
    except (TimeoutError, asyncio.CancelledError):
        process.kill()
        await process.wait()
        raise
    if process.returncode or not output.is_file() or not metadata.is_file():
        return {"status": "unavailable", "reason": "FBX 预览转换失败，原始四边形文件保留。"}
    return {"status": "ready", "file": output.name, "topology": json.loads(metadata.read_text())}
