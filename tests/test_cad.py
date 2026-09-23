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


def _stl_extent(data: bytes):
    """Triangle count and bounding-box extent of a binary STL, read straight out of the bytes."""
    n = struct.unpack("<I", data[80:84])[0]
    lo = [1e9] * 3
    hi = [-1e9] * 3
    off = 84
    for _ in range(n):
        for v in range(3):
            pt = struct.unpack_from("<3f", data, off + 12 + v * 12)
            for k, c in enumerate(pt):
                lo[k] = min(lo[k], c)
                hi[k] = max(hi[k], c)
        off += 50
    return n, [hi[k] - lo[k] for k in range(3)]


def test_the_stl_envelope_does_not_move_with_resolution():
    """THE INVARIANT THE FULL-RESOLUTION TEST CANNOT CHECK, because it runs one resolution.

    `test_generate_stl_fast` proves the STL path is not broken outright; the full test guards
    resolution-dependent failures but takes ~290s and has never run against the current
    `hull.py` outside CI. Between them sits the thing this project actually protects: **the
    outside of the part must not depend on how finely it was built.** This file has a whole
    section on an auto-raise being removed because merely ticking `hollow` moved the outside by
    half a millimetre, and another on a fix rejected for pulling the width in 0.6mm.

    Two resolutions, both runnable here. Measured (after a discarded warmup — timing anything
    on OpenCascade's first call reads 35s instead of 10):

        stations 16 arc 12   1178 tris    9.6s   180.000 x 76.005 x 51.002
        stations 24 arc 16   1372 tris   25.1s   180.000 x 76.004 x 51.001

    They agree to 0.001mm on a 180mm body. The tolerance below is 0.01mm — ten times the
    measured disagreement, and still four hundred times tighter than anything that would print
    differently. Arc segmentation legitimately moves a curved surface by its chord height, so
    this is checked on the ENVELOPE, where the extremes are set by the profiles rather than by
    the arcs, and not on the triangle positions.
    """
    pytest.importorskip("cadquery", reason="needs OpenCascade")
    from app.cad import generate_bytes
    from app.schemas import GenerateOptions

    coarse, _, _ = generate_bytes(_profile(stations=16, arc=12), GenerateOptions(fmt="stl"))
    finer, _, _ = generate_bytes(_profile(stations=24, arc=16), GenerateOptions(fmt="stl"))
    n_coarse, ext_coarse = _stl_extent(coarse)
    n_finer, ext_finer = _stl_extent(finer)

    assert n_finer > n_coarse, (
        "a finer build must produce more triangles, or the resolution knob did nothing and "
        "this test is comparing a body with itself")
    for axis, a, b in zip("xyz", ext_coarse, ext_finer):
        assert abs(a - b) <= 0.01, (
            f"{axis} extent moved {abs(a - b):.4f}mm between stations 16/arc 12 and 24/16 "
            f"({a:.4f} vs {b:.4f}). The outside of the part may not depend on how finely it "
            f"was built — that is the invariant every hollowing change here is measured against.")
    assert ext_coarse[0] == pytest.approx(180.0, abs=0.01), (
        "and the length has to be the length that was asked for, not merely self-consistent")
