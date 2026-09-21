"""
PDF -> traceable page images (PyMuPDF / fitz).

Engineers hand you PDFs. This renders each page to a PNG (so a scanned or vector
side-view can be traced in the UI) and reports any embedded raster images and
vector path counts, which is a hint about whether a page holds a real drawing.
"""
from __future__ import annotations
import base64
import re
from typing import Dict, List, Optional


class PdfUnavailable(RuntimeError):
    pass


def _fitz():
    try:
        import fitz  # PyMuPDF
        return fitz
    except Exception as e:  # pragma: no cover
        raise PdfUnavailable(
            "PyMuPDF not importable. `pip install pymupdf`. Original error: " + repr(e)
        )


def render_pages(pdf_bytes: bytes, dpi: int = 150, max_pages: int = 30) -> Dict:
    fitz = _fitz()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: List[Dict] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png = pix.tobytes("png")
        try:
            vectors = len(page.get_drawings())
        except Exception:
            vectors = 0
        rasters = len(page.get_images(full=True))
        pages.append({
            "index": i,
            "width": pix.width,
            "height": pix.height,
            "vector_paths": vectors,
            "raster_images": rasters,
            "png_base64": base64.b64encode(png).decode("ascii"),
        })

    return {"page_count": doc.page_count, "rendered": len(pages), "pages": pages}


# ---------------------------------------------------------------------------------------
# A PLOTTED PDF IS NOT A PICTURE.
# render_pages above rasterises, which is right for showing someone a page and wrong for
# everything else: a drawing exported from CAD — or from any of the blueprint sites a PM
# actually downloads from — carries its line work as real paths and its dimension callouts
# as real text with real coordinates. Rasterising it and reading the pixels back throws
# away geometry that is exact and numbers that are already machine-readable. It even
# counted the paths (`vector_paths`) and then discarded them.
#
# So: hand back the geometry. Strokes come out as polylines in millimetres on the page,
# with y measured upward the way a drawing is read rather than downward the way a page is
# painted, which is the same frame the DXF stitcher already works in. Text comes back with
# its position, so a height callout can be matched to the region it labels — no OCR, because
# there is nothing to recognise; the characters are in the file.
# ---------------------------------------------------------------------------------------

PT_MM = 25.4 / 72.0          # PDF user space is points, and a point is exactly 1/72 inch


def _bezier(p0, p1, p2, p3, steps: int = 12):
    """A cubic flattened to line segments. Curves are most of a site plan — kerb returns,
    roundabouts, planting beds — so dropping them would lose the drawing."""
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1.0 - t
        out.append((
            u*u*u*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t*t*t*p3[0],
            u*u*u*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t*t*t*p3[1],
        ))
    return out


def extract_geometry(pdf_bytes: bytes, page_index: int = 0, curve_steps: int = 12) -> Dict:
    """Line work, callouts and page size from one page of a plotted PDF."""
    fitz = _fitz()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_index < 0 or page_index >= doc.page_count:
        raise ValueError(f"page {page_index} is outside this {doc.page_count}-page document")
    page = doc[page_index]
    # FLIP y USING THE UNROTATED HEIGHT. `page.rect` is the ROTATED rectangle, but both
    # `get_drawings()` and `get_text()` report in UNROTATED page space — measured on this set,
    # where every sheet carries rotation 270: rect is 3024x2160 while the coordinates run to
    # 2106x2999, which is the mediabox. Using rect.height flipped against 2160 instead of 3024
    # and put every y out by 864pt — 304.8mm — with many going negative.
    #
    # Nothing RELATIVE noticed: lengths, spans, proximity and framing are all invariant to a
    # uniform shift, which is why dimensions linked at 0.00% error throughout. It surfaced only
    # when a crop had to be handed back to PDF space, where absolute position matters.
    h_pt = page.rect.height if page.rotation in (0, 180) else page.rect.width
    mm = lambda x, y: (x * PT_MM, (h_pt - y) * PT_MM)

    strokes: List[List] = []
    for path in page.get_drawings():
        run: List = []

        def flush():
            if len(run) > 1:
                strokes.append([list(p) for p in run])
            run.clear()

        for it in path["items"]:
            kind = it[0]
            if kind == "l":
                a, b = mm(it[1].x, it[1].y), mm(it[2].x, it[2].y)
                if run and run[-1] == list(a):
                    run.append(list(b))
                else:
                    flush(); run.extend([list(a), list(b)])
            elif kind == "c":
                pts = [mm(p.x, p.y) for p in (it[1], it[2], it[3], it[4])]
                if not run or run[-1] != list(pts[0]):
                    flush(); run.append(list(pts[0]))
                run.extend([list(p) for p in _bezier(*pts, steps=curve_steps)])
            elif kind == "re":
                r = it[1]
                corners = [mm(r.x0, r.y0), mm(r.x1, r.y0), mm(r.x1, r.y1), mm(r.x0, r.y1)]
                flush(); strokes.append([list(p) for p in corners] + [list(corners[0])])
            elif kind == "qu":
                q = it[1]
                pts = [mm(p.x, p.y) for p in (q.ul, q.ur, q.lr, q.ll)]
                flush(); strokes.append([list(p) for p in pts] + [list(pts[0])])
        flush()

    words = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        a, b = mm(x0, y1), mm(x1, y0)             # y flips, so the corners swap
        words.append({"text": text, "x": (a[0] + b[0]) / 2.0, "y": (a[1] + b[1]) / 2.0,
                      "box": [a[0], a[1], b[0], b[1]]})

    return {
        "page": page_index,
        "page_count": doc.page_count,
        "page_mm": [page.rect.width * PT_MM, h_pt * PT_MM],
        "strokes": strokes,
        "words": words,
        "plot_scale": detect_plot_scale(words),
        "numbers": [w for w in words if _is_number(w["text"])],
    }


def _is_number(t: str) -> bool:
    t = t.strip().strip("()").replace(",", "")
    if not t:
        return False
    try:
        float(t.lstrip("+-"))
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------------------------------
# IMPERIAL. American construction documents are dimensioned in feet and inches and scaled
# architecturally — 1/4" = 1'-0", not 1:48 — and none of the metric reading below sees any of
# it. Dylan's set is entirely imperial: 4'-0" columns, a 12'-4" height, sheets at 1"=20'-0",
# 1/4"=1'-0", 3/8"=1'-0" and 1/8"=1'-0". Read from the sheet rather than typed in again,
# for the same reason the metric ratio is: the drawing is the document, and retyping a
# dimension is one more chance to disagree with it.
# ----------------------------------------------------------------------------------------
_VULGAR = {"¼": 0.25, "½": 0.5, "¾": 0.75, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
           "⅓": 1/3, "⅔": 2/3}
MM_PER_IN = 25.4

_INCH_RE = re.compile(
    r"^\s*(?:(?P<whole>\d+(?:\.\d+)?)\s*)?"          # 4, or the 1 in 1-1/2 and in 1¾
    r"(?:[-\s]\s*)?"
    r"(?:(?P<num>\d+)\s*/\s*(?P<den>\d+))?"          # 1/2, 3/8
    r"\s*(?P<vul>[¼½¾⅛⅜⅝⅞⅓⅔])?\s*$")                 # ¾ — comes AFTER the whole number


def _inches(text: str) -> Optional[float]:
    """The inch part of a dimension: 4, 1-1/2, 3/8, 1¾, 10, or empty.

    Split out from the feet rather than matched in one pattern, because a vulgar fraction sits
    AFTER its whole number (1¾) while a written fraction sits after a hyphen (1-1/2), and one
    regex trying to hold both orderings silently failed on 42'-1¾" — a real dimension off the
    wayfinding sign detail.
    """
    t = (text or "").strip().rstrip('"').strip()
    if t == "":
        return 0.0
    m = _INCH_RE.match(t)
    if not m:
        return None
    g = m.groupdict()
    if not any(g.values()):
        return None
    v = float(g["whole"]) if g["whole"] else 0.0
    if g["num"] and g["den"] and float(g["den"]) != 0:
        v += float(g["num"]) / float(g["den"])
    if g["vul"]:
        v += _VULGAR[g["vul"]]
    return v


def parse_feet_inches(text: str) -> Optional[float]:
    """A dimension as written on an American drawing, in MILLIMETRES.

    Handles 4'-0", 12'-4", 2'-10", 7", 1/2", 3/8", 1-1/2", 4-1/2" and the vulgar fractions a
    CAD title block emits (42'-1¾"). Returns None rather than a guess for anything it does not
    recognise, because a wrong dimension read confidently is worse than none — it gets built.
    """
    if text is None:
        return None
    t = str(text).strip().replace("’", "'").replace("”", '"')
    if not t or t in ("'", '"', "-"):
        return None
    ft = 0.0
    if "'" in t:
        head, _, tail = t.partition("'")
        head = head.strip()
        try:
            ft = float(head)
        except ValueError:
            return None
        rest = tail.strip().lstrip("-").strip()
    else:
        rest = t
        if not any(c.isdigit() for c in rest):
            return None
    inches = _inches(rest)
    if inches is None:
        return None
    return round((ft * 12.0 + inches) * MM_PER_IN, 6)


# The ratios a drawing is actually plotted at. Architectural: 3"=1'-0" down to 1/32"=1'-0".
# Engineering: 1"=10' through 1"=100'. Plus the metric ratios that appear on the same sheets.
_STANDARD_SCALES = (1, 2, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 384,
                    120, 240, 360, 480, 600, 720, 1200,
                    5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000)

_ARCH_SCALE_RE = re.compile(r"^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$")


def parse_arch_scale(text: str, standard_only: bool = True) -> Optional[float]:
    """An architectural scale as printed — 1/4" = 1'-0" — as a plain ratio denominator.

    1/4" = 1'-0"  ->  48       one paper inch stands for four real feet
    1"   = 20'-0" ->  240
    3/8" = 1'-0"  ->  32
    1/8" = 1'-0"  ->  96

    Same units both sides, so the ratio is just real over paper. Returned in the SAME form as
    the metric reader's, so a caller never has to know which notation the sheet used.
    """
    if not text:
        return None
    t = str(text).strip()
    for lead in ("SCALE:", "SCALE"):
        if t.upper().startswith(lead):
            t = t[len(lead):].strip()
    m = _ARCH_SCALE_RE.match(t)
    if not m:
        return None
    paper = parse_feet_inches(m.group("lhs"))
    real = parse_feet_inches(m.group("rhs"))
    if not paper or not real or paper <= 0 or real <= 0:
        return None
    ratio = real / paper
    if not (1.0 <= ratio <= 20000.0):
        return None
    ratio = round(ratio, 6)
    if not standard_only:
        return ratio
    # ONLY A SCALE SOMEONE ACTUALLY DRAWS AT. Found on the real L406: a detail bubble number
    # sitting just before its scale text gets swallowed by the span search, so `1/4" = 1'-0"`
    # preceded by the bubble "1" reads as `1 1/4" = 1'-0"` — a valid-LOOKING 1:9.6. The bubbles
    # 2 and 3 gave 1:5.33 and 1:3.69 the same way. Every one of those is a scale no drafter
    # uses, and requiring a standard ratio rejects all three while keeping every real one.
    best = min(_STANDARD_SCALES, key=lambda c: abs(c - ratio))
    return float(best) if abs(best - ratio) <= max(0.01, best * 0.002) else None


_SCALE_RE = re.compile(r"^1\s*[:/]\s*(\d{1,6})$")


def detect_plot_scale(words) -> Optional[float]:
    """The ratio printed on the sheet — 1:200 means a millimetre of paper is 200 real ones.

    Read rather than asked for, because it is written on the drawing and typing it again is
    one more chance to disagree with the document. A sheet with two different ratios on it
    (a plan and a blown-up detail) is genuinely ambiguous, so return nothing and ask instead
    of picking one; guessing here is wrong by whole multiples.
    """
    found = set()
    for i, w in enumerate(words):
        m = _SCALE_RE.match(w["text"].strip())
        if m:
            found.add(int(m.group(1)))
            continue
        # ARCHITECTURAL, e.g. 1/4" = 1'-0". A word run may hold the whole thing or just the
        # start of it, so try this word and the few after it — a plotted sheet breaks
        # `1/4" = 1'-0"` into separate runs as readily as it breaks `SCALE 1 : 200`.
        for span in (1, 2, 3, 4, 5):
            a = parse_arch_scale(" ".join(x["text"] for x in words[i:i + span]))
            if a:
                found.add(int(round(a)))
                break
        # "SCALE 1 : 200" arrives as separate runs
        if w["text"].strip().upper() in ("SCALE", "SCALE:"):
            tail = "".join(x["text"] for x in words[i + 1:i + 4])
            m2 = _SCALE_RE.match(tail.strip())
            if m2:
                found.add(int(m2.group(1)))
            else:
                a = parse_arch_scale(tail)
                if a:
                    found.add(int(round(a)))
    return float(found.pop()) if len(found) == 1 else None


# ----------------------------------------------------------------------------------------
# LINKING A DIMENSION TO WHAT IT DIMENSIONS.
#
# `extract_geometry` gives the line work and `parse_feet_inches` gives the number, and until
# now nothing said WHICH line the 4'-0" belonged to. A dimension in CAD is not one object: it
# is two witness lines, a dimension line between them, and a text run near its middle. There
# is no marker in the file saying they belong together.
#
# **The link is arithmetic, not proximity.** A dimension line drawn L millimetres on paper at
# a scale of 1:S measures L*S in the real world, and the text beside it says what that is. So
# a candidate is only accepted when the drawn length AGREES with the written number. That is
# a check, not a guess: proximity alone would happily pair a 4'-0" with whatever line happened
# to be nearest, and on a dense sheet that is often the wrong one.
#
# It also runs backwards. Given enough dimensions, the scale that makes the most of them agree
# with their own line work IS the scale — read from the drawing's internal consistency rather
# than from a title block that may be missing, wrong, or belong to a different detail on the
# same sheet.
# ----------------------------------------------------------------------------------------
def _seg_len(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _polyline_len(pts) -> float:
    return sum(_seg_len(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def link_dimensions(strokes, words, scale: float, tol: float = 0.02,
                    search_mm: float = 25.0) -> List[Dict]:
    """Pair each written dimension with the stroke whose drawn length agrees with it.

    `scale` is the plot ratio: 48 for 1/4"=1'-0". A stroke of L mm on paper stands for L*scale
    mm of building, and a dimension text is accepted against that stroke only when the two
    agree to within `tol` (2% by default — a plotted line is not exact, and a dimension may be
    rounded to the nearest inch on the sheet).

    **`search_mm` IS NOT COSMETIC — it is what makes the length check mean anything.** It began
    at 40mm, which sounds tight until you meet a real sheet: L404 of Dylan's set carries 59,794
    strokes, and within 40mm of any dimension text there is a stroke of very nearly the right
    length AT ALMOST ANY SCALE. Measured on that page, sweeping candidate scales:

        search 40 mm -> true 1:48 wins 126 to 121.  A 4% lead. Right answer, barely.
        search 15 mm -> 76 to 32.    lead 138%
        search  8 mm -> 59 to 14.    lead 321%
        search  4 mm -> 42 to 4.     lead 950%

    **But the right radius differs by job, so the two callers no longer share one.** When the
    scale is KNOWN the length check is already doing the work and a generous radius simply
    finds more true dimensions — tightening to 12mm cost page L201B more than half of them,
    26 matches down to 10, for no gain. When the scale is being GUESSED there is no length
    check yet, only a comparison between candidates, and then the radius is the entire
    discriminator. So `link_dimensions` keeps 25mm and `infer_plot_scale` passes 8mm itself.

    **Match QUALITY does not rescue a loose radius** — at 40mm the WRONG candidate 1:200 had a
    lower mean error AND more sub-0.2% matches than the true scale. Only proximity separates
    them, which is worth knowing before anyone tries to score these by how well they fit.

    Returns one entry per dimension text that found a match, carrying the error so a caller can
    see HOW well it agreed rather than only that it did. Unmatched dimensions are simply absent:
    a dimension whose line cannot be found is not a dimension anyone should build from.
    """
    if not scale or scale <= 0:
        return []
    lens = [(_polyline_len(s), s) for s in strokes if len(s) > 1]
    out: List[Dict] = []
    for w in words or []:
        mm = parse_feet_inches(w.get("text", ""))
        if not mm or mm <= 0:
            continue
        want_paper = mm / scale
        best = None
        for i, (paper, s) in enumerate(lens):
            if paper <= 1e-9:
                continue
            err = abs(paper - want_paper) / want_paper
            if err > tol:
                continue
            mid = ((s[0][0] + s[-1][0]) / 2.0, (s[0][1] + s[-1][1]) / 2.0)
            dist = _seg_len((w.get("x", 0.0), w.get("y", 0.0)), mid)
            if dist > search_mm:
                continue
            if best is None or (err, dist) < (best["error"], best["distance"]):
                best = {"text": w.get("text", ""), "mm": mm, "stroke": i,
                        "paper_mm": paper, "error": err, "distance": dist}
        if best:
            out.append(best)
    return out


def infer_plot_scale(strokes, words, candidates=None, min_matches: int = 3,
                     min_lead: float = 1.5):
    """The scale the drawing's own dimensions agree with, or None.

    A title block can be missing, wrong, or belong to a different detail on the same sheet.
    The line work cannot: if most written dimensions agree with the lengths actually drawn at
    some ratio, that ratio is the scale. Tried against the architectural and metric ratios that
    appear on real sheets.

    Returns None unless one candidate is clearly best — a tie means the evidence does not
    decide, and picking one is wrong by whole multiples. Same refusal `detect_plot_scale` makes
    when a sheet carries two ratios.

    "Clearly best" is a LEAD, not a win. On a dense sheet the runner-up is a pile of
    coincidences, and a 4% margin over a coincidence is not evidence — measured at 126 to 121
    on a real sheet before the search radius was tightened. `min_lead` is the ratio the best
    must beat the runner-up by.
    """
    if candidates is None:
        candidates = [12, 16, 24, 32, 48, 64, 96, 120, 192, 240, 384, 480,   # imperial
                      10, 20, 25, 50, 100, 200, 250, 500, 1000]              # metric
    scored = []
    for c in candidates:
        # 8mm, not the linking default: with the scale unknown, proximity is the only thing
        # separating the true ratio from a pile of coincidences on a dense sheet.
        n = len(link_dimensions(strokes, words, float(c), search_mm=8.0))
        if n:
            scored.append((n, c))
    if not scored:
        return None
    scored.sort(reverse=True)
    best_n, best_c = scored[0]
    if best_n < min_matches:
        return None
    if len(scored) > 1 and best_n < scored[1][0] * min_lead:
        return None                     # a narrow win over a coincidence is not evidence
    return float(best_c)


# ----------------------------------------------------------------------------------------
# THE SURVEY SCHEDULE. A NORTHING/EASTING POINT SCHEDULE is placement data: it says where each
# column, wall centreline and sign stands, to four decimals of a foot. Dimensions say how big
# a thing is; only the schedule says WHERE it goes, and typing ten coordinates at four decimals
# by hand is exactly the transcription this importer exists to remove.
#
# **THE TABLE MAY BE ROTATED, AND ON A REAL SHEET IT WAS.** On L201B of the Saratoga Springs
# set every one of the ten eastings shares a single y and has its own x: what a reader sees as
# rows running down the page are, in page coordinates, columns running across it. A landscape
# sheet rotates its schedules as readily as its title block. So the axis is not assumed — both
# are tried, and the one that yields more COMPLETE records wins. A record is complete only with
# both a northing and an easting, which is what makes that test meaningful rather than circular.
# ----------------------------------------------------------------------------------------
_COORD_RE = re.compile(r"^([NE])\s*(\d{3,9}(?:\.\d+)?)$", re.IGNORECASE)
_BARE_COORD_RE = re.compile(r"^\d{3,9}(?:\.\d+)?$")


def _bands(words, axis: str, tol: float = 2.0):
    """Group word runs into bands sharing a position on one axis.

    A PDF has no rows. A table is a table only because its cells share a baseline, so that
    baseline has to be reconstructed — along y for an upright table, along x for a rotated one.
    """
    key = (lambda w: w.get("y", 0.0)) if axis == "y" else (lambda w: w.get("x", 0.0))
    other = (lambda w: w.get("x", 0.0)) if axis == "y" else (lambda w: -w.get("y", 0.0))
    out: List[List[Dict]] = []
    for w in sorted(words or [], key=lambda w: (-key(w), other(w))):
        for band in out:
            if abs(key(band[0]) - key(w)) <= tol:
                band.append(w)
                break
        else:
            out.append([w])
    for band in out:
        band.sort(key=other)
    return out


def _pos(w, axis: str) -> float:
    """Where a word sits along the axis the band runs in."""
    return w.get("x", 0.0) if axis == "y" else -w.get("y", 0.0)


def _points_from_bands(bands, axis: str, gap_mm: float = 25.0) -> List[Dict]:
    out: List[Dict] = []
    for band in bands:
        northing = easting = None
        used = set()
        for i, w in enumerate(band):
            t = (w.get("text") or "").strip()
            m = _COORD_RE.match(t)
            if m:
                v = float(m.group(2))
                if m.group(1).upper() == "N" and northing is None:
                    northing = v; used.add(i)
                elif m.group(1).upper() == "E" and easting is None:
                    easting = v; used.add(i)
                continue
            if t.upper() in ("N", "E") and i + 1 < len(band):
                nxt = (band[i + 1].get("text") or "").strip()
                if _BARE_COORD_RE.match(nxt):
                    v = float(nxt)
                    if t.upper() == "N" and northing is None:
                        northing = v; used.update((i, i + 1))
                    elif t.upper() == "E" and easting is None:
                        easting = v; used.update((i, i + 1))
        if northing is None or easting is None:
            continue                     # half a coordinate is worse than none
        # KEEP ONLY THE RUN ADJACENT TO THE COORDINATES. A band spans the whole sheet, so it
        # sweeps in whatever else happens to share that line — on the real L201B the
        # descriptions came back carrying "CHECKED BY: DEP", "SHEET NUM" and a plot timestamp
        # from the title block, and one point lost its id to it. A schedule entry is a
        # CONTIGUOUS run: id, description, then the coordinates. So walk back from the first
        # coordinate while the words keep touching, and stop at the first real gap. Measured on
        # the real band for point 21: gaps WITHIN the record run 10-20mm, and the jump from the
        # easting to the title block'''s "L201B" is 38mm. 25mm sits between them. Walking
        # BACKWARD also drops the trailing title block for free — it is never visited.
        first = min(used)
        keep: List[int] = []
        prev = _pos(band[first], axis)
        for i in range(first - 1, -1, -1):
            here = _pos(band[i], axis)
            if abs(prev - here) > gap_mm:
                break
            keep.append(i)
            prev = here
        keep.reverse()
        head = [(band[i].get("text") or "").strip() for i in keep]
        pid = None
        if head and head[0].isdigit():
            pid = int(head[0]); head = head[1:]
        out.append({"id": pid, "description": " ".join(h for h in head if h).strip(),
                    "northing": northing, "easting": easting})
    return out


def parse_point_schedule(words) -> List[Dict]:
    """Survey points from a NORTHING/EASTING schedule: id, description, northing, easting.

    Read off whole bands rather than by scanning for numbers, because a sheet is covered in
    numbers — dimensions, radii, elevations, sheet references — and only the ones sharing a
    band with BOTH a northing and an easting are survey points. Requiring the pair is what
    keeps a dimension out of the placement data.
    """
    by_y = _points_from_bands(_bands(words, "y"), "y")
    by_x = _points_from_bands(_bands(words, "x"), "x")
    return by_x if len(by_x) > len(by_y) else by_y


# ----------------------------------------------------------------------------------------
# WHICH SHEET IS THIS? A drawing set cross-references itself constantly — the materials
# schedule points at "2/L403" meaning detail 2 on sheet L403, and a section marker points at
# another sheet entirely. None of that resolves without knowing which sheet you are holding.
#
# The sheet number is found by SIZE, not position. It is the largest text on the page matching
# a sheet pattern, because a title block prints it bigger than anything else on the sheet — and
# that holds whether the block sits bottom-right, is rotated with the sheet, or has been moved
# by whoever set the template up. Position rules break on a rotated title block; size does not.
# ----------------------------------------------------------------------------------------
_SHEET_NO_RE = re.compile(r"^[A-Z]{1,3}-?\d{2,4}[A-Z]?$")

# statuses a construction set prints on itself, longest first so the specific wins
_STATUS_PHRASES = ("FOR CONSTRUCTION", "CONSTRUCTION DOCUMENT SET", "BID/ PERMIT SET",
                   "BID/PERMIT SET", "PERMIT SET", "NOT FOR CONSTRUCTION")


def _text_height(w) -> float:
    b = w.get("box")
    return abs(b[3] - b[1]) if b and len(b) >= 4 else 0.0


def sheet_identity(words) -> Dict:
    """Sheet number and any printed status. Number by size; status by phrase.

    Returns None for anything it cannot find rather than a best guess: a wrong sheet number
    silently mis-resolves every cross-reference on the page, which is worse than an absent one
    that makes a caller ask.
    """
    best = None
    for w in words or []:
        t = (w.get("text") or "").strip().upper()
        if not _SHEET_NO_RE.match(t):
            continue
        h = _text_height(w)
        if best is None or h > best[0]:
            best = (h, t)
    blob = " ".join((w.get("text") or "") for w in (words or [])).upper()
    status = next((p for p in _STATUS_PHRASES if p in blob), None)
    return {"number": best[1] if best else None,
            "number_text_height": round(best[0], 2) if best else None,
            "status": status}


def read_sheet(data: bytes, page_index: int = 0, want_geometry: bool = False) -> Dict:
    """Everything this module can tell you about one plotted page, in one shape.

    The parsers grew one at a time and each returned its own thing. This is the shape they
    agree on, so a caller — and the studio at the other end — has one contract to read rather
    than five, which is how the two ends of this project stay in step.

    `scale.used` is what a caller should build with: the printed ratio when the sheet states
    one, otherwise the ratio inferred from the line work, otherwise None. Both inputs are kept
    alongside it so a disagreement is visible rather than resolved silently.
    """
    g = extract_geometry(data, page_index=page_index)
    words, strokes = g.get("words", []), g.get("strokes", [])
    details = find_details(words)
    # ONE LIST, ONE INDEX. `details` is what a client is shown and what it picks from, so each
    # entry carries the FRAME its geometry lives in. Reporting titles from one list and cropping
    # from another let `detail=0` return an untitled frame while the listing's first entry was
    # MAIN COLUMN FRONT ELEVATION — a client picking by index would silently get a different
    # drawing from the one it displayed.
    _segs = segment_by_frame(strokes, details)
    _by_title = {x["title"]: x["frame"] for x in _segs if x["title"]}
    for _d in details:
        _d["frame"] = _by_title.get(_d["title"])
    printed = g.get("plot_scale")
    inferred = None if printed else infer_plot_scale(strokes, words)
    used = printed or inferred
    out = {
        "page": {"index": page_index,
                 "width_mm": g.get("width_mm") or g.get("page_width_mm"),
                 "height_mm": g.get("height_mm") or g.get("page_height_mm")},
        "sheet": sheet_identity(words),
        "scale": {"printed": printed, "inferred": inferred, "used": used},
        "counts": {"strokes": len(strokes), "words": len(words)},
        "details": details,
        # PER DETAIL, NOT PER SHEET. A sheet that mixes scales makes a single sheet scale wrong
        # for part of itself — the real L406 measures its wayfinding sign at 3/8" among column
        # sections at 1/4". Linking at the sheet scale loses those dimensions entirely.
        "dimensions": link_dimensions_by_detail(strokes, words, details, used),
        "points": parse_point_schedule(words),
    }
    if want_geometry:
        out["strokes"], out["words"] = strokes, words
    return out


# ----------------------------------------------------------------------------------------
# SURVEY POINTS -> SOMETHING THE APP CAN PLACE.
#
# A schedule gives absolute state-plane coordinates in feet — 2068137.9965 N, 414321.8101 E.
# Nothing can be built from those directly: they are seven digits of offset from a datum
# hundreds of miles away. What a model needs is LOCAL millimetres from a chosen origin, at the
# ratio the model is being built to.
#
# **PLOT SCALE IS NOT MODEL SCALE, and conflating them is the mistake this signature exists to
# prevent.** A sheet plotted at 1"=20'-0" (1:240) is a statement about PAPER. The model may be
# built at 1:100 or 1:200 for reasons that have nothing to do with how the drawing was printed.
# So the ratio is passed in; it is never taken from the sheet.
# ----------------------------------------------------------------------------------------
MM_PER_FT = 304.8          # international foot, exact


def survey_layout(points, model_scale: float, origin_id=None) -> Dict:
    """Survey points as local model millimetres, plus what they span.

    `model_scale` is the build ratio — 200 for a 1:200 model — NOT the sheet's plot scale.
    `origin_id` picks which point sits at (0, 0); the first point is used when it is absent or
    not found, and the choice is reported so a caller is never guessing which one it was.

    x runs EAST and y runs NORTH, which is the convention of the schedule itself rather than
    any screen axis — mapping to a viewport is the caller's business and depends on which way
    the model is laid down.

    The international foot (304.8mm exactly) is used. A state-plane schedule may be in US
    survey feet, which differ by 2 parts per million: across this monument's 50ft span that is
    0.03mm of real building, and at any model ratio it is far below what prints.
    """
    pts = [p for p in (points or []) if p.get("northing") is not None
           and p.get("easting") is not None]
    if not pts:
        return {"origin": None, "model_scale": model_scale, "points": [], "extent_mm": None}
    origin = next((p for p in pts if p.get("id") == origin_id), None) if origin_id is not None else None
    if origin is None:
        origin = pts[0]
    scale = float(model_scale) if model_scale else 1.0
    if scale <= 0:
        scale = 1.0
    out = []
    for p in pts:
        east_ft = p["easting"] - origin["easting"]
        north_ft = p["northing"] - origin["northing"]
        out.append({"id": p.get("id"), "description": p.get("description", ""),
                    "x_mm": round(east_ft * MM_PER_FT / scale, 4),
                    "y_mm": round(north_ft * MM_PER_FT / scale, 4),
                    "east_ft": round(east_ft, 4), "north_ft": round(north_ft, 4)})
    xs = [q["x_mm"] for q in out]
    ys = [q["y_mm"] for q in out]
    return {"origin": {"id": origin.get("id"), "description": origin.get("description", "")},
            "model_scale": scale,
            "points": out,
            "extent_mm": {"x": round(max(xs) - min(xs), 4), "y": round(max(ys) - min(ys), 4)}}


def survey_span(points, a_id, b_id) -> Optional[Dict]:
    """Distance and bearing between two survey points, in real units.

    Bearing is degrees clockwise from NORTH, which is how a drawing states it — not the
    mathematical convention of counter-clockwise from east. Getting that backwards puts a
    monument across the road from where it belongs.
    """
    idx = {p.get("id"): p for p in (points or []) if p.get("id") is not None}
    a, b = idx.get(a_id), idx.get(b_id)
    if not a or not b:
        return None
    de = b["easting"] - a["easting"]
    dn = b["northing"] - a["northing"]
    dist_ft = (de * de + dn * dn) ** 0.5
    import math as _m
    bearing = _m.degrees(_m.atan2(de, dn)) % 360.0
    return {"from": a_id, "to": b_id, "distance_ft": round(dist_ft, 4),
            "distance_mm": round(dist_ft * MM_PER_FT, 2),
            "bearing_deg_from_north": round(bearing, 4)}


# ----------------------------------------------------------------------------------------
# WHAT IS ON THIS SHEET? A details sheet is not one drawing — L406 carries eight, each with a
# bubble number, a title and ITS OWN SCALE. Treating such a sheet as having one scale is wrong
# on its face, and it is why L406 legitimately reports none: it mixes a 3/8" sign detail in
# among the 1/4" column sections.
#
# A detail announces itself the same way on every sheet in this trade: a title, and its scale
# printed directly beneath it. So the scale text is the anchor and the title is read back from
# it. Measured on the real L406, the title words share one band position (x 32.6) while the
# scale sits one line over (x 24.2) and is markedly smaller — 2-6mm of text height against
# 15-34mm. The band is what separates them; the size difference is a corroboration, not the
# test, because a title block can print small titles.
# ----------------------------------------------------------------------------------------
def find_details(words) -> List[Dict]:
    """Every titled detail on a sheet: number, title, scale and where it sits.

    Returns them in sheet order. A sheet with no titled details — a plan, a schedule — yields
    an empty list, which is the honest answer rather than one detail covering the page.
    """
    ws = list(words or [])
    out: List[Dict] = []
    for i, w in enumerate(ws):
        span_hit = None
        for span in (1, 2, 3, 4):
            txt = " ".join(x.get("text", "") for x in ws[i:i + span])
            sc = parse_arch_scale(txt)
            if sc:
                span_hit = (span, sc, txt)
                break
        if not span_hit:
            continue
        span, scale, scale_text = span_hit
        # which axis does a line of text run along? the scale's own runs share one of them.
        group = ws[i:i + span]
        if span > 1:
            dx = max(q.get("x", 0.0) for q in group) - min(q.get("x", 0.0) for q in group)
            dy = max(q.get("y", 0.0) for q in group) - min(q.get("y", 0.0) for q in group)
            axis = "x" if dx <= dy else "y"
        else:
            axis = "x"
        pos = (lambda q: q.get("x", 0.0)) if axis == "x" else (lambda q: q.get("y", 0.0))
        # the title is the contiguous run before the scale sharing ONE band position of its own
        title_words: List[str] = []
        title_pos = None
        for k in range(i - 1, max(-1, i - 14), -1):
            q = ws[k]
            if title_pos is None:
                title_pos = pos(q)
            elif abs(pos(q) - title_pos) > 2.0:
                break
            title_words.append(q.get("text", ""))
        title_words.reverse()
        number = None
        if title_words and re.match(r"^\d{1,2}$", title_words[0].strip()):
            number = int(title_words[0]); title_words = title_words[1:]
        title = " ".join(t for t in title_words if t).strip()
        # NOT EVERY SCALE TEXT BELONGS TO A DETAIL. A plan sheet prints its scale under a
        # SCALE BAR and a north arrow, and reading back from those gave L201B two phantom
        # details titled "N" and "SCALE:". A label ends in a colon and a north arrow is one
        # letter; a real title is neither. This keeps single-word details like "LOGO", which
        # is detail 10 on L404 and would be lost to a two-word rule.
        if not title or len(title) < 2 or title.endswith(":"):
            continue
        # A TITLE IS NOT A SCALE. "SCALE:" is itself an anchor — the parser strips that prefix
        # — and its walk-back happily collected the NEIGHBOURING detail's scale text as a
        # title, yielding a phantom detail called `1" = 20'-0"`. Nothing about position
        # prevents that; only asking what the words mean does.
        if parse_arch_scale(title) or parse_feet_inches(title):
            continue
        out.append({"number": number, "title": title, "scale": scale,
                    "scale_text": scale_text, "x": w.get("x", 0.0), "y": w.get("y", 0.0)})
    return out


def link_dimensions_by_detail(strokes, words, details, fallback_scale=None,
                              tol: float = 0.02, search_mm: float = 25.0) -> List[Dict]:
    """Link every dimension at the scale of the detail it belongs to, not the sheet's.

    **A sheet scale is wrong for a sheet that mixes scales, and the real L406 does.** Eight
    column sections at 1/4"=1'-0" and a wayfinding sign at 3/8" — measuring the sign's
    dimensions at 1:48 understates them by a third, and the arithmetic check then rejects them,
    so they vanish rather than arrive wrong. Either way the sign is unbuildable from the sheet
    it is drawn on.

    Each dimension is assigned to the nearest titled detail and measured at that detail's
    scale. The detail is reported on every match, which is the segmentation a caller actually
    wants: not "here are 87 dimensions on L406" but "here are the eleven belonging to
    MAIN COLUMN FRONT ELEVATION".

    With no titled details — a plan sheet — this falls back to `fallback_scale` and behaves
    exactly as `link_dimensions` does.
    """
    if not details:
        got = link_dimensions(strokes, words, fallback_scale, tol, search_mm) if fallback_scale else []
        for d in got:
            d["detail"] = None
        return got
    buckets: Dict[int, List[Dict]] = {}
    for w in words or []:
        if not parse_feet_inches(w.get("text", "")):
            continue
        wx, wy = w.get("x", 0.0), w.get("y", 0.0)
        best_i, best_d = None, None
        for i, det in enumerate(details):
            dd = ((wx - det["x"]) ** 2 + (wy - det["y"]) ** 2) ** 0.5
            if best_d is None or dd < best_d:
                best_i, best_d = i, dd
        buckets.setdefault(best_i, []).append(w)
    out: List[Dict] = []
    for i, ws in buckets.items():
        det = details[i]
        for m in link_dimensions(strokes, ws, det["scale"], tol, search_mm):
            m["detail"] = {"title": det["title"], "scale": det["scale"]}
            out.append(m)
    return out


# ----------------------------------------------------------------------------------------
# WHICH STROKES BELONG TO WHICH DETAIL. A sheet holds 163,293 of them and nine details; a
# builder needs the few thousand that are one column, not the lot.
#
# **THE SHEET DRAWS THE ANSWER.** A details sheet frames each detail, and on the real L406
# those frames are an exact grid: 181.0 x 368.3mm cells at x 19.4, 200.4, 381.3, 562.3. Using
# them is exact where the alternatives are not — two were tried and measured first:
#
#   nearest-anchor Voronoi on the matched STROKES  9 regions, 5 of 36 pairs overlapping,
#                                                  two degenerate to a point, one spanning
#                                                  half the sheet (a long leader line)
#   nearest-anchor on the dimension TEXT           9 regions, 3 of 36 overlapping, one
#                                                  claiming 87 dimensions over 260x571mm
#
# Both fail the same way: a detail's anchor is its SCALE TEXT, printed at the BOTTOM, so a
# dimension at the top of one detail is often nearer the anchor of the detail below it. A
# frame has no such ambiguity. **A segmentation that is roughly right is worse than none —
# handing a builder two details' geometry mixed together produces a wrong model in silence.**
# ----------------------------------------------------------------------------------------
def detail_frames(strokes, min_mm: float = 60.0) -> List[Dict]:
    """Axis-aligned rectangles a details sheet uses to box each detail, outer border removed.

    The border is dropped by containment rather than by size: it is the rectangle that holds
    the others. Sorting by area and dropping the largest would also drop a legitimately large
    detail on a sheet that has no border at all.
    """
    rects = []
    for i, s in enumerate(strokes or []):
        if not (4 <= len(s) <= 6):
            continue
        xs = [p[0] for p in s]
        ys = [p[1] for p in s]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if (x1 - x0) < min_mm or (y1 - y0) < min_mm:
            continue
        if not all(abs(s[k][0] - s[k + 1][0]) < 0.6 or abs(s[k][1] - s[k + 1][1]) < 0.6
                   for k in range(len(s) - 1)):
            continue
        rects.append({"stroke": i, "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                      "w": x1 - x0, "h": y1 - y0})
    # de-duplicate: a frame may be drawn twice, or as a path and its own outline
    uniq: List[Dict] = []
    for r in rects:
        if not any(abs(r["x0"] - q["x0"]) < 1.0 and abs(r["y0"] - q["y0"]) < 1.0
                   and abs(r["w"] - q["w"]) < 1.0 and abs(r["h"] - q["h"]) < 1.0 for q in uniq):
            uniq.append(r)
    def contains(a, b):
        return (a["x0"] <= b["x0"] + 1.0 and a["y0"] <= b["y0"] + 1.0
                and a["x1"] >= b["x1"] - 1.0 and a["y1"] >= b["y1"] - 1.0 and a is not b)
    return [r for r in uniq if not any(contains(r, q) for q in uniq)]


def _in_frame(x, y, f, pad: float = 0.0) -> bool:
    return (f["x0"] - pad) <= x <= (f["x1"] + pad) and (f["y0"] - pad) <= y <= (f["y1"] + pad)


def segment_by_frame(strokes, details, frames=None) -> List[Dict]:
    """Each framed detail with the strokes drawn inside its frame.

    A detail is placed by its anchor; a stroke by its midpoint, so a dimension line reaching
    slightly past a frame edge still lands with the drawing it measures. Frames holding no
    titled detail are returned with `title: None` rather than dropped — on a real sheet that is
    a detail whose title did not parse, and silently discarding its geometry would hide it.
    """
    frames = detail_frames(strokes) if frames is None else frames
    # ONE DETAIL PER FRAME, ONE FRAME PER DETAIL. Walking frames and taking the first detail
    # that fits let a single detail claim TWO frames — measured on L406, where
    # MAIN COLUMN CROSS-SECTION 5 was assigned twice while WAYFINDING SIGN got nothing. A
    # scale text sits at the bottom edge of its own frame, so with any padding at all an anchor
    # falls inside its neighbour too. Assigning detail -> frame, smallest containing frame
    # first, makes the relationship one-to-one by construction.
    # NO PADDING. Frames abut exactly — L406's grid is 181.0mm cells with no gutter — so any
    # padding at all puts an anchor inside its neighbour as well. Measured on that sheet:
    #     pad  0mm  -> 9 of 9 details inside exactly one frame
    #     pad  4mm  -> 9 of 9
    #     pad 12mm  -> 3 of 9, with SIX inside several
    # The padding was the whole fault: it caused both the duplicate claims and the two details
    # that ended up with no frame at all. A scale text is printed INSIDE its own frame, so
    # nothing needed to be allowed for.
    claimed: Dict[int, Dict] = {}
    for d in details or []:
        fits = [(fi, f) for fi, f in enumerate(frames)
                if _in_frame(d.get("x", 0.0), d.get("y", 0.0), f, pad=0.0)]
        if not fits:
            continue
        fi, _ = min(fits, key=lambda p: p[1]["w"] * p[1]["h"])
        if fi not in claimed:
            claimed[fi] = d
    out = []
    for fi, f in enumerate(frames):
        d = claimed.get(fi)
        title = d["title"] if d else None
        scale = d["scale"] if d else None
        idx = []
        for i, s in enumerate(strokes or []):
            if not s:
                continue
            mx = sum(p[0] for p in s) / len(s)
            my = sum(p[1] for p in s) / len(s)
            if _in_frame(mx, my, f):
                idx.append(i)
        out.append({"title": title, "scale": scale, "frame": f, "strokes": idx})
    return out


def render_detail(pdf_bytes: bytes, page_index: int, frame: Dict, dpi: int = 300,
                  margin_mm: float = 2.0) -> Dict:
    """One framed detail, rasterised on its own, for a person to trace.

    The silhouette of a detail cannot be extracted automatically — measured on L406, the drawn
    ink covers six times the object's area, because a construction detail draws the thing IN
    ITS CONTEXT: the column plus its footing, the finished grade, the compacted subgrade. Which
    of those is "the object" is a judgement the geometry does not carry. **So the trace stays,
    and this is what makes it cheap:** one detail at a time instead of a 725 x 952mm sheet, with
    its scale and dimensions already read off the drawing.

    `frame` is a rectangle in the SAME millimetres `extract_geometry` reports, which measures y
    upward from the page bottom while PDF user space measures it downward — so the crop inverts
    it. Getting that wrong renders a different detail entirely, mirrored about the page middle,
    and it looks perfectly plausible.
    """
    fitz = _fitz()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    to_pt = 1.0 / PT_MM
    # THREE SPACES, AND ALL THREE MATTER. Our millimetres measure y UPWARD in the UNROTATED
    # page; PDF points measure it downward in the same unrotated page; and `get_pixmap(clip=)`
    # wants the ROTATED display rectangle. Every sheet in this set carries rotation 270, so
    # skipping the last step silently clipped crops against the wrong page edge — one detail
    # came back 1682px tall where 4397 was right, and it looked like a plausible image.
    h_pt = page.rect.height if page.rotation in (0, 180) else page.rect.width
    x0 = (frame["x0"] - margin_mm) * to_pt
    x1 = (frame["x1"] + margin_mm) * to_pt
    y0 = h_pt - (frame["y1"] + margin_mm) * to_pt
    y1 = h_pt - (frame["y0"] - margin_mm) * to_pt
    clip = (fitz.Rect(x0, y0, x1, y1) * page.rotation_matrix) & page.rect
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    # THE IMAGE COMES BACK THE RIGHT WAY UP, which on a rotated page means its axes are SWAPPED
    # relative to the frame: a 181 x 368mm frame on a 270-degree sheet renders 4398 x 2186px,
    # not 2186 x 4398. That is what a person should see, so it is what is returned — but a
    # caller mapping a traced point back to millimetres has to know, so the rotation and the
    # frame's own size are reported beside the image rather than left to be inferred.
    return {"png": pix.tobytes("png"), "width": pix.width, "height": pix.height,
            "dpi": dpi,
            "mm_per_px": 25.4 / dpi,
            "rotation": page.rotation,
            "axes_swapped": page.rotation in (90, 270),
            "frame_mm": {"w": frame["x1"] - frame["x0"] + 2 * margin_mm,
                         "h": frame["y1"] - frame["y0"] + 2 * margin_mm},
            "origin_mm": {"x": frame["x0"] - margin_mm, "y": frame["y0"] - margin_mm}}
