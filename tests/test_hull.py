"""
Tests for the exact (OpenCascade) build.

The geometry prep is deliberately kept free of CadQuery so it can be tested anywhere —
including CI on the light image, which is where regressions would otherwise hide until
someone actually asked for a STEP file. The kernel-dependent bits are skipped, not faked.
"""
import pytest

from app import hull


PROFILE = {
    "name": "lambo",
    "length": 190,
    "topProfile": [[0, 10], [0.5, 60], [1, 20]],
    "widthProfile": [[0, 10], [0.5, 40], [1, 16]],
    "sidePoly": [[0.05, 0.1], [0.9, 0.1], [0.9, 0.8], [0.05, 0.8]],
    "topPoly": [[0.05, 0.1], [0.9, 0.1], [0.9, 0.9], [0.05, 0.9]],
    "frontPoly": [[0.1, 0.05], [0.9, 0.05], [0.9, 0.85], [0.1, 0.85]],
    "wallThickness": 1.8,
    "features": [
        {"kind": "poly", "view": "side", "name": "window", "depth": -3, "through": True,
         "poly": [[0.3, 0.4], [0.6, 0.4], [0.6, 0.7], [0.3, 0.7]]},
        {"kind": "poly", "view": "side", "name": "mirror", "depth": 2,
         "poly": [[0.1, 0.2], [0.2, 0.2], [0.2, 0.3], [0.1, 0.3]]},
        {"kind": "text", "view": "side", "name": "badge", "depth": -1,
         "box": [0.1, 0.1, 0.3, 0.2]},
    ],
}


def test_dims_read_the_same_way_the_studio_does():
    L, W, H = hull.dims(PROFILE)
    assert L == 190
    assert W == 80          # widthProfile holds HALF widths
    assert H == 60


def test_dims_fall_back_sanely_on_an_empty_profile():
    L, W, H = hull.dims({})
    assert L > 0 and W > 0 and H > 0


def test_outlines_land_in_millimetres_on_the_right_planes():
    o = hull.outlines_mm(PROFILE)
    # side: (x , z) spanning length x height
    xs = [p[0] for p in o["side"]]
    zs = [p[1] for p in o["side"]]
    assert min(xs) == pytest.approx(0.05 * 190)
    assert max(zs) == pytest.approx(0.8 * 60)
    # top: (x , y) with the width centred on zero, like the model
    ys = [p[1] for p in o["top"]]
    assert min(ys) == pytest.approx(0.1 * 80 - 40)
    assert max(ys) == pytest.approx(0.9 * 80 - 40)
    # front: (y , z)
    fy = [p[0] for p in o["front"]]
    assert min(fy) == pytest.approx(0.1 * 80 - 40)


def test_a_missing_outline_becomes_a_plain_box_rather_than_an_error():
    o = hull.outlines_mm({"length": 100, "topProfile": [[0, 50]], "widthProfile": [[0, 20]]})
    assert len(o["side"]) == 4 and len(o["top"]) == 4 and len(o["front"]) == 4


def test_only_through_features_become_real_cuts():
    p = hull.plan(PROFILE)
    assert [f["name"] for f in p["through_cuts"]] == ["window"]
    # a raised mirror is a surface effect, and text has no outline to extrude
    assert "mirror" in [f["name"] for f in p["surface_only"]]
    assert "badge" not in [f["name"] for f in p["through_cuts"]]


def test_a_positive_depth_never_becomes_a_hole():
    prof = dict(PROFILE)
    prof["features"] = [{"kind": "poly", "view": "side", "name": "boss", "depth": 3, "through": True,
                         "poly": [[0.3, 0.4], [0.6, 0.4], [0.6, 0.7], [0.3, 0.7]]}]
    p = hull.plan(prof)
    assert p["through_cuts"] == [], "a raised feature must never be cut out"


def test_rear_features_are_mirrored_like_the_studio_shows_them():
    prof = dict(PROFILE)
    prof["features"] = [{"kind": "poly", "view": "rear", "name": "vent", "depth": -2, "through": True,
                         "poly": [[0.1, 0.2], [0.3, 0.2], [0.3, 0.5], [0.1, 0.5]]}]
    f = hull.plan(prof)["through_cuts"][0]
    ys = [p[0] for p in f["pts"]]
    # traced from behind, so it has to be flipped to land on the correct side
    assert max(ys) > 0, "a rear feature should mirror across the centreline"


def test_junk_points_are_cleaned_rather_than_crashing():
    prof = dict(PROFILE)
    prof["sidePoly"] = [[0.1, 0.1], [0.1, 0.1], ["x", 2], [0.9, 0.1], None, [0.9, 0.8], [0.1, 0.1]]
    o = hull.outlines_mm(prof)
    assert len(o["side"]) >= 3
    # the repeated closing point is dropped; the extruder closes the wire itself
    assert o["side"][0] != o["side"][-1]


def test_a_degenerate_outline_falls_back_to_a_box():
    prof = dict(PROFILE)
    prof["sidePoly"] = [[0.1, 0.1], [0.2, 0.2]]        # only two points: not a shape
    assert len(hull.outlines_mm(prof)["side"]) == 4


def test_poly_area_is_winding_independent():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert hull.poly_area(sq) == pytest.approx(100)
    assert hull.poly_area(list(reversed(sq))) == pytest.approx(100)


def test_the_plan_works_without_opencascade_installed():
    # this is the whole point of splitting prep from the kernel: CI on the light image
    # still checks the wiring
    p = hull.plan(PROFILE)
    assert p["dims"]["length"] == 190
    assert "outlines" in p


def test_asking_for_an_exact_build_without_the_kernel_says_so_clearly():
    pytest.importorskip  # noqa
    try:
        import cadquery  # noqa: F401
        pytest.skip("OpenCascade is installed here; the clean-error path can't be checked")
    except Exception:
        pass
    with pytest.raises(hull.CadUnavailable) as e:
        hull.build_solid(PROFILE)
    assert "Dockerfile.full" in str(e.value), "the error should say how to fix it"


@pytest.mark.skipif("cadquery" not in [m for m in __import__("sys").modules] and True, reason="needs OpenCascade")
def test_exact_build_when_the_kernel_is_present():  # pragma: no cover - full image only
    cq = pytest.importorskip("cadquery")
    solid = hull.build_solid(PROFILE)
    assert solid.solids().vals(), "the three outlines should intersect into a solid"
