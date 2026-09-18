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
    h_pt = page.rect.height                       # to flip y: page paints downward, plans read upward
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


_ARCH_SCALE_RE = re.compile(r"^(?P<lhs>[^=]+?)\s*=\s*(?P<rhs>.+)$")


def parse_arch_scale(text: str) -> Optional[float]:
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
    return ratio if 1.0 <= ratio <= 20000.0 else None


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
        "dimensions": link_dimensions(strokes, words, used) if used else [],
        "points": parse_point_schedule(words),
    }
    if want_geometry:
        out["strokes"], out["words"] = strokes, words
    return out
