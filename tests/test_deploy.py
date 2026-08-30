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


def test_the_exact_build_hollows_when_the_studio_says_hollow():
    """The studio and the backend have to mean the same thing by "hollow".

    They didn't. The planner read sepBottom — which is about whether the underside is a
    separate printed piece — while the studio expresses hollowing with hullHollow and sends
    sepBottom true on every frame. So the exact build came back SOLID every time, silently,
    next to a preview that was a thin shell. For a 200mm car that is roughly a litre of
    material instead of ninety-odd cc.
    """
    from app.hull import plan

    base = {
        "length": 200.0,
        "topProfile": [[0, 80]], "bottomProfile": [[0, 0]], "widthProfile": [[0, 30]],
        "sidePoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "topPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "frontPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "wallThickness": 6.3,
        "sepBottom": True,          # what the studio really sends, on every frame
    }

    assert plan({**base, "hullHollow": True})["hollow"] is True, \
        "a hollow frame must plan as hollow even with sepBottom set"
    assert plan({**base, "hullHollow": False})["hollow"] is False, \
        "and a solid one must not"
    assert plan({**base, "hullHollow": True, "wallThickness": 0})["hollow"] is False, \
        "no wall means nothing to hollow"

    # profiles saved before hullHollow existed still read correctly
    legacy = {k: v for k, v in base.items()}
    assert plan({**legacy, "sepBottom": False})["hollow"] is True
    assert plan({**legacy, "sepBottom": True})["hollow"] is False


def test_the_exact_build_is_given_the_traced_shape():
    """/solid takes the profile as a raw dict on purpose, so the traced outlines and the
    features reach the planner. If it were ever narrowed to the older Profile model the
    shape and every feature would be dropped without an error."""
    from app.hull import plan

    tri = [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]
    p = plan({
        "length": 100.0,
        "topProfile": [[0, 50]], "bottomProfile": [[0, 0]], "widthProfile": [[0, 20]],
        "sidePoly": tri, "topPoly": tri, "frontPoly": tri,
        "wallThickness": 2.0, "hullHollow": True,
        "features": [{"view": "side", "poly": [[0.3, 0.3], [0.6, 0.3], [0.6, 0.6], [0.3, 0.6]],
                      "depth": -3.0, "through": True, "name": "vent"}],
    })
    assert p["outlines"]["side"], "the traced side outline has to arrive"
    assert p["dims"]["length"] == 100.0
    assert [f["name"] for f in p["through_cuts"]] == ["vent"], \
        "a cut-through feature must plan as a real hole"


def test_the_endpoint_hollows_by_default_when_the_profile_says_so(monkeypatch):
    """The studio sends no hollow flag, so the endpoint has to take the profile's word for
    it. It used to default to solid, which is how a hollow frame came back as a lump."""
    import json
    from fastapi.testclient import TestClient
    from app.main import app

    prof = {
        "name": "t", "length": 120.0,
        "topProfile": [[0, 60]], "bottomProfile": [[0, 0]], "widthProfile": [[0, 25]],
        "sidePoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "topPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "frontPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "wallThickness": 3.0, "hullHollow": True, "sepBottom": True,
    }
    c = TestClient(app)
    r = c.post("/solid?plan_only=true", json=prof)
    assert r.status_code == 200, r.text
    assert r.json()["hollow"] is True, "no flag sent, and the profile asked for a shell"

    r2 = c.post("/solid?plan_only=true&hollow=false", json=prof)
    assert r2.json()["hollow"] is False, "an explicit flag still wins"

    r3 = c.post("/solid?plan_only=true", json={**prof, "hullHollow": False})
    assert r3.json()["hollow"] is False, "and a solid profile stays solid"


def test_the_endpoint_says_when_it_could_not_actually_hollow(monkeypatch):
    """`plan()` says hollow:true because the profile ASKED for a shell. If the cavity cannot
    be built the exact build hands back a solid, and until now nothing on the wire said so —
    the studio would show "hollow" beside a STEP that is a solid lump.

    This is the header half of the fix, and it is deliberately in the FAST job: the geometry
    that makes a hollow fail is checked in `test_hull.py` under the kernel, but the wiring
    from report -> header must never be able to rot unnoticed while OpenCascade is absent.
    That is the whole lesson of the kernel tests that lay dormant for a year.
    """
    from fastapi.testclient import TestClient
    from app import hull
    from app.main import app

    prof = {
        "name": "t", "length": 120.0,
        "topProfile": [[0, 60]], "bottomProfile": [[0, 0]], "widthProfile": [[0, 25]],
        "sidePoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "topPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "frontPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "wallThickness": 3.0, "hullHollow": True, "sepBottom": True,
    }

    def stub(failed):
        """A stand-in for the kernel that writes the report the real build would write."""
        def export(profile, fmt="step", hollow=False, report=None):
            if report is not None:
                report["hollow_failed"] = failed
                if failed:
                    report["hollow_failed_reason"] = "ValueError('the cavity came out empty')"
            return b"ISO-10303-21;", "application/step", "t.step"
        return export

    c = TestClient(app)

    monkeypatch.setattr(hull, "export_bytes", stub(True))
    r = c.post("/solid", json=prof)
    assert r.status_code == 200, r.text
    assert r.headers.get("X-LEE3D-Hollow-Failed") == "1", (
        "a shell was asked for and not built — the header has to say so, "
        f"got {dict(r.headers)!r}")

    monkeypatch.setattr(hull, "export_bytes", stub(False))
    r2 = c.post("/solid", json=prof)
    assert r2.headers.get("X-LEE3D-Hollow-Failed") == "0", "a working shell reports 0"

    # and a build that never asked for a shell must not report a failure either
    def never_asked(profile, fmt="step", hollow=False, report=None):
        return b"ISO-10303-21;", "application/step", "t.step"

    monkeypatch.setattr(hull, "export_bytes", never_asked)
    r3 = c.post("/solid", json={**prof, "hullHollow": False})
    assert r3.headers.get("X-LEE3D-Hollow-Failed") == "0", (
        "an absent report is not a failure — 0 covers both 'worked' and 'never asked'")
