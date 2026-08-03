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
        # "SCALE 1 : 200" arrives as separate runs
        if w["text"].strip().upper() in ("SCALE", "SCALE:"):
            tail = "".join(x["text"] for x in words[i + 1:i + 4])
            m2 = _SCALE_RE.match(tail.strip())
            if m2:
                found.add(int(m2.group(1)))
    return float(found.pop()) if len(found) == 1 else None
