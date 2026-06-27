"""
PDF -> traceable page images (PyMuPDF / fitz).

Engineers hand you PDFs. This renders each page to a PNG (so a scanned or vector
side-view can be traced in the UI) and reports any embedded raster images and
vector path counts, which is a hint about whether a page holds a real drawing.
"""
from __future__ import annotations
import base64
from typing import Dict, List


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
