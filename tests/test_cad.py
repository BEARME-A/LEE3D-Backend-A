"""
CAD smoke test. Skips cleanly if cadquery isn't installed (so it can live in CI
where the conda env has it, but won't explode in a bare checkout)."""
import tempfile, struct
from pathlib import Path

def _profile():
    from app.schemas import Profile
    return Profile(
        **{"schema": "lee3d.profile/v1"},
        name="test-car", length=180, stations=48, arcSegments=40,
        roofFlatness=1.4, wallThickness=1.8, archLift=1.0,
        topProfile=[[0,26],[0.5,58],[1,30]],
        bottomProfile=[[0,10],[0.5,7],[1,10]],
        widthProfile=[[0,14],[0.5,38],[1,18]],
        wheels=[{"x":-55,"z":13,"r":16,"width":26},{"x":55,"z":13,"r":16,"width":26}],
    )

def test_generate_stl():
    try:
        import cadquery  # noqa
    except Exception:
        print("cadquery not installed — skipping CAD test"); return
    from app.cad import generate_bytes
    from app.schemas import GenerateOptions
    data, mime, name = generate_bytes(_profile(), GenerateOptions(fmt="stl"))
    assert name.endswith(".stl") and len(data) > 84
    n = struct.unpack("<I", data[80:84])[0]
    assert len(data) == 84 + n * 50, "binary STL length must match triangle count"
    assert n > 100, "expected a non-trivial mesh"
    print(f"CAD STL OK: {n} triangles, {len(data)} bytes")

if __name__ == "__main__":
    test_generate_stl()
