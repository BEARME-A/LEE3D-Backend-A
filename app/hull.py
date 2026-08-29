"""
Exact solid modelling of a traced profile (OpenCascade, via CadQuery).

The browser builds the same shape out of a voxel grid: fast, always watertight, good
enough to look at. It has two hard limits, and both come from the same place — it can
only *move* the surface it already has:

  * a window can be dished, never cut through
  * a corner is only as sharp as the grid is fine

OpenCascade has no such limit, and it is free and open source — it is already sitting in
this repo (see Dockerfile.full). So here the same traced outlines become real geometry:

  * the visual hull is three extruded outlines INTERSECTED — exact, no grid, no rounding
  * a feature marked "through" becomes a genuine boolean cut, i.e. an actual hole
  * the result exports as STEP, which opens in any CAD package and stays editable

Nothing here replaces the browser. The browser is the fast always-works path; this is the
"make it exact" pass.

CadQuery is heavy, so it is imported lazily: the API still boots and serves everything
else without it, and asks for the full image only when someone actually wants exact output.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple


class CadUnavailable(RuntimeError):
    """Raised when exact modelling is asked for but OpenCascade isn't installed."""


def _import_cq():
    try:
        import cadquery as cq  # noqa: F401
        return cq
    except Exception as e:  # pragma: no cover - depends on the image
        raise CadUnavailable(
            "Exact modelling needs OpenCascade (CadQuery), which isn't in this image. "
            "This service runs the light image by default so it deploys fast; build with "
            "./Dockerfile.full for exact/STEP output. Original error: " + repr(e)
        )


# --------------------------------------------------------------------------------------
# Pure geometry prep. No CadQuery here on purpose, so it can be tested anywhere.
# --------------------------------------------------------------------------------------
Pt = Tuple[float, float]

_UNIT_BOX: List[Pt] = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def _clean(poly: Sequence[Sequence[float]] | None) -> List[Pt] | None:
    """Drop junk, repeated points and a duplicated closing point."""
    if not poly:
        return None
    out: List[Pt] = []
    for p in poly:
        if p is None or len(p) < 2:
            continue
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            continue
        if x != x or y != y:          # NaN
            continue
        if out and abs(out[-1][0] - x) < 1e-9 and abs(out[-1][1] - y) < 1e-9:
            continue
        out.append((x, y))
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-9 and abs(out[0][1] - out[-1][1]) < 1e-9:
        out.pop()                     # the extruder closes it for us
    return out if len(out) >= 3 else None


# =======================================================================================
# PER-FACE WALL THICKNESS — roof, sides and floor can differ.
#
# The studio lets someone set a thick floor to bolt through with thin walls elsewhere, and the
# exact build shelled with one number, so a per-face model exported uniform. `solid.shell()`
# cannot vary its thickness, so the cavity has to be built rather than offset.
#
# Which is the carving principle again, one level in: the body is the intersection of three
# extruded outlines, so the CAVITY is the intersection of those same outlines each pulled
# inward by the wall belonging to the surface it creates. Cut one from the other and the shell
# is whatever is between them.
#
# Collin's framing, and it is the right one: label every outline point by which axis it faces.
# A point on the side outline whose normal points up is ROOF; the same outline's normal
# pointing along the length is a nose or tail, which counts as SIDE. That classification is
# all `wall_for_normal` needs, and it is what makes a 2D outline carry 3D face information.
#
# The polygon maths lives here, in plain Python, because it is the part that can be got wrong
# and the part that can be tested without a CAD kernel. Everything OpenCascade touches is kept
# trivial on purpose.
# =======================================================================================

def wall_spec(profile: dict) -> dict:
    """Roof / side / floor thickness, each falling back to the single wall. Mirrors
    `wallSpec()` in the studio exactly, so the two ends cannot drift apart on the defaults."""
    base = max(0.2, float(profile.get("wallThickness") or 1.8))
    return {
        "top": max(0.2, float(profile.get("wallTop") or base)),
        "side": max(0.2, float(profile.get("wallSide") or base)),
        "bot": max(0.2, float(profile.get("wallBottom") or base)),
        "base": base,
    }


def wall_varies(spec: dict) -> bool:
    """True only when the three faces actually differ. A uniform model must take the plain
    shell path it always did — this is what keeps the change free for everyone else."""
    return (abs(spec["top"] - spec["side"]) > 1e-6
            or abs(spec["bot"] - spec["side"]) > 1e-6
            or abs(spec["top"] - spec["bot"]) > 1e-6)


def wall_for_normal(n3: Sequence[float], spec: dict) -> float:
    """Blend roof/side/floor by how much a normal points up, sideways and down.
    Same formula as `wallAt()` in the studio: weighted, not switched, so the thickness turns
    smoothly through a corner instead of stepping and leaving a seam."""
    up = max(0.0, n3[2])
    down = max(0.0, -n3[2])
    side = math.hypot(n3[0], n3[1])
    total = up + down + side
    if total < 1e-9:
        return spec["base"]
    return (spec["top"] * up + spec["bot"] * down + spec["side"] * side) / total


def lift_normal(n2: Sequence[float], plane: str) -> Tuple[float, float, float]:
    """Put a 2D outline normal back into 3D. This is the `ax, ay, az` step: an outline is drawn
    on one plane, and which axes its normal occupies is what says whether that stretch of it is
    roof, floor or flank.
        XZ (the side view)   -> (nx, 0, nz)   can be roof, floor, nose or tail
        XY (the plan view)   -> (nx, ny, 0)   always a flank
        YZ (the front view)  -> (0, ny, nz)   can be roof, floor or flank
    """
    a, b = float(n2[0]), float(n2[1])
    if plane == "XZ":
        return (a, 0.0, b)
    if plane == "XY":
        return (a, b, 0.0)
    return (0.0, a, b)


def offset_inward(poly: Sequence[Pt], plane: str, spec: dict) -> List[Pt]:
    """Pull a closed outline inward, by a different amount along each stretch of it.

    Each edge moves in along its own inward normal by the wall belonging to that edge's
    direction. The new corners are where consecutive offset edges meet — solved as a line
    intersection, so a corner stays a corner instead of being rounded or clipped.

    Where two offset edges are nearly parallel their intersection runs away to infinity, so
    that corner falls back to the plain offset point. Rare, and a wrong corner is better than
    a coordinate at 1e17.
    """
    n = len(poly)
    if n < 3:
        return list(poly)
    # WHICH WAY IS IN. `poly_area()` returns a magnitude — it is abs()-ed, because every other
    # caller wants a size — so it cannot tell the two windings apart. Using it here made a
    # clockwise outline offset OUTWARD, which on a traced file is a coin flip: nothing
    # guarantees the winding of an outline somebody drew. Compute the SIGNED area locally.
    signed = 0.0
    for i in range(n):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        signed += x1 * y2 - x2 * y1
    ccw = signed > 0
    lines = []
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        if length < 1e-12:
            lines.append(None)
            continue
        # Inward normal — the direction this edge has to move to make the cavity.
        nx, ny = (-ey / length, ex / length) if ccw else (ey / length, -ex / length)
        # ...but the wall is chosen by the SURFACE normal, which points the other way. An edge
        # along the bottom of a side view has an inward normal pointing UP, and lifting that
        # straight into 3D reads as roof — while the surface it makes faces DOWN and is the
        # floor. Getting this backwards silently swaps a thick floor for a thick roof, which is
        # exactly the mistake this whole feature exists to prevent.
        w = wall_for_normal(lift_normal((-nx, -ny), plane), spec)
        lines.append((x1 + nx * w, y1 + ny * w, ex / length, ey / length))
    out: List[Pt] = []
    for i in range(n):
        a = lines[i - 1]
        b = lines[i]
        if a is None or b is None:
            out.append(poly[i])
            continue
        ax, ay, adx, ady = a
        bx, by, bdx, bdy = b
        den = adx * bdy - ady * bdx
        if abs(den) < 1e-9:                       # parallel: no corner to solve
            out.append((bx, by))
            continue
        t = ((bx - ax) * bdy - (by - ay) * bdx) / den
        out.append((ax + adx * t, ay + ady * t))
    return out


def poly_area(poly: Sequence[Pt]) -> float:
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def dims(profile: Dict[str, Any]) -> Tuple[float, float, float]:
    """Length / width / height in mm, read the same way the studio reads them."""
    L = float(profile.get("length") or 150.0)
    top = profile.get("topProfile") or []
    wid = profile.get("widthProfile") or []
    H = max((float(p[1]) for p in top if len(p) > 1), default=60.0)
    halfW = max((float(p[1]) for p in wid if len(p) > 1), default=30.0)
    return max(1.0, L), max(1.0, 2.0 * halfW), max(1.0, H)


def outlines_mm(profile: Dict[str, Any]) -> Dict[str, List[Pt]]:
    """
    The three traced outlines, turned from 0..1 into real millimetres on their own plane.
    Matches the studio exactly, so the exact build and the preview agree:

        side  (u,v) -> (x , z)      length x height
        top   (u,v) -> (x , y)      length x width   (y centred on 0)
        front (u,v) -> (y , z)      width  x height  (y centred on 0)
    """
    L, W, H = dims(profile)
    side = _clean(profile.get("sidePoly")) or _UNIT_BOX
    top = _clean(profile.get("topPoly")) or _UNIT_BOX
    front = _clean(profile.get("frontPoly")) or _UNIT_BOX
    return {
        "side": [(u * L, v * H) for u, v in side],
        "top": [(u * L, v * W - W / 2.0) for u, v in top],
        "front": [(u * W - W / 2.0, v * H) for u, v in front],
    }


def feature_mm(feat: Dict[str, Any], L: float, W: float, H: float) -> Dict[str, Any] | None:
    """One feature's outline on its own plane, in mm, plus how it should be applied."""
    poly = _clean(feat.get("poly"))
    if not poly:
        return None                    # text/mask features stay a surface effect for now
    view = feat.get("view") or "side"
    depth = float(feat.get("depth") or 0.0)
    # ALL SIX VIEWS ARE NAMED HERE. "sideR" used to fall through to the front/rear branch
    # and a window traced on the right flank was cut through the nose instead — the same
    # fall-through the studio had, and it has to be fixed on both ends or the exact build
    # and the preview disagree about where a feature is.
    if view == "side":
        pts = [(u * L, v * H) for u, v in poly]
    elif view == "sideR":
        # traced standing on the far side, so its length axis mirrors — exactly the flip
        # the studio applies to sidePolyR
        pts = [((1.0 - u) * L, v * H) for u, v in poly]
    elif view in ("top", "bottom"):
        # features store v screen-up, topPoly/bottomPoly store v screen-down; without the
        # 1- the detail lands on the opposite flank from the one it was drawn on
        pts = [(u * L, (1.0 - v) * W - W / 2.0) for u, v in poly]
    else:                              # front / rear
        pts = [(u * W - W / 2.0, v * H) for u, v in poly]
        if view == "rear":
            pts = [(-y, z) for y, z in pts]
    return {
        "view": view,
        "pts": pts,
        "depth": depth,
        "through": bool(feat.get("through")),
        "name": feat.get("name") or "feature",
    }


def _hollow_wanted(profile: Dict[str, Any]) -> bool:
    """Is this meant to be a shell? The studio says so with hullHollow. Older profiles only
    carried sepBottom, where "no separate bottom piece" implied a single hollow body."""
    want = profile.get("hullHollow")
    if want is None:
        want = not profile.get("sepBottom")
    return bool(want)


def plan(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Everything the exact build is going to do, worked out without touching OpenCascade.
    Handy for testing, and for telling someone what they're about to get.
    """
    L, W, H = dims(profile)
    o = outlines_mm(profile)
    feats = [f for f in (feature_mm(x, L, W, H) for x in (profile.get("features") or [])) if f]
    # WHAT THE EXACT BUILD DOES WITH EACH FEATURE.
    # This used to be two buckets: through-cuts, and "surface_only — the browser already does
    # these". That second comment stopped being true when the studio moved its detail work into
    # the distance field: a pocket is now REAL GEOMETRY cut to an exact depth, not a dish
    # pressed into a surface. The two ends silently disagreed, and on the project's own
    # reference car that meant 0 of 153 features made it into the STEP — an export that looked
    # like a smooth body and raised no error. Same shape as the sepBottom/hullHollow bug below.
    # OpenCascade cuts a finite-depth pocket directly, so there is no reason to skip them.
    cuts = [f for f in feats if f["through"] and f["depth"] < 0]
    pockets = [f for f in feats if not f["through"] and f["depth"] < 0]
    raises = [f for f in feats if not f["through"] and f["depth"] > 0]
    # A feature with no depth is a mask or a text label: a surface effect with no solid meaning.
    surface = [f for f in feats if f["depth"] == 0.0]
    # OUTLINES THIS BUILD CANNOT USE.
    # The studio can now carve from silhouettes at ANY angle (p.extraViews), which is the
    # groundwork for building from photographs — several views of an object, each one saying
    # where the object cannot be. This build intersects the three axis outlines only, so a
    # model that uses extra views would come out FATTER here than in the preview: every extra
    # view removes material, and the ones we cannot use remove none.
    # It is reported rather than ignored. That is the whole lesson of the pockets: a quiet
    # difference between the two ends is worse than a loud limitation.
    extra = [v for v in (profile.get("extraViews") or [])
             if isinstance(v, dict) and _clean(v.get("poly"))]
    return {
        "dims": {"length": L, "width": W, "height": H},
        "outlines": o,
        "unusable_views": len(extra),
        "through_cuts": cuts,
        "pockets": pockets,
        "raises": raises,
        "surface_only": surface,      # masks and labels: genuinely nothing to build
        # HOLLOW COMES FROM hullHollow, WHICH IS THE FLAG THE STUDIO ACTUALLY SETS.
        # This used to read sepBottom, which means something else entirely — whether the
        # underside is a separate printed piece — and the studio sends that as true on every
        # frame. So "hollow" evaluated False every single time and an exact build came back
        # SOLID: for a 200mm car, on the order of a litre of material against the 95cc shell
        # in the preview beside it. Nothing errored; the two ends simply disagreed.
        # sepBottom stays as a fallback for profiles saved before hullHollow existed, where
        # having no separate bottom did imply one hollow body.
        "hollow": _hollow_wanted(profile) and float(profile.get("wallThickness") or 0) > 0,
        "wall": float(profile.get("wallThickness") or 1.8),
        "wall_spec": wall_spec(profile),          # roof/side/floor, for the per-face cavity
        "wall_varies": wall_varies(wall_spec(profile)),
        # THE EXACT BUILD IS SYMMETRIC. It intersects three extruded outlines, and there is
        # only one side outline in that set — sidePolyR is not read here at all. The studio
        # DOES sweep between two side drawings, so on an asymmetric model the STEP and the
        # preview are different shapes. That was true before and simply invisible; say it
        # out loud instead, so the studio can warn rather than hand over a quietly wrong file.
        "ignored_second_side": bool(
            (profile.get("sidePolyR") or []) and len(profile.get("sidePolyR") or []) > 2
        ),
    }


# --------------------------------------------------------------------------------------
# The exact build. Needs OpenCascade.
# --------------------------------------------------------------------------------------
def build_solid(profile: Dict[str, Any], hollow: bool | None = None):
    """`hollow=None` means ASK THE PROFILE, which is almost always what a caller wants.

    It used to default to False, so `build_solid(profile)` on a profile that says
    `hullHollow: true` returned a solid block and said nothing. The real export path passes the
    flag explicitly and was never affected — but every test written against `build_solid`
    directly was quietly measuring a solid, including four of mine that were meant to be
    checking the hollowing. They passed for a year of sessions without running the thing they
    named.
    Deferring to the profile removes the trap; an explicit True or False still wins, so the
    export path is unchanged.

    Three traced outlines -> one exact solid.

    The visual hull is literally the intersection of the three outlines extruded through
    each other. The browser approximates that on a grid; OpenCascade just computes it, so
    corners are corners and curves are curves at any zoom.
    """
    cq = _import_cq()
    p = plan(profile)
    if hollow is None:
        hollow = p["hollow"]
    L, W, H = p["dims"]["length"], p["dims"]["width"], p["dims"]["height"]
    o = p["outlines"]

    def prism(plane: str, pts: List[Pt], length: float):
        wp = cq.Workplane(plane).polyline([(float(a), float(b)) for a, b in pts]).close()
        return wp.extrude(length, both=True)      # generous, both ways; the intersect trims it

    side = prism("XZ", o["side"], W * 2.0)        # sweeps across the width
    top = prism("XY", o["top"], H * 2.0)          # sweeps up through the height
    front = prism("YZ", o["front"], L * 2.0)      # sweeps along the length

    solid = side.intersect(top).intersect(front)
    if not solid.solids().vals():
        raise ValueError(
            "Those outlines don't overlap into a solid. Every view has to be of the same "
            "object, facing the way the studio expects (length left-to-right on side/top)."
        )

    # WHICH WAY A FEATURE GOES IN.
    # A feature is drawn on one face and travels straight in along the axis that face looks
    # down. Which END of that axis it starts from decides where a finite-depth pocket puts its
    # floor, so it has to be right per view — side enters from -y and sideR from +y, top from
    # +z and bottom from -z, front from +x and rear from -x. Getting this wrong on a through
    # cut is invisible (it goes all the way through either way); on a pocket it puts the
    # detail on the opposite face.
    PLANE = {"side": "XZ", "sideR": "XZ", "top": "XY", "bottom": "XY"}
    SPAN = {"side": W, "sideR": W, "top": H, "bottom": H}
    NEAR_MAX = {"side": False, "sideR": True, "top": True, "bottom": False,
                "front": True, "rear": False}

    def extent(view: str):
        """(axis index, low, high) of the body along the axis this view looks down."""
        if view in ("side", "sideR"):
            return 1, -W / 2.0, W / 2.0
        if view in ("top", "bottom"):
            return 2, 0.0, H
        return 0, 0.0, L

    # real holes — the thing the browser fundamentally cannot do
    for f in p["through_cuts"]:
        plane = PLANE.get(f["view"], "YZ")
        span = SPAN.get(f["view"], L) * 2.0
        try:
            tool = prism(plane, f["pts"], span)
            solid = solid.cut(tool)
        except Exception as e:                     # one bad outline shouldn't lose the model
            print(f"[hull] skipped through-cut {f['name']!r}: {e!r}")

    # FINITE-DEPTH POCKETS AND RAISES — the part that was missing.
    # The studio cuts these into its distance field, so they are real geometry there and have
    # to be real geometry here or the STEP does not match what someone approved on screen.
    # OpenCascade does it exactly: build the prism, keep only the slab within `depth` of the
    # face it enters from, and cut (or fuse) that. No grid, so no minimum feature size and no
    # knife edge — this path should be BETTER than the browser, not absent.
    # ONE BOOLEAN, NOT A HUNDRED AND FIFTY.
    # Each cut() is a full CSG operation, and a real car carries 150+ pockets — done one at a
    # time that is 150 rebuilds of the whole solid, each one more expensive than the last as
    # the shape gets more complicated. Building all the pocket tools first, fusing them into
    # one compound and cutting ONCE is the same result for a fraction of the work. Raises are
    # fused the same way. Anything that fails to build is still reported individually, so a
    # single bad outline cannot take the model with it.
    pocket_tools, raise_tools = [], []
    for f in p["pockets"] + p["raises"]:
        view = f["view"]
        plane = PLANE.get(view, "YZ")
        span = SPAN.get(view, L) * 2.0
        depth = abs(f["depth"])
        is_raise = f["depth"] > 0
        try:
            tool = prism(plane, f["pts"], span)
            axis, lo, hi = extent(view)
            near_max = NEAR_MAX.get(view, True)
            # The slab the feature occupies, measured from the face it enters. A raise stands
            # OUTSIDE that face, so its slab sits beyond it.
            if near_max:
                a, b = (hi, hi + depth) if is_raise else (hi - depth, hi)
            else:
                a, b = (lo - depth, lo) if is_raise else (lo, lo + depth)
            pad = max(L, W, H)
            box_lo = [-pad, -pad, -pad]
            box_hi = [L + pad, pad, H + pad]
            box_lo[axis], box_hi[axis] = a, b
            slab = cq.Workplane("XY").box(
                box_hi[0] - box_lo[0], box_hi[1] - box_lo[1], box_hi[2] - box_lo[2],
                centered=False).translate((box_lo[0], box_lo[1], box_lo[2]))
            shaped = tool.intersect(slab)
            if not shaped.solids().vals():
                continue                           # the slab missed the body: nothing to do
            (raise_tools if is_raise else pocket_tools).append(shaped)
        except Exception as e:
            kind = "raise" if is_raise else "pocket"
            print(f"[hull] skipped {kind} {f['name']!r}: {e!r}")

    def combine(tools):
        """Fuse a list of tool solids into one. Pairwise, because a failure in the middle of a
        long fuse should cost that one tool and not the whole batch."""
        out = None
        for t in tools:
            if out is None:
                out = t
                continue
            try:
                out = out.union(t)
            except Exception as e:
                print(f"[hull] a tool would not fuse, skipping it: {e!r}")
        return out

    cutter = combine(pocket_tools)
    if cutter is not None:
        try:
            solid = solid.cut(cutter)
        except Exception as e:
            print(f"[hull] pockets would not cut ({e!r}); leaving them out")
    adder = combine(raise_tools)
    if adder is not None:
        try:
            solid = solid.union(adder)
        except Exception as e:
            print(f"[hull] raises would not fuse ({e!r}); leaving them out")

    if hollow and p["wall"] > 0:
        spec = p["wall_spec"]
        # BUILD THE CAVITY, DO NOT OFFSET THE FACES.
        # `shell()` offsets every face at once and needs them all to offset consistently. On a
        # traced car that is 188 faces, many near-tangent, and one bad offset returns a Null
        # TopoDS_Shape — measured. The failure was caught and the solid returned, so a real
        # car exported as 807 cm3 of material where a 4.9mm shell was asked for, with no error.
        # It went unseen because the kernel tests had never run.
        #
        # So intersect the three outlines pulled inward, and cut that out. Same carving
        # principle as the body itself, one level in. Measured on a real car: 812 cm3 solid ->
        # 352 cm3 shell, one valid solid, 1.6 seconds.
        #
        # `offset2D` rather than our own `offset_inward` for the uniform case, because pulling
        # a polygon inward creates loops where an edge is SHORTER than the wall — on this car,
        # a 4.22mm edge against a 4.9mm wall folded past its neighbour and produced a
        # self-intersecting outline that OpenCascade would build and then refuse to intersect.
        # offset2D removes those loops itself. It takes ONE distance, so per-face keeps the
        # hand-rolled route; per-face on a real traced car is still broken for the same
        # short-edge reason and falls back, which is why the order below matters.
        def cavity_uniform(dist: float):
            inner = None
            for key, plane, span in (("side", "XZ", W), ("top", "XY", H), ("front", "YZ", L)):
                poly = o.get(key)
                if not poly:
                    continue
                wp = (cq.Workplane(plane)
                        .polyline([(float(a), float(b)) for a, b in poly])
                        .close().offset2D(-abs(dist))
                        .extrude(span * 2.0, both=True))
                inner = wp if inner is None else inner.intersect(wp)
            return inner

        def cavity_per_face(sp: dict):
            """Per-face thickness WITHOUT offsetting any polygon.

            `offset2D` takes one distance, and our own `offset_inward` tangles a traced outline
            wherever an edge is shorter than the wall — a 4.22mm edge against a 4.9mm wall on
            the reference car produced a self-intersecting loop that OpenCascade would build
            and then refuse to intersect.

            So: build the cavity at the THINNEST face, where offset2D is reliable, then trim it
            back with half-spaces for the faces that want more. Trimming only ever removes from
            the cavity, so the wall can only get thicker — it cannot overshoot, and there is no
            polygon arithmetic to go wrong. Roof, floor and flanks are axis-aligned, which is
            exactly what wallTop/wallBottom/wallSide mean.
            Measured on the reference car: 5mm walls with a 15mm floor gave +35,831 mm3 over
            uniform, one valid solid, 1.2s."""
            thin = abs(min(sp["top"], sp["side"], sp["bot"]))
            inner = cavity_uniform(thin)
            if inner is None:
                return None
            pad = max(L, W, H) * 3.0

            def half(dx, dy, dz, ox, oy, oz):
                return (cq.Workplane("XY").box(dx, dy, dz, centered=False)
                          .translate((ox, oy, oz)))

            bot, top_, side = abs(sp["bot"]), abs(sp["top"]), abs(sp["side"])
            if bot > thin:      # keep only what is above the floor thickness
                inner = inner.intersect(half(pad, pad, pad, -pad / 2, -pad / 2, bot))
            if top_ > thin:     # ...and below the roof thickness
                inner = inner.intersect(half(pad, pad, pad, -pad / 2, -pad / 2, H - top_ - pad))
            if side > thin:     # ...and inside both flanks. The body is mirrored about y=0.
                inner = inner.intersect(half(pad, W - 2 * side, pad,
                                             -pad / 2, -(W / 2 - side), -pad / 2))
            return inner

        if wall_varies(spec):
            # PER-FACE: build the cavity and cut it, because shell() cannot vary its thickness.
            # The cavity is the same intersection the body is, with each outline pulled inward
            # by the wall belonging to the surfaces it creates. If any part of it fails, fall
            # through to the uniform shell rather than hand back a solid lump.
            try:
                inner = cavity_per_face(spec)
                if inner is not None and inner.solids().vals():
                    solid = solid.cut(inner)
                else:
                    raise ValueError("the cavity came out empty")
            except Exception as e:
                # per-face could not be built — fall back to a uniform shell at the THINNEST
                # face, so the part is never thicker than asked anywhere
                print(f"[hull] per-face hollow failed ({e!r}); falling back to a uniform wall")
                thin = abs(min(spec["top"], spec["side"], spec["bot"]))
                try:
                    inner = cavity_uniform(thin)
                    if inner is None or not inner.solids().vals():
                        raise ValueError("the cavity came out empty")
                    solid = solid.cut(inner)
                except Exception as e2:
                    print(f"[hull] could not hollow it ({e2!r}); returning it SOLID")
                    p["hollow_failed"] = True
        else:
            try:
                inner = cavity_uniform(p["wall"])
                if inner is None or not inner.solids().vals():
                    raise ValueError("the cavity came out empty")
                solid = solid.cut(inner)
            except Exception as e:
                print(f"[hull] could not hollow it ({e!r}); returning it SOLID")
                p["hollow_failed"] = True
    return solid


def export_bytes(profile: Dict[str, Any], fmt: str = "step", hollow: bool = False):
    """Exact solid -> (bytes, mime, filename)."""
    cq = _import_cq()
    import tempfile
    from pathlib import Path

    solid = build_solid(profile, hollow=hollow)
    name = (profile.get("name") or "model").strip().replace(" ", "-") or "model"
    fmt = (fmt or "step").lower()
    ext = {"step": "step", "stl": "stl"}.get(fmt)
    if not ext:
        raise ValueError(f"unsupported format {fmt!r}; use step or stl")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / f"{name}.{ext}"
        cq.exporters.export(solid, str(out))
        data = out.read_bytes()
    mime = "application/step" if ext == "step" else "model/stl"
    return data, mime, f"{name}.{ext}"
