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
    if view == "side":
        pts = [(u * L, v * H) for u, v in poly]
    elif view == "top":
        pts = [(u * L, v * W - W / 2.0) for u, v in poly]
    elif view == "bottom":
        pts = [(u * L, v * W - W / 2.0) for u, v in poly]
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


def plan(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Everything the exact build is going to do, worked out without touching OpenCascade.
    Handy for testing, and for telling someone what they're about to get.
    """
    L, W, H = dims(profile)
    o = outlines_mm(profile)
    feats = [f for f in (feature_mm(x, L, W, H) for x in (profile.get("features") or [])) if f]
    cuts = [f for f in feats if f["through"] and f["depth"] < 0]
    skipped = [f for f in feats if not (f["through"] and f["depth"] < 0)]
    return {
        "dims": {"length": L, "width": W, "height": H},
        "outlines": o,
        "through_cuts": cuts,
        "surface_only": skipped,      # dishes/bosses: the browser already does these
        "hollow": bool(profile.get("sepBottom")) is False and float(profile.get("wallThickness") or 0) > 0,
        "wall": float(profile.get("wallThickness") or 1.8),
    }


# --------------------------------------------------------------------------------------
# The exact build. Needs OpenCascade.
# --------------------------------------------------------------------------------------
def build_solid(profile: Dict[str, Any], hollow: bool = False):
    """
    Three traced outlines -> one exact solid.

    The visual hull is literally the intersection of the three outlines extruded through
    each other. The browser approximates that on a grid; OpenCascade just computes it, so
    corners are corners and curves are curves at any zoom.
    """
    cq = _import_cq()
    p = plan(profile)
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

    # real holes — the thing the browser fundamentally cannot do
    for f in p["through_cuts"]:
        plane = {"side": "XZ", "top": "XY", "bottom": "XY"}.get(f["view"], "YZ")
        span = {"side": W, "top": H, "bottom": H}.get(f["view"], L) * 2.0
        try:
            tool = prism(plane, f["pts"], span)
            solid = solid.cut(tool)
        except Exception as e:                     # one bad outline shouldn't lose the model
            print(f"[hull] skipped through-cut {f['name']!r}: {e!r}")

    if hollow and p["wall"] > 0:
        try:
            solid = solid.shell(-abs(p["wall"]))   # negative = inward, keeps outside size
        except Exception as e:
            print(f"[hull] could not hollow it ({e!r}); returning it solid")
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
