import asyncio

import pytest
from fastapi.testclient import TestClient
from test_studio import FakeProvider

from asset_factory.blender_export import build_blend
from asset_factory.model_preview import prepare_fbx_preview
from asset_factory.studio import create_app


def test_preview_preserves_original_without_real_blender(tmp_path):
    source = tmp_path / "model.fbx"
    original = b"synthetic FBX; never send this to installed Blender"
    source.write_bytes(original)
    result = asyncio.run(prepare_fbx_preview(source))
    assert result["status"] == "unavailable"
    assert source.read_bytes() == original
    assert not source.with_name("model-preview.glb").exists()


def test_export_requires_explicit_mock_in_unit_tests(tmp_path):
    with pytest.raises(RuntimeError, match="BLENDER_BINARY"):
        asyncio.run(build_blend([], tmp_path / "export", "test"))
    assert not (tmp_path / "export").exists()


def test_opening_app_and_static_files_never_starts_blender(tmp_path):
    # The autouse subprocess guard fails immediately if app startup spawns a worker.
    with TestClient(create_app(tmp_path, {"demo": FakeProvider()})) as client:
        assert client.get("/").status_code == 200
        assert client.get("/static/models.js").status_code == 200
        assert client.get("/api/auth/me").status_code == 401

