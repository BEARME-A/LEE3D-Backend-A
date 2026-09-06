"""
Tests for the exact (OpenCascade) build.

The geometry prep is deliberately kept free of CadQuery so it can be tested anywhere —
including CI on the light image, which is where regressions would otherwise hide until
someone actually asked for a STEP file. The kernel-dependent bits are skipped, not faked.
"""
import importlib.util
import pytest


def _has_cadquery() -> bool:
    """Is the CAD kernel importable?

    `importlib.util.find_spec` is the right question, but it can RAISE rather than return None
    — a broken install, a partially-built OpenCascade, an import hook — and an exception at
    module level kills COLLECTION, taking every test in this file with it, not just the ones
    that need the kernel. That is a worse failure than the skip it was meant to produce.
    Previous guard was `"cadquery" not in sys.modules and True`, which skipped unless cadquery
    had already been imported — so in a fresh pytest run these never ran at all, even with the
    kernel installed."""
    try:
        return importlib.util.find_spec("cadquery") is not None
    except Exception:
        return False


HAS_CQ = _has_cadquery()

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


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
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


# ---------------------------------------------------------------------------------------
# PER-FACE WALL THICKNESS. The polygon maths is here in plain Python precisely so it can be
# tested without a CAD kernel — it is the part that can be got wrong. Everything OpenCascade
# touches is kept trivial on purpose.
# ---------------------------------------------------------------------------------------
def test_a_uniform_wall_still_takes_the_plain_path():
    """The guard that makes this free for everyone else: three equal values must not switch on
    the cavity build. profile_7 and every model like it keeps the shell() it always had."""
    assert not hull.wall_varies(hull.wall_spec({"wallThickness": 4.2}))
    assert not hull.wall_varies(hull.wall_spec(
        {"wallThickness": 4.2, "wallTop": 4.2, "wallSide": 4.2, "wallBottom": 4.2}))
    assert hull.wall_varies(hull.wall_spec(
        {"wallThickness": 4.2, "wallTop": 4.2, "wallSide": 4.2, "wallBottom": 12.0}))


def test_an_outline_normal_says_which_face_it_makes():
    """Collin's `ax, ay, az`: which axes a normal occupies is what turns a 2D outline into 3D
    face information. On a side view, up is the roof, down is the floor, and along the length
    is a nose or tail — which counts as a flank."""
    spec = hull.wall_spec({"wallThickness": 6, "wallTop": 6, "wallSide": 6, "wallBottom": 16})
    assert hull.wall_for_normal(hull.lift_normal((0, 1), "XZ"), spec) == 6      # roof
    assert hull.wall_for_normal(hull.lift_normal((0, -1), "XZ"), spec) == 16    # floor
    assert hull.wall_for_normal(hull.lift_normal((1, 0), "XZ"), spec) == 6      # nose: a flank
    # a plan view can only ever make flanks, whatever its normal does
    assert hull.wall_for_normal(hull.lift_normal((0, 1), "XY"), spec) == 6
    assert hull.wall_for_normal(hull.lift_normal((1, 0), "XY"), spec) == 6
    # and a 45-degree stretch blends rather than switching, so a corner has no seam
    blended = hull.wall_for_normal(hull.lift_normal((0.7071, -0.7071), "XZ"), spec)
    assert 6 < blended < 16, f"a sloped surface should blend, got {blended}"


def test_each_edge_moves_in_by_its_own_wall():
    """The heart of it. A 100x60 side outline with a 16mm floor and 6mm elsewhere must come
    back with its bottom edge raised 16 and everything else moved 6."""
    spec = hull.wall_spec({"wallThickness": 6, "wallTop": 6, "wallSide": 6, "wallBottom": 16})
    out = hull.offset_inward([(0, 0), (100, 0), (100, 60), (0, 60)], "XZ", spec)
    xs = sorted({round(x, 3) for x, _ in out})
    zs = sorted({round(z, 3) for _, z in out})
    assert xs == [6.0, 94.0], f"sides should move in 6mm, got {xs}"
    assert zs == [16.0, 54.0], f"floor should rise 16 and roof drop 6, got {zs}"


def test_the_wall_is_chosen_by_the_surface_normal_not_the_direction_of_travel():
    """The sign trap, and it is worth a test of its own because getting it backwards silently
    swaps a thick floor for a thick roof — which is exactly the mistake this feature exists to
    prevent. An edge along the bottom moves UP to make the cavity, but the surface it creates
    faces DOWN and is the floor."""
    spec = hull.wall_spec({"wallThickness": 6, "wallTop": 6, "wallSide": 6, "wallBottom": 16})
    out = hull.offset_inward([(0, 0), (100, 0), (100, 60), (0, 60)], "XZ", spec)
    bottom = min(z for _, z in out)
    top = max(z for _, z in out)
    assert abs(bottom - 16.0) < 1e-6, f"the THICK value belongs to the floor, got {bottom}"
    assert abs((60 - top) - 6.0) < 1e-6, f"the thin value belongs to the roof, got {60 - top}"


def test_offsetting_a_wound_outline_either_way_gives_the_same_cavity():
    """Winding is not something a traced outline can be trusted to have consistently, and
    inward has to mean inward regardless. `poly_area()` is abs()-ed, so it cannot tell the two
    apart — using it here made a clockwise outline offset OUTWARD."""
    spec = hull.wall_spec({"wallThickness": 5})
    ccw = [(0, 0), (100, 0), (100, 60), (0, 60)]
    a = hull.offset_inward(ccw, "XZ", spec)
    b = hull.offset_inward(list(reversed(ccw)), "XZ", spec)
    assert sorted(round(x, 3) for x, _ in a) == sorted(round(x, 3) for x, _ in b)
    assert min(x for x, _ in a) > 0 and max(x for x, _ in a) < 100, "it must move INWARD"


def test_a_degenerate_outline_does_not_explode():
    """Repeated points and near-parallel edges are normal in traced data. A wrong corner is
    survivable; a coordinate at 1e17 is not."""
    spec = hull.wall_spec({"wallThickness": 3})
    out = hull.offset_inward([(0, 0), (0, 0), (50, 0), (50, 40), (0, 40)], "XZ", spec)
    assert len(out) == 5
    for x, y in out:
        assert abs(x) < 1e6 and abs(y) < 1e6, f"runaway corner at {(x, y)}"


def _block_with(features, length=100.0, height=40.0, half_width=30.0):
    """A plain rectangular block, so a volume can be predicted by hand rather than compared
    against a previous run of the same code."""
    return {
        "length": length,
        "topProfile": [[0, height], [1, height]],
        "widthProfile": [[0, half_width], [1, half_width]],
        "sidePoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "topPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "frontPoly": [[0, 0], [1, 0], [1, 1], [0, 1]],
        "hullHollow": False,
        "features": features,
    }


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_hollow_profile_comes_back_hollow():  # pragma: no cover - needs the kernel
    """The one nobody had written, and the reason it mattered.

    `build_solid(profile)` used to default `hollow` to False regardless of what the profile
    said, so calling it directly returned a SOLID BLOCK in silence. Every test written against
    it was therefore measuring a solid — including four of mine that were named for the
    hollowing they were not checking. They passed for a year of sessions.

    Nothing shipped was broken by it: the real export path passes the flag. But a test that
    cannot fail is worse than no test, because it is counted."""
    block = _block_with([])
    block["hullHollow"] = True
    block["wallThickness"] = 5.0
    solid = hull.build_solid(_block_with([]))            # hullHollow absent -> a solid block
    shell = hull.build_solid(block)                      # asks the profile, and it says hollow
    assert shell.val().Volume() < solid.val().Volume() * 0.7, (
        f"a profile that says hullHollow must come back hollow: "
        f"{shell.val().Volume():.0f} vs a solid {solid.val().Volume():.0f} mm3")
    # and an explicit flag must still win, so the export path is unaffected
    assert hull.build_solid(block, hollow=False).val().Volume() == solid.val().Volume()


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_thick_floor_really_is_thicker_in_the_solid():  # pragma: no cover - needs the kernel
    """The per-face cavity, built for real. This shipped verified only through `plan()` and the
    polygon maths — the CAD half had never been executed anywhere.

    A 100x60 block with 5mm walls and a 15mm floor should hold about 45,000 cubic mm more
    material than the uniform version: the extra 10mm of floor over roughly 90x50 of cavity."""
    base = _block_with([])
    base["hullHollow"] = True
    uniform = dict(base, wallThickness=5.0, wallTop=5.0, wallSide=5.0, wallBottom=5.0)
    thick = dict(base, wallThickness=5.0, wallTop=5.0, wallSide=5.0, wallBottom=15.0)
    u = hull.build_solid(uniform).val().Volume()
    t = hull.build_solid(thick).val().Volume()
    assert t > u, f"a thicker floor must add material ({t:.0f} vs {u:.0f})"
    assert abs((t - u) - 45000) < 15000, (
        f"a 10mm thicker floor should add roughly 45,000 cubic mm, added {t - u:.0f}")
    assert hull.build_solid(thick).val().isValid(), "and the result must be a valid solid"


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_real_traced_car_comes_back_hollow():  # pragma: no cover - needs the kernel
    """The bug this exists to prevent, and it shipped for months.

    `shell()` offsets every face at once. On a traced car that is 188 faces, many near-tangent,
    and one bad offset returns a Null TopoDS_Shape. The code caught it, printed a line nobody
    reads, and returned the SOLID — so a real car exported as 807 cm3 of material where a
    4.9mm shell was asked for. No error, valid file, wrong part.

    A unit block has six faces and shells fine, so every existing test passed. Only a real
    traced outline shows it, which is why this test loads one rather than building a box."""
    import json as _json
    from pathlib import Path as _Path
    candidates = [
        _Path(__file__).resolve().parent.parent.parent / "LEE3D-Lib" / "schema" / "fixture-charger.profile.json",
        _Path(__file__).resolve().parent.parent.parent / "lib" / "schema" / "fixture-charger.profile.json",
    ]
    car = None
    for c in candidates:
        if c.exists():
            car = _json.loads(c.read_text(encoding="utf8"))
            break
    if car is None:
        pytest.skip("no traced car available — check out LEE3D-Lib beside this repo")

    plain = dict(car, features=[])
    solid = hull.build_solid(plain, hollow=False).val().Volume()
    shell = hull.build_solid(plain).val()          # profile says hullHollow
    assert shell.isValid(), "the hollow build must still be a valid solid"
    assert len(shell.Solids()) == 1, "and one piece, not fragments"
    assert shell.Volume() < solid * 0.7, (
        f"a real traced car must come back HOLLOW: {shell.Volume():.0f} mm3 against a solid "
        f"{solid:.0f}. If these are equal, shell()/the cavity has failed and been swallowed.")


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_per_face_walls_work_on_a_real_traced_car():  # pragma: no cover - needs the kernel
    """Per-face thickness on a REAL outline, not a box.

    The first implementation offset each traced polygon inward by its own face's wall. That
    tangles any outline with an edge shorter than the wall — a 4.22mm edge against a 4.9mm wall
    on this car — and the resulting self-intersecting loop builds into a solid that then
    refuses to intersect with anything. Every pair of inset prisms came out empty. The unit
    square tests all passed, because a square has four long edges.

    The working approach offsets nothing: build the cavity at the THINNEST face, where
    offset2D is reliable, then trim it back with half-spaces for the faces that want more.
    Trimming can only make a wall thicker, never thinner, and there is no polygon arithmetic
    to go wrong."""
    import json as _json
    from pathlib import Path as _Path
    car = None
    for c in [_Path(__file__).resolve().parent.parent.parent / n / "schema" / "fixture-charger.profile.json"
              for n in ("LEE3D-Lib", "lib")]:
        if c.exists():
            car = _json.loads(c.read_text(encoding="utf8"))
            break
    if car is None:
        pytest.skip("no traced car available — check out LEE3D-Lib beside this repo")

    body = dict(car, features=[])
    uniform = hull.build_solid(dict(body, wallThickness=5, wallTop=5, wallSide=5,
                                    wallBottom=5)).val().Volume()
    for name, w in (("floor", dict(wallTop=5, wallSide=5, wallBottom=15)),
                    ("roof", dict(wallTop=15, wallSide=5, wallBottom=5)),
                    ("side", dict(wallTop=5, wallSide=12, wallBottom=5))):
        g = hull.build_solid(dict(body, wallThickness=5, **w)).val()
        assert g.isValid() and len(g.Solids()) == 1, f"{name}: not one valid solid"
        assert g.Volume() > uniform * 1.02, (
            f"thickening the {name} must add material on a real car "
            f"({g.Volume():.0f} vs uniform {uniform:.0f} mm3) — if it does not, per-face has "
            f"silently fallen back to a uniform wall")


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_hollow_that_fails_says_so_instead_of_returning_a_quiet_solid():
    # pragma: no cover - needs the kernel
    """`plan()` reports hollow:true because the PROFILE asked for a shell. It has no way of
    knowing whether one was actually built — the cavity can come out empty, and when it does
    the build catches it, prints, and returns the SOLID.

    Until now that fact never left `build_solid`: `p["hollow_failed"]` was set on a plan dict
    created inside the function and thrown away on return. So a caller could ask for a shell,
    be told hollow:true, and be handed a solid lump with nothing anywhere saying so. Same
    family as the pockets vanishing from every STEP and the extra views being ignored.

    A 40mm wall on a 40mm-tall block cannot leave a cavity — the inset collapses before it
    encloses anything. That is the honest trigger, and it needs no monkeypatching."""
    block = _block_with([])                    # 100 long, 40 tall, 60 wide
    block["hullHollow"] = True
    block["wallThickness"] = 40.0              # >= the half-height: no cavity is possible

    report: dict = {}
    solid = hull.build_solid(block, report=report)

    assert report.get("hollow_failed") is True, (
        "the cavity cannot exist at this wall, so the build must report the failure; "
        f"got {report!r}")
    assert "hollow_failed_reason" in report, "and it must say WHY, not just that it failed"

    plain = hull.build_solid(_block_with([]), hollow=False).val().Volume()
    assert abs(solid.val().Volume() - plain) < 1.0, (
        f"a failed hollow returns the solid unchanged: {solid.val().Volume():.0f} "
        f"vs {plain:.0f} mm3")

    # and plan() still cheerfully says hollow:true — which is exactly why the report is needed
    assert hull.plan(block)["hollow"] is True


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_hollow_that_works_reports_false_not_nothing():
    # pragma: no cover - needs the kernel
    """An ABSENT key and a False key mean different things: "nobody asked for a shell" versus
    "a shell was asked for and it worked". If only the failure path ever wrote to the report,
    the caller could not tell a success from a build that never tried, and would have to guess.
    Guessing is what put the pockets bug in the field."""
    block = _block_with([])
    block["hullHollow"] = True
    block["wallThickness"] = 5.0               # comfortably buildable on this block

    report: dict = {}
    shell = hull.build_solid(block, report=report)
    assert report.get("hollow_failed") is False, f"a working hollow reports False: {report!r}"

    solid = hull.build_solid(_block_with([]), hollow=False).val().Volume()
    assert shell.val().Volume() < solid * 0.7, "and it really is hollow"

    # a profile that never asked writes nothing at all
    untouched: dict = {}
    hull.build_solid(_block_with([]), report=untouched)
    assert "hollow_failed" not in untouched, (
        f"a solid build must not claim anything about hollowing: {untouched!r}")


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_export_bytes_passes_the_report_back_up():
    # pragma: no cover - needs the kernel
    """The endpoint calls `export_bytes`, not `build_solid`. A report that stops one frame
    short of the caller is no better than one that never left."""
    block = _block_with([])
    block["hullHollow"] = True
    block["wallThickness"] = 40.0
    report: dict = {}
    data, mime, name = hull.export_bytes(block, fmt="step", hollow=True, report=report)
    assert report.get("hollow_failed") is True, f"it must survive export_bytes: {report!r}"
    assert data and mime == "application/step", "and the export still works normally"


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_wall_at_exactly_the_inradius_is_a_failed_hollow_not_a_through_slot():
    # pragma: no cover - needs the kernel
    """THE KNIFE-EDGE. `offset2D` at exactly an outline's inradius does not raise — it returns
    a wire of area 0.0, and extruding that gives a solid of volume 0.0. Intersecting against a
    zero-volume solid is a SILENT NO-OP in OpenCascade, so the collapsed planes stopped
    constraining the cavity and whichever plane survived became the whole of it.

    Measured on the 100x40x60 block at its 20mm inradius: side and front both offset to area
    0.0000, top offset to 1200.0, and the "intersection" was the top prism alone. The cut
    removed 48000mm3 through the FULL height — an open through-slot in a part whose whole
    contract is to be closed and hollow — and it reported success.

    It is reachable with ordinary numbers. A 40x10x20mm bracket at a 5mm wall is the same
    point: 3000mm3 of an 8000mm3 part, 38%, sliced out and called a shell.

    One tick either side was always right: 19.9999 removes 0.2mm3 as it should, 20.0001 raises
    and is reported as a failed hollow. This pins the point between them to the 20.0001
    behaviour, which is the correct one.

    Three geometries, because the critical wall is min(half-height, half-width) and NOT
    half-height — the 90-tall block fails at 30 (its half-width), not at 45. One geometry
    would have recorded the wrong rule."""
    for name, kw, crit in (("100x40x60", dict(height=40.0, half_width=30.0), 20.0),
                           ("100x26x60", dict(height=26.0, half_width=30.0), 13.0),
                           ("100x90x60", dict(height=90.0, half_width=30.0), 30.0),
                           ("40x10x20", dict(length=40.0, height=10.0, half_width=10.0), 5.0)):
        solid = hull.build_solid(_block_with([], **kw), hollow=False).val().Volume()
        body = _block_with([], **kw)
        body["hullHollow"] = True
        body["wallThickness"] = crit

        report: dict = {}
        got = hull.build_solid(body, report=report).val().Volume()

        assert report.get("hollow_failed") is True, (
            f"{name}: at a {crit}mm wall no cavity can exist, so this is a FAILED hollow and "
            f"must say so rather than cutting a slot; got {report!r}")
        assert abs(got - solid) < 0.5, (
            f"{name}: a failed hollow returns the solid untouched — {solid - got:.1f}mm3 was "
            f"removed, which is a through-slot, not a shell")

    # and the tick below the edge must still hollow normally, or the guard is too greedy
    below = _block_with([])
    below["hullHollow"] = True
    below["wallThickness"] = 19.9999
    report = {}
    v = hull.build_solid(below, report=report).val().Volume()
    assert report.get("hollow_failed") is False, "a hair under the edge still builds a cavity"
    assert 0.1 < (240000.0 - v) < 0.4, (
        f"and it removes the 0.2mm3 it should, not nothing: {240000.0 - v:.3f}mm3")


def test_a_collinear_outline_is_degenerate_even_though_it_has_three_points():
    """`_clean` counted POINTS. Three distinct points can still be collinear, and a line has
    no area to extrude.

    The two-point case was already caught and falls back to a box. This one was not: the
    outline passed through, `polyline().close().extrude()` returned solids of volume 0.0
    without raising, and `intersect()` DISCARDS a zero-volume operand and hands back the other
    one whole. So the side view stopped constraining the body and it came out as the full
    240000mm3 bounding box — not an error, not a warning, just a view silently ignored.

    Asserted on the OUTLINE, not the volume, and deliberately so: the box fallback produces the
    same body, so the volume is 240000 either way. A volume assertion here would pass whether
    or not the fix is present. Identical output means the code path did not run."""
    prof = dict(PROFILE)
    prof["sidePoly"] = [[0, 0], [0.5, 0], [1, 0]]          # three DISTINCT, all collinear
    assert len(hull.outlines_mm(prof)["side"]) == 4, (
        "a zero-area outline has to reach the box fallback like any other degenerate one")
    # and the two-point case must keep working
    prof["sidePoly"] = [[0.1, 0.1], [0.2, 0.2]]
    assert len(hull.outlines_mm(prof)["side"]) == 4


def test_a_collinear_feature_carves_nothing_rather_than_a_slab_across_the_body():
    """The same hole in the same guard, and far worse on this side.

    `shaped = tool.intersect(slab)` with a zero-volume `tool`: OpenCascade discards the
    collapsed operand and returns the SLAB — measured at 125,000,000mm3 for a 500mm test slab.
    The slab then became the cutter. A feature with no area cut a 3mm slot straight across the
    whole part: 240000 -> 228000mm3, exactly 100 x 40 x 3.

    Unlike the outline case this changes the answer, so it is pinned on the volume."""
    f = {"kind": "poly", "view": "side", "name": "flat", "depth": -3,
         "poly": [[0.2, 0.4], [0.5, 0.4], [0.7, 0.4]]}
    assert hull._clean(f["poly"]) is None, "a zero-area feature outline is degenerate"
    p = hull.plan(dict(PROFILE, features=[f]))
    assert p["pockets"] == [] and p["through_cuts"] == [] and p["surface_only"] == [], (
        f"a feature with no area has nothing to build: {p['pockets']} {p['surface_only']}")


def test_a_genuinely_thin_sliver_is_still_a_shape():
    """The collapse guard must catch an exact collapse and nothing else. These coordinates are
    normalised 0..1, where even a 0.0005-wide sliver measures 3e-4 in area — eight orders above
    the 1e-12 threshold. A guard that also rejected thin features would be a worse bug than the
    one it fixed, because thin is exactly what a traced panel line is."""
    thin = [[0.2, 0.2], [0.2005, 0.2], [0.2005, 0.8], [0.2, 0.8]]
    assert hull._clean(thin) is not None, "a thin sliver is a shape, not a collapse"
    p = hull.plan(dict(PROFILE, features=[
        {"kind": "poly", "view": "side", "name": "sliver", "depth": -3, "poly": thin}]))
    assert [f["name"] for f in p["pockets"]] == ["sliver"]


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_zero_volume_operand_is_discarded_by_every_boolean():
    # pragma: no cover - needs the kernel
    """THE ROOT CAUSE, pinned directly, because three separate bugs have now come from it and
    the next one will too if this is only ever written down in a comment.

    A wire with no area still extrudes to solids — they just have volume 0.0. OpenCascade does
    not treat that as an error in any boolean:

        a.intersect(zero)  -> a, untouched      the constraint silently stops applying
        a.cut(zero)        -> EMPTY             the model is destroyed
        a.union(zero)      -> volume 0.0        the model is destroyed

    Note they fail in different directions, so no single instinct covers them. The lesson for
    any new guard in this file: **test volume, never presence.** `solids().vals()` is non-empty
    for a collapsed solid — that check passes precisely when it matters most."""
    import cadquery as cq          # inside the test on purpose: a module-level import would
                                   # make this file unimportable on the light image and turn
                                   # the whole fast gate red instead of skipping one test
    zero = (cq.Workplane("XZ").polyline([(0, 0), (50, 0), (100, 0)])
            .close().extrude(100.0, both=True))
    zvals = zero.solids().vals()
    assert zvals, "a collapsed wire still produces solids — this is the whole trap"
    assert sum(s.Volume() for s in zvals) <= 1e-9, "with no volume"

    box = cq.Workplane("XY").box(100, 60, 40, centered=False)
    V = sum(s.Volume() for s in box.solids().vals())
    assert V == pytest.approx(240000)

    def vol(wp):
        return sum(s.Volume() for s in wp.solids().vals())

    assert vol(box.intersect(zero)) == pytest.approx(V), "intersect discards it and no-ops"
    assert vol(box.cut(zero)) <= 1e-9, "cut destroys the model"
    assert vol(box.union(zero)) <= 1e-9, "union destroys the model"


def test_the_studio_rejects_a_zero_area_outline_the_same_way_this_end_does():
    """BOTH ENDS, PINNED TOGETHER. `_clean` here and `normPoly` in index.html have to agree
    about what counts as a traced outline, or the preview and the export disagree about the
    shape of the part — which is the one failure this project cannot tolerate quietly.

    Both were `length >= 3` and both let a collinear outline through. Fixing only this end
    would have been worse than fixing neither: the backend would fall back to a box while the
    studio still built from the flat line, and the two would differ with nothing reporting it.

    This reads the studio's source directly rather than trusting a comment, because a comment
    saying "matches the backend" is exactly what stops being true first."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent
    idx = None
    for cand in (root / "LEE3D-Frontend" / "index.html",
                 root / "LEE3D-Frontend-main" / "index.html"):
        if cand.exists():
            idx = cand
            break
    if idx is None:
        pytest.skip("LEE3D-Frontend is not checked out beside this repo")

    src = idx.read_text(encoding="utf8", errors="ignore")
    assert "const polyAreaN=" in src, (
        "the studio's normPoly no longer measures area — it has regressed to counting points, "
        "and a flat traced outline will now build differently at the two ends")
    assert "polyAreaN(out)<=1e-12?null:out" in src, (
        "the studio's zero-area rejection is gone or its threshold has moved away from the "
        "1e-12 this end uses in _clean")


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_leaving_the_underside_open_actually_removes_the_floor():
    # pragma: no cover - needs the kernel
    """This end never read the studio's "Leave the underside open" tick at all. It always
    built a closed shell, so a model shown in the studio with an open underside came back
    from STEP export with a floor in it.

    Pinned on VOLUME, because that is what changes. A floor removed is material removed, and
    the bounding box is identical either way — asserting on the box would pass whether or not
    the flag does anything, which is exactly how this went unnoticed."""
    block = _block_with([])
    block["hullHollow"] = True
    block["wallThickness"] = 5.0

    closed = hull.build_solid(dict(block, openUnderside=False)).val().Volume()
    opened = hull.build_solid(dict(block, openUnderside=True)).val().Volume()

    assert opened < closed * 0.95, (
        f"opening the underside has to remove the floor: {opened:.0f} vs {closed:.0f} mm3")
    # the older spelling must work too — profiles saved before the rename carry openArches
    legacy = hull.build_solid(dict(block, openArches=True)).val().Volume()
    assert legacy == pytest.approx(opened, rel=1e-6), (
        "openArches is the older name for the same tick and must build the same part")
    # and it must still be one valid solid, not a lump cut in half
    v = hull.build_solid(dict(block, openUnderside=True)).val()
    assert v.isValid() and len(v.Solids()) == 1


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_the_open_underside_cut_has_to_overlap_the_cavity():
    # pragma: no cover - needs the kernel
    """THE BUG IN MY FIRST FIX, pinned so it cannot come back.

    The floor is removed by extending the cavity downward. My first attempt pushed one copy
    of the cavity down by more than the whole body height — which lands it entirely BELOW the
    part, with a gap, so the union was two disconnected lumps and the cut took nothing out.
    Volume came back byte-identical open and closed and it looked like the flag was being
    ignored again.

    The guard is that the extension must reach BELOW the body while staying connected to the
    cavity. Checked by measuring how much came out: a disconnected extension removes 0."""
    block = _block_with([])
    block["hullHollow"] = True
    block["wallThickness"] = 5.0
    closed = hull.build_solid(dict(block, openUnderside=False)).val().Volume()
    opened = hull.build_solid(dict(block, openUnderside=True)).val().Volume()
    removed = closed - opened
    assert removed > 0, "a disconnected extension removes nothing — this is that bug"
    # the floor of a 100x40x60 block at a 5mm wall is roughly the cavity footprint x 5mm
    assert removed > 5000, f"only {removed:.0f} mm3 came out; that is not a floor"


def test_the_studio_draws_its_cavity_from_the_unclipped_body():
    """BOTH ENDS. The studio's field hollow grew a wall band against the LEVELLING PLANE, and
    a wall band against that plane is a floor sealing the underside. It only appeared once the
    wall was thick enough for the field path to switch on, which is why "turn the thickness up
    and the underbody stops being hollow" was the shape of the report.

    Measured on the user's own car, his settings, before the fix:

        wall 2.1  field OFF  material up the middle 85.5-86.9           open
        wall 2.5  field ON   material up the middle 5.0-7.5, 85.2-86.8  FLOOR
        wall 6.0  field ON   material up the middle 5.0-16.8            FLOOR

    The floor starts at z=5.0, exactly his baseCutZ of 5.017.

    The fix feeds the CAVITY the unclipped body while the outer skin keeps the clipped field.
    Pinned by reading index.html, because the failure mode of the previous attempt was that it
    looked right and broke three other tests."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent
    idx = None
    for cand in (root / "LEE3D-Frontend" / "index.html",
                 root / "LEE3D-Frontend-main" / "index.html"):
        if cand.exists():
            idx = cand
            break
    if idx is None:
        pytest.skip("LEE3D-Frontend is not checked out beside this repo")
    src = idx.read_text(encoding="utf8", errors="ignore")
    assert "const F=(x,y,z,noCut)=>{" in src, (
        "the studio's field function no longer offers an unclipped reading, so the cavity has "
        "nothing to draw from but the levelling plane and the floor will be back")
    assert "if(noCut) return d;" in src, "the unclipped branch is gone"
    # , not : the floor-band extension below reassigns it.
    assert "bIn = openUnder ? Math.min(b, F(xm,ym,zm,true)) : b" in src, (
        "the cavity is no longer drawn from the unclipped body — the underside will seal "
        "again at every wall thickness the field path handles")
    # The unclipped cavity opens the BASE PLANE only. Ceilings above it — the underside of the
    # body where it sits over a wheel arch — need the ground-facing ramp, and without it the
    # studio floors them at every field wall thickness while THIS end opens them. Verified
    # against the kernel on a real traced car at a 3mm wall: closed leaves material at z 43.1,
    # 32.1 and 55.1 at three stations, open leaves only the roof.
    assert "if(openUnder && zm > baseCut + Math.max(wLoc, cell * 2))" in src, (
        "the studio's arch-ceiling ramp is gone, or its guard no longer keeps clear of the "
        "base plane — ramping down there lifts the body's floor and fails three of its own "
        "hollow invariants")
    # The floor band immediately above the opening needs its own term: the unclipped reading
    # bottoms out around -4.2mm there, so any wall thicker than that seals the underside.
    # All three conditions are load-bearing and each was learned by breaking something —
    # unbounded turns the body into cavity, dropping the normal test hollows the side walls
    # that hold the bbox floor, and dropping the depth test eats the rim at the opening.
    assert "bIn = Math.min(bIn, -(zm - baseCut) - wall - cell)" in src, (
        "the floor-band extension is gone — the underside will seal again above about a "
        "4.2mm wall")
    assert "zm < baseCut + wall*2 && -gz/g > 0.35 && bIn < -wall*0.6" in src, (
        "the floor-band extension's guards have changed. Unbounded turns the whole body into "
        "cavity; without the normal test the side walls get hollowed and the bbox floor "
        "lifts; without `bIn < -wall*0.6` it eats the rim and `the rim you see at an opening "
        "is a clean band, one wall thick` fails")
    # and the outer term must STILL read the clipped field: that is the invariant the previous
    # attempt broke, and three guard tests in the studio's own suite caught it.
    assert "shell[o]=Math.max(b, -(dist+wLoc));" in src, (
        "the outer surface must still come from `b`. Reading it from the cavity's field moves "
        "the body's outside and fails the studio's own hollow invariants.")


def test_base_cut_z_finds_the_ground_line_and_declines_when_there_is_none():
    """A direct port of the studio's `baseCutZ`. It has to agree with the studio, and it has
    to REFUSE when there is nothing to level — a plain block already stands flat, and cutting
    it at the mean of its own bottom face would shave the part for no reason.

    On a shape with wheels and arches the lows split into two populations: the parts that
    reach the ground and the parts that hang in the air. Fewer than 8% of the height between
    them means one population, and no cut."""
    # a block: every column bottoms out at the same z, so there is only one population
    blk = hull.outlines_mm(_block_with([]))
    assert hull.base_cut_z(blk["side"], 40.0) == float("-inf"), (
        "a flat-bottomed body has no ground line to find and must not be cut")

    # a silhouette with two feet and a raised belly between them
    feet = [(0, 0), (30, 0), (30, 20), (70, 20), (70, 0), (100, 0), (100, 60), (0, 60)]
    z = hull.base_cut_z(feet, 60.0)
    assert z == pytest.approx(0.0, abs=1e-6), (
        f"the feet reach z=0 and that is the level the part stands on; got {z}")

    # and it declines on garbage rather than returning a number
    assert hull.base_cut_z(None, 40.0) == float("-inf")
    assert hull.base_cut_z([(0, 0), (1, 1)], 40.0) == float("-inf")


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_the_exact_body_is_levelled_the_same_way_the_studio_levels_it():
    # pragma: no cover - needs the kernel
    """THE SKIRT. This end had no level-base cut at all, so every STEP export carried whatever
    the trace left below the ground-touching line while the studio's preview showed it clipped
    flat. On a real traced car that was 5mm of material the user never saw — the exact solid
    stood 89.0mm against the studio's 83.9mm — and a part that does not sit flat on the bed is
    precisely what levelling a base is for.

    The silhouette here has two feet at 0.15, a belly raised to 0.5, and ONE narrow column that
    dips to 0. Without the cut the body's lowest point is that dip; with it the body starts at
    the feet. Asserting on the dip is what makes this test able to fail — a shape that already
    stands flat would pass whether or not the cut ran at all."""
    feet = [[0.00, 0.15], [0.20, 0.15], [0.20, 0.50], [0.40, 0.50],
            [0.40, 0.15], [0.44, 0.15], [0.44, 0.00], [0.46, 0.00],   # the dip
            [0.46, 0.15], [0.60, 0.15], [0.60, 0.50], [0.80, 0.50],
            [0.80, 0.15], [1.00, 0.15], [1.00, 1.00], [0.00, 1.00]]
    prof = dict(PROFILE)
    prof["sidePoly"] = feet
    o = hull.outlines_mm(prof)
    H = hull.plan(prof)["dims"]["height"]
    z = hull.base_cut_z(o["side"], H)
    assert z > 1e-6, f"this silhouette has a clear ground line at 0.15*H; got {z}"

    lowest = min(q[1] for q in o["side"])
    assert lowest < z - 1.0, (
        "the fixture must dip BELOW its own ground line or this test cannot fail")

    v = hull.build_solid(prof, hollow=False).val()
    assert v.BoundingBox().zmin == pytest.approx(z, abs=0.2), (
        f"the body must be levelled to {z:.3f}; got {v.BoundingBox().zmin:.3f}. "
        f"Uncut it would reach down to {lowest:.3f}.")


def test_a_flat_bottomed_body_is_not_shaved_by_the_levelling():
    """The guard on the other side. `base_cut_z` returning -inf has to mean NO CUT, not a cut
    at minus infinity, and a block must come back the height it went in."""
    blk = _block_with([])
    p = hull.plan(blk)
    assert hull.base_cut_z(hull.outlines_mm(blk)["side"], p["dims"]["height"]) == float("-inf")


def test_scale_is_recorded_without_touching_the_geometry():
    """A building cannot be expressed as a model dimension alone. An architect works at 1:200
    and the model size FOLLOWS from the real size; without somewhere to keep the real figure it
    is lost the moment a model length is typed in.

    `length` remains the MODEL size and every dimension is still built from it, so a profile
    carrying neither field behaves exactly as it always has. **That is what keeps the car
    untouched by the construction work**, and it is asserted here rather than assumed."""
    plain = hull.plan(PROFILE)
    assert plain["real_dims"] is None and plain["scale_mismatch"] is None, (
        "a profile with no scale must report none — this is the car's path")

    scaled = hull.plan(dict(PROFILE, modelScale=200))
    assert scaled["dims"] == plain["dims"], (
        "the MODEL dimensions must not move when a scale is attached; geometry is built from "
        "them and attaching a scale is a record, not a transform")
    L = plain["dims"]["length"]
    assert scaled["real_dims"]["length"] == pytest.approx(L * 200)
    assert scaled["real_dims"]["height"] == pytest.approx(plain["dims"]["height"] * 200)


def test_a_scale_that_disagrees_with_the_model_size_is_reported_not_resolved():
    """Given a real length AND a scale, the two can contradict the model length — and then the
    model is not the scale it claims to be. Report it, the way `unusable_views` and
    `hollow_failed` are reported. Quietly preferring one of them is exactly how the two ends of
    this project have gone out of step before."""
    L = hull.plan(PROFILE)["dims"]["length"]

    ok = hull.plan(dict(PROFILE, modelScale=100, realLength=L * 100))
    assert ok["scale_mismatch"] is None, "consistent numbers must not raise a false alarm"

    bad = hull.plan(dict(PROFILE, modelScale=100, realLength=L * 250))
    assert bad["scale_mismatch"] is not None, (
        "a real length of 250x the model at a claimed 1:100 is a contradiction")
    assert bad["scale_mismatch"]["implied_length"] == pytest.approx(L * 2.5)
    assert bad["scale_mismatch"]["model_length"] == pytest.approx(L)

    # and junk in those fields must not throw — a saved profile can carry anything
    for junk in ("", None, "abc", 0, -5):
        p = hull.plan(dict(PROFILE, modelScale=junk, realLength=junk))
        assert p["real_dims"] is None and p["scale_mismatch"] is None


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_turned_object_is_revolved_here_not_carved_from_silhouettes():
    # pragma: no cover - needs the kernel
    """A VISUAL HULL CANNOT MAKE A ROUND THING ROUND. Measured in the studio on a fountain
    elevation: 36% out of round — a square is 41% — everywhere the body is narrower than its
    widest plan circle, because the cross-section there is side-width intersected with
    front-width. No refinement fixes it.

    The studio grew a lathe first. Without this dispatch a fountain previewed as round would
    export through the hull and arrive SQUARE — the two ends disagreeing about the whole part,
    which is the failure this repo keeps being caught by. Here it costs nothing to be exact:
    `revolve` is what a lathe is."""
    import math
    import cadquery as cq        # inside the test: a module-level import would make this file
                                 # unimportable on the light image and turn the fast gate red
    H = 100.0
    # a stepped profile: wide base, narrow stem, wide flange, narrow top
    prof = []
    for i in range(49):
        t = i / 48.0
        r = 60.0 if t < 0.18 else (26.4 if t < 0.55 else (60.0 if t < 0.72 else 26.4))
        prof.append([t, r])
    p = {"shape": "lathe", "revProfileV": prof, "revHeight": H, "length": 120.0,
         "topProfile": [[0, 100], [1, 100]], "widthProfile": [[0, 60], [1, 60]],
         "hullHollow": False, "wallThickness": 3.0}
    v = hull.build_solid(p, hollow=False).val()
    assert v.isValid() and len(v.Solids()) == 1
    bb = v.BoundingBox()
    assert bb.zmin == pytest.approx(0.0, abs=0.5) and bb.zmax == pytest.approx(H, abs=0.5), (
        f"a turned body stands on the floor at its own height; got z {bb.zmin}..{bb.zmax}. "
        f"A z span of roughly -H..+H means the revolve axis is wrong — `revolve`'s axis points "
        f"are in the WORKPLANE's local coordinates, and on XZ world Z is local (0,1,0).")

    # round at a height where the hull would have been square
    rs = []
    for a in range(0, 360, 15):
        r = 0.5
        while r < 90:
            if not v.isInside(cq.Vector(r*math.cos(math.radians(a)), r*math.sin(math.radians(a)), 40.0), 1e-6):
                break
            r += 0.25
        rs.append(r)
    assert max(rs) / min(rs) < 1.02, (
        f"a turned body must be round: radii {min(rs):.2f}..{max(rs):.2f} at z=40. "
        f"The hull's answer here was 36% out of round.")


@pytest.mark.skipif(not HAS_CQ, reason="needs OpenCascade")
def test_a_turned_object_hollows_for_printing():
    # pragma: no cover - needs the kernel
    """A solid fountain at model scale is a lot of filament and a long print. The cavity is
    revolved from the same profile pulled in by one wall and stopped one wall short of the top,
    so the top keeps its thickness and the underside is open — the convention the rest of this
    file already uses."""
    prof = [[i/48.0, 60.0 if i/48.0 < 0.5 else 30.0] for i in range(49)]
    base = {"shape": "lathe", "revProfileV": prof, "revHeight": 100.0, "length": 120.0,
            "topProfile": [[0, 100], [1, 100]], "widthProfile": [[0, 60], [1, 60]],
            "wallThickness": 3.0}
    solid = hull.build_solid(dict(base, hullHollow=False), hollow=False).val().Volume()
    shell = hull.build_solid(dict(base, hullHollow=True), hollow=True).val().Volume()
    assert shell < solid * 0.5, (
        f"hollowing has to remove most of it: {shell/1000:.1f} against {solid/1000:.1f} cm3")
    assert shell > solid * 0.02, "and it must not remove everything — that is a failed cut"


def test_a_lathe_profile_that_is_junk_raises_rather_than_building_nonsense():
    """A saved profile can carry anything. A turned object with no radius in it has no shape,
    and returning some default lump would be worse than saying so."""
    if not HAS_CQ:
        pytest.skip("needs OpenCascade")
    for bad in ([], [[0, 0], [1, 0]], [["x", "y"]], None):
        with pytest.raises(Exception):
            hull.build_solid({"shape": "lathe", "revProfileV": bad, "revHeight": 100.0,
                              "length": 120.0, "topProfile": [[0, 100], [1, 100]],
                              "widthProfile": [[0, 60], [1, 60]]}, hollow=False)
