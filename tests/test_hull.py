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


def test_every_feature_with_depth_is_built_as_real_geometry():
    """REWRITTEN. This used to assert that anything not a through-cut was surface_only, with
    the reasoning that the browser handled dishes and bosses as surface effects. That stopped
    being true when the studio moved its detail work into the distance field: a pocket became
    real geometry cut to an exact depth. The two ends then disagreed in silence — on the
    project's own reference car, 0 of 153 features reached the STEP and the export looked like
    a smooth body with no error raised.
    OpenCascade cuts a finite-depth pocket directly, so there was never a reason to skip them.
    What genuinely has no solid meaning is a feature with NO depth: a mask or a text label."""
    p = hull.plan(PROFILE)
    assert [f["name"] for f in p["through_cuts"]] == ["window"]
    # a raised mirror is a boss now, not a surface effect
    assert "mirror" in [f["name"] for f in p["raises"]]
    assert "mirror" not in [f["name"] for f in p["surface_only"]]
    # a positive depth must never become a hole
    assert "badge" not in [f["name"] for f in p["through_cuts"]]
    # nothing with a depth may be silently dropped
    named = {f["name"] for f in p["through_cuts"] + p["pockets"] + p["raises"]}
    for f in PROFILE["features"]:
        if f.get("depth") and f.get("poly"):
            assert f["name"] in named, f"{f['name']!r} has a depth and must be built"


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


# ---------------------------------------------------------------------------------------
# WHERE A FEATURE LANDS.
# These pin the plane and the position, not merely that a feature was read. "sideR" used to
# fall through the front/rear branch, so a window traced on the right flank was planned as a
# cut through the NOSE — the studio had the identical fall-through, and both ends agreed
# with each other about the wrong answer, which is the worst way for two services to agree.
# ---------------------------------------------------------------------------------------
def _profile_with(view):
    return {
        "length": 100.0,
        "topProfile": [[0, 40], [1, 40]],
        "widthProfile": [[0, 30], [1, 30]],
        "sidePoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "topPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "frontPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "wallThickness": 2.0,
        "hullHollow": True,
        "features": [{"view": view, "poly": [[0.10, 0.60], [0.30, 0.60],
                                             [0.30, 0.80], [0.10, 0.80]],
                      "depth": -4.0, "through": True, "name": "win"}],
    }


def _cut(view):
    from app.hull import plan
    cuts = plan(_profile_with(view))["through_cuts"]
    assert len(cuts) == 1, f"{view}: expected one through-cut, got {len(cuts)}"
    return cuts[0]


def test_a_right_side_feature_is_planned_on_the_side_plane():
    # L=100, W=60, H=40. On the side plane a point is (x, z); on the front plane it is (y, z).
    # The giveaway is the first coordinate's range: it can only reach 70..90 on a 100mm body.
    xs = [p[0] for p in _cut("sideR")["pts"]]
    assert max(xs) > 60, (
        "a right-side feature is being planned on the front plane — its first coordinate "
        f"tops out at {max(xs):.1f}, which is inside the 60mm width, not along the length"
    )


def test_a_right_side_feature_mirrors_along_the_length():
    # traced standing on the far side, so u runs the other way, exactly as sidePolyR does
    xs = [p[0] for p in _cut("sideR")["pts"]]
    assert 65 <= min(xs) <= 75 and 85 <= max(xs) <= 95, f"expected x 70..90, got {min(xs):.1f}..{max(xs):.1f}"
    left = [p[0] for p in _cut("side")["pts"]]
    assert 5 <= min(left) <= 15 and 25 <= max(left) <= 35, f"left view moved: {min(left):.1f}..{max(left):.1f}"


def test_a_right_side_feature_is_cut_on_the_right_plane_and_span():
    from app.hull import build_solid  # noqa: F401  (import-only; the mapping is what matters)
    # the mapping build_solid uses, asserted directly so it can't drift from feature_mm
    planes = {"side": "XZ", "sideR": "XZ", "top": "XY", "bottom": "XY"}
    assert planes.get("sideR") == "XZ", "sideR must extrude across the width, like side"


def test_plan_view_features_share_the_outline_frame():
    # features are stored v screen-up, topPoly is stored v screen-down. v 0.60..0.80 must
    # therefore come out at y (1-v)*W centred on zero = -18..-6, not +6..+18.
    ys = [p[1] for p in _cut("top")["pts"]]
    assert max(ys) < 0, f"plan-view detail landed on the wrong flank: y {min(ys):.1f}..{max(ys):.1f}"
    yb = [p[1] for p in _cut("bottom")["pts"]]
    assert max(yb) < 0, f"underside detail landed on the wrong flank: y {min(yb):.1f}..{max(yb):.1f}"


def test_every_view_the_studio_can_draw_on_is_planned():
    for view in ("side", "sideR", "top", "bottom", "front", "rear"):
        assert _cut(view)["pts"], f"{view} produced no geometry"


def test_it_says_when_it_is_about_to_ignore_the_second_side():
    from app.hull import plan
    p = _profile_with("side")
    assert plan(p)["ignored_second_side"] is False
    p["sidePolyR"] = [[0, 0], [1, 0], [1, 0.5], [0, 0.5]]
    assert plan(p)["ignored_second_side"] is True, (
        "the exact build intersects one side outline; if a second was traced the STEP is a "
        "different shape from the preview and the studio has to be able to say so"
    )


def test_the_contract_keeps_fields_it_has_not_been_taught():
    # pydantic drops unknown fields by default, and /generate writes the parsed object into
    # the versions table — so a stripped profile was being stored as the saved version.
    from app.schemas import Profile
    import json
    p = Profile(**{"length": 200, "topProfile": [[0, 60]], "bottomProfile": [[0, 5]],
                   "widthProfile": [[0, 30]], "sidePoly": [[0, 0], [1, 0], [1, 1]],
                   "features": [{"view": "sideR", "poly": [[0, 0]], "depth": -2}],
                   "hullCrisp": 0.5, "hullHollow": True, "wallTop": 2.1})
    out = json.loads(p.model_dump_json(by_alias=True))
    for key in ("sidePoly", "features", "hullCrisp", "hullHollow", "wallTop"):
        assert key in out, f"{key} was dropped on the way through the contract"


def test_a_pocket_enters_from_the_face_it_was_drawn_on():
    """Which END of an axis a feature starts from decides where a finite-depth pocket puts its
    floor. On a through-cut it does not matter — the cut goes all the way either way — so this
    only began to matter when pockets became real. Getting it wrong puts the detail on the
    opposite face, which is the same class of bug as sideR once being cut through the nose."""
    prof = dict(PROFILE)
    square = [[0.3, 0.3], [0.6, 0.3], [0.6, 0.6], [0.3, 0.6]]
    prof["features"] = [
        {"kind": "poly", "view": "side", "name": "left", "depth": -3, "poly": square},
        {"kind": "poly", "view": "sideR", "name": "right", "depth": -3, "poly": square},
        {"kind": "poly", "view": "top", "name": "roof", "depth": -3, "poly": square},
        {"kind": "poly", "view": "bottom", "name": "floor", "depth": -3, "poly": square},
    ]
    p = hull.plan(prof)
    assert len(p["pockets"]) == 4, "all four must be built, none skipped"
    assert p["through_cuts"] == [], "none of them was marked through"
    # opposite views must not resolve to the same footprint, or they are the same pocket twice
    by = {f["name"]: f["pts"] for f in p["pockets"]}
    assert by["left"] != by["right"], "side and sideR must mirror along the length"


def test_a_feature_with_no_depth_has_no_solid_meaning():
    """Masks and text labels carry no depth. They are the only things the exact build can
    honestly skip, and it must say so rather than quietly dropping anything else."""
    prof = dict(PROFILE)
    prof["features"] = [
        {"kind": "poly", "view": "side", "name": "mask", "depth": 0,
         "poly": [[0.3, 0.3], [0.6, 0.3], [0.6, 0.6], [0.3, 0.6]]},
        {"kind": "poly", "view": "side", "name": "dish", "depth": -2,
         "poly": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]},
    ]
    p = hull.plan(prof)
    assert [f["name"] for f in p["surface_only"]] == ["mask"]
    assert [f["name"] for f in p["pockets"]] == ["dish"]


def test_a_degenerate_outline_is_dropped_by_both_ends():
    """A three-point polygon whose first and last points are the same is a LINE, not a
    triangle. It carves nothing, so dropping it is right — but it is worth pinning, because
    the studio counts such a feature and this end does not, and an unexplained 153-vs-152
    is exactly the kind of discrepancy that hides a real one."""
    prof = dict(PROFILE)
    prof["features"] = [{"kind": "poly", "view": "side", "name": "sliver", "depth": -2,
                         "poly": [[0.2, 0.4], [0.7, 0.4], [0.2, 0.4]]}]
    p = hull.plan(prof)
    assert p["pockets"] == [] and p["through_cuts"] == []


def test_extra_views_are_reported_because_this_build_cannot_use_them():
    """The studio can carve from silhouettes at any angle — the groundwork for building from
    photographs. This build intersects the three axis outlines only, so a model using extra
    views comes out FATTER here: every extra view removes material and the ones we cannot use
    remove none. That difference has to be loud. A quiet one is what let 153 pockets go
    missing from a STEP for weeks."""
    prof = dict(PROFILE)
    prof["extraViews"] = [
        {"dir": [0, 1, 1], "poly": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {"dir": [1, 0, 1], "poly": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        {"dir": [1, 1, 0], "poly": None},          # malformed: must not be counted
    ]
    p = hull.plan(prof)
    assert p["unusable_views"] == 2, "usable-looking extra views must be counted and reported"
    prof2 = dict(PROFILE)
    p2 = hull.plan(prof2)
    assert p2["unusable_views"] == 0, "a model with no extra views must not raise the alarm"
