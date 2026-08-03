"""A plotted PDF is not a picture.

Dylan's drawings arrive as PDFs downloaded from a blueprint service, not as DXF — he's a
construction PM, not a CAD operator. The instinct is to rasterise and trace the pixels, and
the importer did exactly that: it even counted the vector paths and then threw them away.
But a plotted drawing carries its line work as real paths and its dimension callouts as
real text with real coordinates. Reading pixels off it discards geometry that is exact and
numbers that are already machine-readable — there is nothing to recognise, the characters
are in the file.
"""
import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed in this environment")

from app.pdf_import import extract_geometry, detect_plot_scale, PT_MM


def _plan():
    """A site plan the way one plots: vector line work plus text callouts."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)          # A4 landscape, in points
    sh = page.new_shape()
    for r in (200, 130):                                # roundabout, outer and inner kerb
        sh.draw_circle(fitz.Point(421, 300), r)
    sh.draw_rect(fitz.Rect(381, 280, 461, 320))         # the sign island in the middle
    sh.finish(color=(0, 0, 0), width=0.7)
    sh.commit()
    page.insert_text(fitz.Point(60, 560), "SCALE 1:200", fontsize=10)
    page.insert_text(fitz.Point(392, 305), "FFE 150", fontsize=8)
    page.insert_text(fitz.Point(430, 96), "R 20.00", fontsize=9)
    return doc.tobytes()


def test_the_page_reports_its_true_paper_size():
    g = extract_geometry(_plan())
    assert g["page_mm"][0] == pytest.approx(297.0, abs=0.5), "A4 landscape is 297mm wide"
    assert g["page_mm"][1] == pytest.approx(210.0, abs=0.5)


def test_curves_survive_as_geometry_not_pixels():
    # Curves are most of a site plan — kerb returns, roundabouts, planting beds. Dropping
    # them, or reading them back off a raster, loses the drawing.
    g = extract_geometry(_plan())
    assert len(g["strokes"]) >= 3, "two kerb lines and an island"
    assert sum(len(s) for s in g["strokes"]) > 40, "the circles are flattened, not skipped"
    # the kerbs must come back at their true size on the paper: r=200pt -> 400pt across
    widths = []
    for s in g["strokes"]:
        xs = [p[0] for p in s]; ys = [p[1] for p in s]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if abs(w - h) < 0.5 and w > 20:
            widths.append(w)
    assert widths, "the round kerbs came through"
    assert max(widths) == pytest.approx(400 * PT_MM, abs=1.0), "outer kerb, true to the page"


def test_y_reads_upward_like_a_drawing_not_downward_like_a_page():
    # A page is painted top-down; a plan is read bottom-up, and so is every other coordinate
    # frame in this project. Handing back page coordinates would put every model upside down.
    g = extract_geometry(_plan())
    at = lambda t: next(w for w in g["words"] if w["text"] == t)
    assert at("SCALE")["y"] < at("FFE")["y"], "the title block sits below the drawing"


def test_the_callouts_come_back_as_numbers_with_positions():
    # This is what makes a height per region possible without anyone typing: the numbers are
    # already in the file, with coordinates, so each one can be matched to what it labels.
    g = extract_geometry(_plan())
    vals = {w["text"] for w in g["numbers"]}
    assert "150" in vals, "the level callout"
    assert "20.00" in vals, "the radius dimension"
    ffe = next(w for w in g["numbers"] if w["text"] == "150")
    assert 100 < ffe["x"] < 200 and 80 < ffe["y"] < 130, "and it knows where on the sheet it is"


def test_the_plot_scale_is_read_off_the_sheet():
    assert extract_geometry(_plan())["plot_scale"] == 200.0


def test_it_refuses_to_pick_a_scale_when_the_sheet_gives_two():
    # A sheet carrying a plan at 1:200 and a blown-up detail at 1:50 is genuinely ambiguous,
    # and being wrong here is wrong by a whole multiple. Ask; never guess.
    assert detect_plot_scale([{"text": "1:200"}, {"text": "1:50"}]) is None
    assert detect_plot_scale([{"text": "1:200"}, {"text": "1:200"}]) == 200.0
    assert detect_plot_scale([{"text": "SCALE"}, {"text": "1:200"}]) == 200.0
    assert detect_plot_scale([{"text": "NORTH"}]) is None


def test_a_page_that_does_not_exist_is_a_clear_error_not_a_crash():
    with pytest.raises(ValueError):
        extract_geometry(_plan(), page_index=7)
