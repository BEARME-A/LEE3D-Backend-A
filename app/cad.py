"""
Production body generator (CadQuery + OpenCascade).

This is the "grown-up" version of the loft the browser does in JS. Same Profile
in, but here we get a real B-rep kernel: lofted solid -> open-bottom thin shell
-> true boolean-cut wheel openings -> STL *and* STEP (so the friend can open it
in any CAD package and keep editing).

cadquery is heavy (OpenCascade). We import it lazily and raise a clean,
actionable error if the environment isn't set up, so `uvicorn app.main:app`
still starts and serves the rest of the API.
"""
from __future__ import annotations
import math
import tempfile
from pathlib import Path
from typing import List, Tuple

from .schemas import Profile, GenerateOptions


class CadUnavailable(RuntimeError):
    pass


def _import_cq():
    try:
        import cadquery as cq  # noqa
        return cq
    except Exception as e:  # pragma: no cover - depends on environment
        raise CadUnavailable(
            "CadQuery/OpenCascade is not importable in this environment. "
            "Install it with conda: `conda env create -f environment.yml` "
            "(see README), then restart the server. Original error: " + repr(e)
        )


# ---- piecewise-linear sampler (matches the frontend exactly) ----
def _sample(points: List[List[float]], xf: float) -> float:
    if not points:
        return 0.0
    if len(points) == 1:
        return points[0][1]
    if xf <= points[0][0]:
        return points[0][1]
    if xf >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= xf <= x1:
            t = 0.0 if x1 == x0 else (xf - x0) / (x1 - x0)
            return y0 + (y1 - y0) * t
    return points[-1][1]


def _section_points(halfW: float, zc: float, halfH: float,
                    m: int, style: str, exponent: float):
    """One closed cross-section in the Y-Z plane, returned as (y, z) samples."""
    pts = []
    n = max(1.2, exponent)
    for k in range(m):
        th = 2.0 * math.pi * k / m
        c, s = math.cos(th), math.sin(th)
        if style == "ellipse":
            y = halfW * c
            z = zc + halfH * s
        else:  # superellipse -> flatter floor + roof, more car-like
            y = halfW * math.copysign(abs(c) ** (2.0 / n), c)
            z = zc + halfH * math.copysign(abs(s) ** (2.0 / n), s)
        pts.append((y, z))
    return pts


def build_solid(profile: Profile, options: GenerateOptions):
    """Return a CadQuery Workplane containing the finished body."""
    cq = _import_cq()
    from cadquery import Vector, Wire, Solid, Workplane

    L = profile.length
    N = max(8, profile.stations)
    M = max(12, profile.arcSegments)

    wires = []
    max_halfW = 0.0
    for i in range(N + 1):
        xf = i / N
        x = (xf - 0.5) * L
        zTop = _sample(profile.topProfile, xf)
        zBot = _sample(profile.bottomProfile, xf)
        halfW = max(0.4, _sample(profile.widthProfile, xf))
        max_halfW = max(max_halfW, halfW)
        zc = 0.5 * (zTop + zBot)
        halfH = max(0.4, 0.5 * (zTop - zBot))
        sec = _section_points(halfW, zc, halfH, M, options.section, profile.roofFlatness)
        verts = [Vector(x, y, z) for (y, z) in sec]
        wires.append(Wire.makePolygon(verts, close=True))

    # ---- loft the sections into a solid ----
    solid = Solid.makeLoft(wires, ruled=False)
    body = Workplane(obj=solid)

    # ---- open-bottom thin shell (a printable body shell) ----
    if options.open_bottom and profile.wallThickness > 0:
        t = profile.wallThickness
        try:
            body = body.faces("<Z").shell(-t)            # remove the underside, hollow inward
        except Exception:
            try:
                body = Workplane(obj=solid).shell(-t)     # fallback: closed hollow shell
            except Exception:
                body = Workplane(obj=solid)               # last resort: solid (slicer can hollow)

    # ---- true wheel openings via boolean cut (axis along Y, through the width) ----
    if options.cut_wheels and profile.wheels:
        through = (max_halfW * 2.0) + 60.0
        for w in profile.wheels:
            cutter = Solid.makeCylinder(
                w.r, through,
                pnt=Vector(w.x, -through / 2.0, w.z),
                dir=Vector(0, 1, 0),
            )
            try:
                body = body.cut(Workplane(obj=cutter))
            except Exception:
                pass  # skip a cutter that fails rather than killing the whole job

    return body


def generate_bytes(profile: Profile, options: GenerateOptions) -> Tuple[bytes, str, str]:
    """Generate and return (file_bytes, mime_type, filename)."""
    cq = _import_cq()
    body = build_solid(profile, options)

    suffix = ".step" if options.fmt == "step" else ".stl"
    mime = "model/step" if options.fmt == "step" else "model/stl"
    name = (profile.name or "body").replace(" ", "_") + suffix

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / ("body" + suffix)
        if options.fmt == "step":
            cq.exporters.export(body, str(out), exportType="STEP")
        else:
            # ascii=False -> binary STL; tolerance tuned for printable smoothness
            cq.exporters.export(body, str(out), tolerance=0.05, angularTolerance=0.1)
        data = out.read_bytes()
    return data, mime, name
