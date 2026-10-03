import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_blender.py"


@pytest.mark.parametrize("saved_text", [False, True])
def test_export_script_resolves_blender_virtual_file(tmp_path, saved_text):
    package = tmp_path / "Jinx_blender"
    package.mkdir()
    (package / "manifest.json").write_text('{"models": [], "project_name": "Jinx"}')
    script = package / "import_blender.py"
    script.write_text("# saved text")
    scene = package / "Jinx.blend"
    scene.write_bytes(b"fixture")
    bpy = types.SimpleNamespace(
        context=types.SimpleNamespace(space_data=types.SimpleNamespace(
            text=types.SimpleNamespace(filepath=str(script) if saved_text else ""))),
        data=types.SimpleNamespace(filepath=str(scene)),
        path=types.SimpleNamespace(abspath=lambda value: value),
    )
    source = SCRIPT.read_text().split("collection =", 1)[0].replace("import bpy", "")
    state = {"bpy": bpy, "__file__": str(scene / "import_blender.py")}
    exec(compile(source, str(SCRIPT), "exec"), state)  # noqa: S102 -- repository script fixture
    assert state["root"] == package
    assert state["manifest"]["project_name"] == "Jinx"


def test_export_script_missing_package_has_clear_error(tmp_path):
    bpy = types.SimpleNamespace(
        context=types.SimpleNamespace(space_data=None),
        data=types.SimpleNamespace(filepath=""),
        path=types.SimpleNamespace(abspath=lambda value: value),
    )
    source = SCRIPT.read_text().split("collection =", 1)[0].replace("import bpy", "")
    with pytest.raises(RuntimeError, match="Cannot find manifest.json"):
        exec(compile(source, str(SCRIPT), "exec"), {"bpy": bpy, "__file__": str(tmp_path / "missing.py")})  # noqa: S102 -- repository script fixture
