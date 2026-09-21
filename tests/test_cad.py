"""
CAD smoke test. Skips cleanly if cadquery isn't installed (so it can live in CI
where the conda env has it, but won't explode in a bare checkout)."""
import tempfile, struct
import pytest
from pathlib import Path

def _profile(stations: int = 48, arc: int = 40):
    from app.schemas import Profile
    return Profile(
        **{"schema": "lee3d.profile/v1"},
        name="test-car", length=180, stations=stations, arcSegments=arc,
        roofFlatness=1.4, wallThickness=1.8, archLift=1.0,
        topProfile=[[0,26],[0.5,58],[1,30]],
        bottomProfile=[[0,10],[0.5,7],[1,10]],
        widthProfile=[[0,14],[0.5,38],[1,18]],
        wheels=[{"x":-55,"z":13,"r":16,"width":26},{"x":55,"z":13,"r":16,"width":26}],
    )

def test_generate_stl_fast():
    """The same path as the full test below, at a resolution that can actually be RUN.

    The full profile takes about 290s — one `generate_bytes` call, nothing to split — which
    exceeds a tool-call limit, so `app/cad.py` was never exercised outside CI. Measured after a
    3.5s OpenCascade warmup:

        stations 12 arc 10   ->    864 tris in   3.0s
        stations 16 arc 12   ->   1178 tris in  10.5s
        stations 24 arc 16   ->   1372 tris in  28.5s
        stations 48 arc 40   ->  did not finish in 275s   <- the full test

    Growth is steeply superlinear, so a modest reduction buys a great deal of time. This
    version catches an STL path that is broken outright; the full one below still guards
    resolution-dependent failures in CI.
    """
    pytest.importorskip("cadquery", reason="needs OpenCascade")
    from app.cad import generate_bytes
    from app.schemas import GenerateOptions
    data, mime, name = generate_bytes(_profile(stations=16, arc=12), GenerateOptions(fmt="stl"))
    assert name.endswith(".stl") and len(data) > 84
    n = struct.unpack("<I", data[80:84])[0]
    assert len(data) == 84 + n * 50, "binary STL length must match triangle count"
    assert n > 100, "expected a non-trivial mesh"


def test_generate_stl_full_resolution():
    """RENAMED so it does not PREFIX the fast one. `--deselect ...::test_generate_stl` matches
    node ids by prefix, so excluding the slow test also excluded `test_generate_stl_fast` —
    the suite reported "2 deselected" and the fast test silently did not run, which is exactly
    the kind of quiet non-execution this file has now been bitten by twice."""
    # A BARE `return` HERE REPORTED AS A PASS. Without cadquery this test printed a line and
    # returned, so the summary counted it green while nothing had been built — the same way a
    # skip reads as a pass in a summary line. `importorskip` says what actually happened.
    pytest.importorskip("cadquery", reason="needs OpenCascade")
    from app.cad import generate_bytes
    from app.schemas import GenerateOptions
    data, mime, name = generate_bytes(_profile(), GenerateOptions(fmt="stl"))
    assert name.endswith(".stl") and len(data) > 84
    n = struct.unpack("<I", data[80:84])[0]
    assert len(data) == 84 + n * 50, "binary STL length must match triangle count"
    assert n > 100, "expected a non-trivial mesh"
    print(f"CAD STL OK: {n} triangles, {len(data)} bytes")

if __name__ == "__main__":
    test_generate_stl_full_resolution()
