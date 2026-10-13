import pytest


@pytest.fixture(autouse=True)
def registration_passes(monkeypatch):
    # Test-only allowlist; never depend on the developer's private .env.
    monkeypatch.setenv("STUDIO_REGISTRATION_PASSES", "test-registration-pass,second-test-pass")


@pytest.fixture(autouse=True)
def isolate_blender_workers(monkeypatch):
    # Workflow fixtures contain synthetic FBX data, not production model files.
    # Discovery must not launch an installed Blender during normal test runs.
    monkeypatch.setattr("asset_factory.model_preview.blender_binary", lambda: None)
    monkeypatch.setattr("asset_factory.blender_export.blender_binary", lambda: None)

    async def unexpected_worker(*args, **kwargs):
        pytest.fail("Unit tests must mock Blender workers; real subprocess launch blocked.")

    monkeypatch.setattr("asyncio.create_subprocess_exec", unexpected_worker)
