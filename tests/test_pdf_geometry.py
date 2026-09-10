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


# =====================================================================================
# IMPERIAL. American construction documents are dimensioned in feet and inches and scaled
# architecturally. None of the metric reading above sees any of it, and Dylan's real set —
# Saratoga Springs / Cathedral Oak Parkway — is entirely imperial. These are the actual
# strings off those sheets, not invented ones.
# =====================================================================================
def test_feet_and_inches_are_read_as_written_on_the_sheet():
    from app.pdf_import import parse_feet_inches as f
    assert f("4'-0\"") == pytest.approx(1219.2)      # main column width
    assert f("12'-4\"") == pytest.approx(3759.2)     # main column height
    assert f("23'-0\"") == pytest.approx(7010.4)     # community sign
    assert f("16'-0\"") == pytest.approx(4876.8)     # wayfinding sign, maximum height
    assert f("2'-10\"") == pytest.approx(863.6)
    assert f("7\"") == pytest.approx(177.8)
    assert f("1/2\"") == pytest.approx(12.7)         # polymetal thickness
    assert f("3/8\"") == pytest.approx(9.525)        # raked joints
    assert f("1-1/2\"") == pytest.approx(38.1)       # sign lettering thickness
    assert f("4-1/2\"") == pytest.approx(114.3)      # community logo thickness


def test_a_vulgar_fraction_sits_after_its_whole_number():
    """42'-1¾" is off the wayfinding sign detail, and it broke the first version of this.

    A vulgar fraction follows its whole number (1¾) while a written one follows a hyphen
    (1-1/2). One regex trying to hold both orderings matched neither, and returned None on a
    real dimension — which reads as "no dimension there" rather than as a parser fault."""
    from app.pdf_import import parse_feet_inches as f
    assert f("42'-1¾\"") == pytest.approx(12846.05)
    assert f("1¾\"") == pytest.approx(44.45)
    assert f("1-1/2\"") == pytest.approx(38.1)
    assert f("3/8\"") == pytest.approx(9.525)


def test_a_dimension_it_cannot_read_returns_nothing_rather_than_a_guess():
    """A wrong dimension read confidently is worse than none: it gets built."""
    from app.pdf_import import parse_feet_inches as f
    for junk in (None, "", "   ", "HELLO", "'", '"', "-", "NOT TO SCALE"):
        assert f(junk) is None, f"{junk!r} must not parse to a number"


def test_architectural_scales_come_back_in_the_same_form_as_metric_ones():
    """1/4" = 1'-0" is 1:48. Returned as a plain denominator so a caller never has to know
    which notation the sheet used — the same shape `detect_plot_scale` already returns."""
    from app.pdf_import import parse_arch_scale as a
    assert a("1\" = 20'-0\"") == pytest.approx(240)    # L201B site layout, L301B grading
    assert a("1/4\" = 1'-0\"") == pytest.approx(48)    # the column and section details
    assert a("3/8\" = 1'-0\"") == pytest.approx(32)    # wayfinding sign
    assert a("1/8\" = 1'-0\"") == pytest.approx(96)    # monument cross-section
    assert a("SCALE: 1\" = 20'-0\"") == pytest.approx(240)
    assert a("nonsense") is None and a("") is None


def test_the_sheet_scale_is_found_whichever_notation_it_is_printed_in():
    from app.pdf_import import detect_plot_scale
    w = lambda t: {"text": t, "x": 0.0, "y": 0.0}
    assert detect_plot_scale([w("1:200")]) == pytest.approx(200)
    assert detect_plot_scale([w("SCALE:"), w("1\" = 20'-0\"")]) == pytest.approx(240)
    # broken into separate runs, which is how a plotted sheet actually arrives
    assert detect_plot_scale([w("1/4\""), w("="), w("1'-0\"")]) == pytest.approx(48)
    # two different scales on one sheet is genuinely ambiguous: say nothing
    assert detect_plot_scale([w("1:200"), w("1/4\" = 1'-0\"")]) is None
