"""
Tests for the deploy config.

These exist because the blueprint failed on Render for a reason that was invisible from
the code: a free-tier service may not ask for a persistent disk. That's the kind of
mistake you only find by pasting the repo in and reading an error, which is a slow and
annoying way to find out. Now it's a test.
"""
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "render.yaml"


@pytest.fixture(scope="module")
def svc():
    if not BLUEPRINT.exists():
        pytest.skip("render.yaml isn't in this checkout")
    data = yaml.safe_load(BLUEPRINT.read_text())
    assert data.get("services"), "a blueprint needs at least one service"
    return data["services"][0]


def test_free_tier_never_asks_for_a_disk(svc):
    # Render: "disks are not supported for free tier services" — the blueprint is rejected
    # outright, so this is a hard rule, not a preference.
    if svc.get("plan") == "free":
        assert "disk" not in svc, (
            "a free service cannot have a disk. Nothing here needs one: the only thing it "
            "held was a SQLite cache, and every real model lives in Supabase or LEE3D-Lib."
        )


def test_the_data_dir_is_somewhere_always_writable(svc):
    env = {e["key"]: e.get("value") for e in svc.get("envVars", [])}
    d = env.get("LEE3D_DATA_DIR")
    assert d, "set LEE3D_DATA_DIR explicitly so it can't land somewhere read-only"
    if svc.get("plan") == "free":
        assert d.startswith("/tmp"), "with no disk, the cache belongs in /tmp"


def test_it_defaults_to_the_image_that_actually_fits(svc):
    # The full CAD image is multi-GB and will not run on the free tier. Defaulting to it
    # would mean everyone's first deploy fails for a reason the error won't explain.
    path = svc.get("dockerfilePath", "./Dockerfile")
    if svc.get("plan") == "free":
        assert "full" not in path.lower(), (
            "the OpenCascade image can't fit a free instance; keep ./Dockerfile as the "
            "default and switch deliberately"
        )


def test_health_check_points_at_a_route_that_exists(svc):
    assert svc.get("healthCheckPath") == "/health"
    main = (ROOT / "app" / "main.py").read_text()
    assert '"/health"' in main, "Render will restart the service forever if this 404s"


def test_the_token_is_never_committed(svc):
    env = {e["key"]: e for e in svc.get("envVars", [])}
    tok = env.get("LEE3D_GITHUB_TOKEN")
    assert tok is not None, "the library publish path needs a token on the server"
    assert tok.get("sync") is False, "sync:false = Render prompts for it; a value would be in git"
    assert "value" not in tok, "a real token must never appear in the blueprint"


def test_the_deployed_studio_is_allowed_to_call_it(svc):
    env = {e["key"]: e.get("value") for e in svc.get("envVars", [])}
    origins = env.get("LEE3D_CORS_ORIGINS", "")
    assert "github.io" in origins, "the Pages studio would be blocked by CORS without this"


def test_the_dockerfile_it_names_is_actually_in_the_repo(svc):
    # This is the one that bit. The blueprint said ./Dockerfile and the repo has only
    # Dockerfile.light and Dockerfile.full, so Render failed at BUILD — before any of the
    # app ran, with an error that says nothing about the real cause. The old version of
    # this test skipped a missing file instead of failing on it, so it sailed through.
    path = svc.get("dockerfilePath", "./Dockerfile")
    f = ROOT / path.lstrip("./")
    assert f.exists(), (
        f"render.yaml points at {path}, which isn't in this repo. Present: "
        + ", ".join(sorted(x.name for x in ROOT.glob("Dockerfile*")))
    )


def test_every_image_binds_to_the_platform_port():
    # Render sets $PORT; a container that hard-codes 8000 fails its health check and gets
    # restarted forever, which looks like a mystery rather than a config error.
    found = sorted(ROOT.glob("Dockerfile*"))
    assert found, "the repo needs at least one image to deploy"
    for f in found:
        assert "PORT" in f.read_text(), f"{f.name} must honour ${{PORT}}, not hard-code a port"
