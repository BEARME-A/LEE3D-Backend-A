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


# =====================================================================================
# LINKING A DIMENSION TO WHAT IT DIMENSIONS.
# A dimension in CAD is not one object — two witness lines, a dimension line, a text run, and
# nothing in the file saying they belong together. The link here is ARITHMETIC: a line drawn L
# mm on paper at 1:S measures L*S, and the text says what that should be. Proximity alone would
# pair a 4'-0" with whatever line happened to be nearest, which on a dense sheet is often wrong.
# =====================================================================================
def _ln(x0, y0, x1, y1):
    return [[x0, y0], [x1, y1]]


def test_a_dimension_is_matched_to_the_line_whose_length_agrees_with_it():
    from app.pdf_import import link_dimensions
    S = 48.0                                    # 1/4" = 1'-0", the column detail sheets
    strokes = [_ln(0, 0, 1219.2 / S, 0),        # a 4'-0" width
               _ln(0, 0, 0, 3759.2 / S)]        # a 12'-4" height
    words = [{"text": "4'-0\"", "x": 1219.2 / S / 2, "y": 2.0},
             {"text": "12'-4\"", "x": 2.0, "y": 3759.2 / S / 2}]
    got = {d["text"]: d for d in link_dimensions(strokes, words, S)}
    assert set(got) == {"4'-0\"", "12'-4\""}
    assert got["4'-0\""]["stroke"] == 0 and got["4'-0\""]["error"] < 1e-6
    assert got["12'-4\""]["stroke"] == 1


def test_a_nearer_line_of_the_wrong_length_is_not_the_match():
    """THE WHOLE POINT. A decoy sits closer to the text than the line the dimension belongs to.
    Proximity would take it; arithmetic does not."""
    from app.pdf_import import link_dimensions
    S = 48.0
    strokes = [_ln(0, 0, 1219.2 / S, 0),        # the real 4'-0"
               _ln(10, 1, 13, 1)]               # a 3mm stub right beside the text
    words = [{"text": "4'-0\"", "x": 11.0, "y": 1.5}]
    got = link_dimensions(strokes, words, S)
    assert len(got) == 1 and got[0]["stroke"] == 0, (
        "the decoy is nearer but measures 3mm*48 = 144mm, not 4 feet")


def test_a_plotted_line_is_allowed_to_be_slightly_off_but_not_wrong():
    from app.pdf_import import link_dimensions
    S = 48.0
    exact = 1219.2 / S
    words = [{"text": "4'-0\"", "x": exact / 2, "y": 2.0}]
    assert link_dimensions([_ln(0, 0, exact * 1.01, 0)], words, S), "1% off must still match"
    assert not link_dimensions([_ln(0, 0, exact * 1.25, 0)], words, S), "25% off is a different line"


def test_the_scale_can_be_recovered_from_the_line_work_alone():
    """A title block can be missing, wrong, or belong to a different detail on the same sheet.
    The line work cannot: the ratio that makes the written dimensions agree with the lengths
    actually drawn IS the scale."""
    from app.pdf_import import infer_plot_scale
    S = 48.0
    strokes = [_ln(0, 0, 1219.2 / S, 0), _ln(0, 0, 0, 3759.2 / S),
               _ln(50, 50, 50 + 7010.4 / S, 50)]
    words = [{"text": "4'-0\"", "x": 1219.2 / S / 2, "y": 2.0},
             {"text": "12'-4\"", "x": 2.0, "y": 3759.2 / S / 2},
             {"text": "23'-0\"", "x": 50 + 7010.4 / S / 2, "y": 52.0}]
    assert infer_plot_scale(strokes, words) == pytest.approx(48.0)


def test_too_little_evidence_decides_nothing():
    """One agreeing dimension is a coincidence waiting to happen, and a tie is not an answer.
    Both return None — the same refusal `detect_plot_scale` makes on a sheet carrying two
    ratios, and for the same reason: guessing here is wrong by whole multiples."""
    from app.pdf_import import infer_plot_scale
    S = 48.0
    one = ([_ln(0, 0, 1219.2 / S, 0)], [{"text": "4'-0\"", "x": 12.0, "y": 2.0}])
    assert infer_plot_scale(*one) is None
    assert infer_plot_scale([], []) is None


def test_a_narrow_win_over_coincidences_is_not_an_answer():
    """Measured on a real sheet: L404 of the Saratoga Springs set carries 59,794 strokes, and
    at a 40mm search radius the true 1:48 beat a coincidence 126 to 121 — a 4% lead. The right
    answer, and luck. `min_lead` makes the margin part of the claim.

    Two candidates have to be in contention for a lead to mean anything, so the fixture puts
    them there: a 25.4mm stroke is 4'-0" at 1:48 and 8'-0" at 1:96, so four of the first and
    three of the second give 1:48 a win of 4 to 3 — a win, and not a lead."""
    from app.pdf_import import infer_plot_scale
    strokes, words = [], []
    for k in range(4):                                   # four that only work at 1:48
        y = k * 60.0
        strokes.append(_ln(0, y, 25.4, y))
        words.append({"text": "4'-0\"", "x": 12.7, "y": y + 1.0})
    for k in range(3):                                   # three that only work at 1:96
        y = 500.0 + k * 60.0
        strokes.append(_ln(0, y, 25.4, y))
        words.append({"text": "8'-0\"", "x": 12.7, "y": y + 1.0})
    assert infer_plot_scale(strokes, words, min_lead=1.0) == pytest.approx(48.0), (
        "with no lead required, the bare win stands")
    assert infer_plot_scale(strokes, words) is None, (
        "4 against 3 is a win, not a lead — the default must refuse it")


def test_the_two_jobs_use_different_search_radii_on_purpose():
    """With the scale KNOWN the length check does the work and a generous radius finds more
    real dimensions — tightening to 12mm cost sheet L201B more than half of them, 26 down to
    10, for nothing. With the scale GUESSED there is no length check yet, only a comparison,
    and the radius IS the discriminator. One default cannot serve both."""
    import inspect
    from app.pdf_import import link_dimensions, infer_plot_scale
    assert inspect.signature(link_dimensions).parameters["search_mm"].default == 25.0
    src = inspect.getsource(infer_plot_scale)
    assert "search_mm=8.0" in src, (
        "inference must pass its own tight radius, not inherit the linking default")


# =====================================================================================
# THE SURVEY SCHEDULE. Dimensions say how big a thing is; only a NORTHING/EASTING schedule
# says WHERE it goes. These fixtures mirror the layout measured on the real L201B, which the
# repo cannot carry.
# =====================================================================================
def _sched_words(rows, rotated: bool):
    """A schedule laid out either upright or turned 90 degrees on the page."""
    ws = []
    for r, (pid, desc, n, e) in enumerate(rows):
        toks = [str(pid)] + desc.split() + ["N", n, "E", e]
        for t, tok in enumerate(toks):
            along, across = t * 16.0, r * 8.0       # 16mm between cells, from the real sheet
            ws.append({"text": tok,
                       "x": along if not rotated else across,
                       "y": -across if not rotated else -along})
    return ws


_ROWS = [(21, "WEST ENTRY MONUMENT", "2068137.9965", "414321.8101"),
         (22, "WEST ENTRY MONUMENT", "2068139.3216", "414321.6075"),
         (27, "WEST ENTRY MONUMENT", "2068125.5657", "414371.1075")]


def test_a_survey_schedule_is_read_whichever_way_the_table_is_turned():
    """ON THE REAL SHEET IT WAS ROTATED. Every one of L201B's ten eastings shares a single y
    and has its own x: what a reader sees as rows running down the page are, in page
    coordinates, columns running across it. A landscape sheet turns its schedules as readily
    as its title block, so the axis is found rather than assumed."""
    from app.pdf_import import parse_point_schedule
    for rotated in (False, True):
        pts = {p["id"]: p for p in parse_point_schedule(_sched_words(_ROWS, rotated))}
        assert set(pts) == {21, 22, 27}, f"rotated={rotated} lost rows: {sorted(pts)}"
        assert pts[21]["northing"] == pytest.approx(2068137.9965)
        assert pts[21]["easting"] == pytest.approx(414321.8101)
        assert "WEST ENTRY MONUMENT" in pts[27]["description"]


def test_title_block_text_sharing_a_band_stays_out_of_the_schedule():
    """A band spans the whole sheet. On the real L201B the descriptions came back carrying
    'CHECKED BY: DEP' and 'SHEET NUM', and one point lost its id to a plot timestamp. Within a
    record the gaps measured 10-20mm; the jump to the title block was 38mm."""
    from app.pdf_import import parse_point_schedule
    ws = _sched_words(_ROWS, rotated=True)
    for r in range(3):                      # title block, far along the same band
        for k, tok in enumerate(("L201B", "SCALE:", "AS", "NOTED")):
            ws.append({"text": tok, "x": r * 8.0, "y": -(200.0 + k * 40.0)})
    pts = {p["id"]: p for p in parse_point_schedule(ws)}
    assert set(pts) == {21, 22, 27}
    for p in pts.values():
        for junk in ("L201B", "SCALE", "NOTED"):
            assert junk not in p["description"], f"title block leaked in: {p['description']!r}"


def test_half_a_coordinate_is_not_a_point():
    """A sheet is covered in numbers — dimensions, radii, elevations, sheet references. Only
    the ones sharing a band with BOTH a northing and an easting are survey points, and
    requiring the pair is what keeps a dimension out of the placement data."""
    from app.pdf_import import parse_point_schedule
    ws = _sched_words([(21, "WEST ENTRY MONUMENT", "2068137.9965", "414321.8101")], rotated=True)
    assert len(parse_point_schedule(ws)) == 1
    only_n = [w for w in ws if w["text"] not in ("E", "414321.8101")]
    assert parse_point_schedule(only_n) == [], "a northing alone is not a location"
    assert parse_point_schedule([]) == [] and parse_point_schedule(None) == []


# =====================================================================================
# ONE SHAPE FOR A SHEET. The parsers grew one at a time and each returned its own thing;
# `read_sheet` is the shape they agree on, and LEE3D-Lib/schema/sheet.schema.json is the
# contract. Two ends reading a drawing five different ways is how they drift.
# =====================================================================================
def test_the_sheet_number_is_found_by_size_not_position():
    """A title block prints its sheet number larger than anything else on the page, and that
    holds when the block is rotated with the sheet — which on this set it is. A position rule
    breaks there; a size rule does not."""
    from app.pdf_import import sheet_identity
    # THE SMALL CALLOUT COMES FIRST ON PURPOSE. With the real sheet listed first, "take the
    # largest" and "take the first you see" give the same answer, and the test proves nothing —
    # a mutation to first-seen passed it. Order the fixture so only the size rule can pass.
    words = [{"text": "L219", "x": 50, "y": 300, "box": [48, 299, 56, 302]},  # 3mm, a callout
             {"text": "L201B", "x": 10, "y": 10, "box": [8, 6, 20, 14]},      # 8mm, the sheet
             {"text": "BID/ PERMIT SET", "x": 10, "y": 2, "box": [5, 1, 30, 3]}]
    got = sheet_identity(words)
    assert got["number"] == "L201B", "the larger of two candidates is the sheet"
    assert got["status"] == "BID/ PERMIT SET"


def test_no_sheet_number_is_reported_as_none_not_guessed():
    """A wrong sheet number silently mis-resolves every cross-reference on the page — a
    materials schedule pointing at '2/L403' lands somewhere else entirely. Absent makes a
    caller ask; wrong does not."""
    from app.pdf_import import sheet_identity
    got = sheet_identity([{"text": "SARATOGA", "x": 1, "y": 1, "box": [0, 0, 9, 4]}])
    assert got["number"] is None and got["status"] is None
    assert sheet_identity([])["number"] is None and sheet_identity(None)["number"] is None


def test_a_read_sheet_result_matches_the_published_contract():
    """The shape is published in LEE3D-Lib so the studio reads a sheet the same way the backend
    writes one. If this drifts, the two ends disagree about what a drawing IS."""
    import json, pathlib
    for base in (pathlib.Path(__file__).resolve().parents[2],
                 pathlib.Path(__file__).resolve().parents[1].parent):
        cand = base / "LEE3D-Lib" / "schema" / "sheet.schema.json"
        alt = base / "LEE3D-Lib-main" / "schema" / "sheet.schema.json"
        for path in (cand, alt):
            if path.exists():
                schema = json.loads(path.read_text())
                required = set(schema["required"])
                assert required == {"page", "sheet", "scale", "counts", "details",
                                    "dimensions", "points"}
                for k in ("printed", "inferred", "used"):
                    assert k in schema["properties"]["scale"]["properties"], (
                        f"the contract must keep both scale inputs beside the answer; {k} missing")
                return
    pytest.skip("LEE3D-Lib not checked out beside this repo")


# =====================================================================================
# SURVEY POINTS -> SOMETHING PLACEABLE. A schedule gives seven-digit state-plane feet, offset
# from a datum hundreds of miles away. A model needs LOCAL millimetres from a chosen origin at
# the ratio it is being built to. The coordinates below are the real West Entry Monument.
# =====================================================================================
_REAL_POINTS = [
    {"id": 21, "description": "WEST ENTRY MONUMENT", "northing": 2068137.9965, "easting": 414321.8101},
    {"id": 22, "description": "WEST ENTRY MONUMENT", "northing": 2068139.3216, "easting": 414321.6075},
    {"id": 27, "description": "WEST ENTRY MONUMENT", "northing": 2068125.5657, "easting": 414371.1075},
]


def test_a_span_between_survey_points_matches_the_hand_reduction():
    """Reduced by hand off the photographed schedule before the PDF arrived: 50.84 ft at
    104.15 degrees. The parsed-and-computed answer has to be the same number."""
    from app.pdf_import import survey_span
    s = survey_span(_REAL_POINTS, 21, 27)
    assert s["distance_ft"] == pytest.approx(50.8405, abs=1e-3)
    assert s["distance_mm"] == pytest.approx(15496, abs=1.0)
    assert s["bearing_deg_from_north"] == pytest.approx(104.1526, abs=1e-3)
    assert survey_span(_REAL_POINTS, 21, 999) is None, "an unknown point is not an answer"


def test_bearing_is_clockwise_from_north_the_way_a_drawing_states_it():
    """NOT the mathematical convention of counter-clockwise from east. Getting this backwards
    puts a monument across the road from where it belongs, and both conventions produce a
    plausible-looking number, so nothing downstream would catch it."""
    from app.pdf_import import survey_span
    due_east = [{"id": 1, "northing": 1000.0, "easting": 0.0},
                {"id": 2, "northing": 1000.0, "easting": 100.0}]
    assert survey_span(due_east, 1, 2)["bearing_deg_from_north"] == pytest.approx(90.0)
    due_north = [{"id": 1, "northing": 0.0, "easting": 500.0},
                 {"id": 2, "northing": 100.0, "easting": 500.0}]
    assert survey_span(due_north, 1, 2)["bearing_deg_from_north"] == pytest.approx(0.0)


def test_the_model_ratio_is_given_not_taken_from_the_sheet():
    """PLOT SCALE IS NOT MODEL SCALE. A sheet plotted at 1"=20'-0" is a statement about PAPER;
    the model may be built at any ratio for reasons that have nothing to do with printing. So
    the ratio is a parameter, and halving it halves the model."""
    from app.pdf_import import survey_layout
    at100 = survey_layout(_REAL_POINTS, 100, origin_id=21)
    at200 = survey_layout(_REAL_POINTS, 200, origin_id=21)
    assert at100["extent_mm"]["x"] == pytest.approx(at200["extent_mm"]["x"] * 2, rel=1e-6)
    assert at100["origin"]["id"] == 21
    by21 = {p["id"]: p for p in at100["points"]}
    assert by21[21]["x_mm"] == 0.0 and by21[21]["y_mm"] == 0.0, "the origin sits at zero"


def test_the_origin_is_reported_so_nobody_has_to_guess_which_point_it_was():
    from app.pdf_import import survey_layout
    fallback = survey_layout(_REAL_POINTS, 100, origin_id=999)
    assert fallback["origin"]["id"] == 21, "an unknown origin falls back to the first point"
    assert survey_layout([], 100)["points"] == []
    assert survey_layout(_REAL_POINTS, 0)["model_scale"] == 1.0, "a zero ratio must not divide"


def test_a_detail_bubble_number_does_not_become_part_of_the_scale():
    """FOUND ON THE REAL L406. A scale text is searched across several word runs, because a
    plotted sheet breaks `1/4" = 1'-0"` into separate ones. That search also swallows the
    DETAIL BUBBLE NUMBER sitting just before it: bubble 1 gave `1 1/4" = 1'-0"` and a
    valid-looking 1:9.6; bubbles 2 and 3 gave 1:5.33 and 1:3.69.

    Those readings polluted the sheet's scale set and made L404 look ambiguous — it reported no
    printed scale at all and had to fall back on inference. Requiring a ratio someone actually
    plots at rejects all three and keeps every real one."""
    from app.pdf_import import parse_arch_scale
    for junk in ('1 1/4" = 1\'-0"', '2 1/4" = 1\'-0"', '3 1/4" = 1\'-0"'):
        assert parse_arch_scale(junk) is None, f"{junk} is a bubble number plus a scale"
    # the arithmetic itself was never wrong — it is the standard-ratio filter doing the work
    assert parse_arch_scale('1 1/4" = 1\'-0"', standard_only=False) == pytest.approx(9.6)
    for real, want in (('1/4" = 1\'-0"', 48), ('3/8" = 1\'-0"', 32), ('1/8" = 1\'-0"', 96),
                       ('1" = 20\'-0"', 240), ('1" = 1\'-0"', 12), ('3" = 1\'-0"', 4),
                       ('1/2" = 1\'-0"', 24), ('1/16" = 1\'-0"', 192)):
        assert parse_arch_scale(real) == pytest.approx(want), f"{real} is a real scale"


def test_a_scale_comes_back_clean_not_as_float_noise():
    """1/4" = 1'-0" was returning 48.00000000000001, which reaches a caller and an API response
    looking like a measurement rather than a ratio."""
    from app.pdf_import import parse_arch_scale
    assert repr(parse_arch_scale('1/4" = 1\'-0"')) == "48.0"
    assert repr(parse_arch_scale('1/8" = 1\'-0"')) == "96.0"


# =====================================================================================
# WHAT IS ON THIS SHEET. A details sheet is not one drawing — the real L406 carries nine, and
# they are NOT all at one scale: eight column sections at 1/4"=1'-0" and a wayfinding sign at
# 3/8". Treating such a sheet as having a single scale is wrong on its face.
# =====================================================================================
def _detail(title, scale_toks, x, y, step=6.0):
    """A detail as a rotated sheet lays it out: the title in one band, its scale one line over.
    Measured on the real L406 — title words at x 32.6, scale at x 24.2."""
    ws = [{"text": t, "x": x + 8.4, "y": y - k * step, "box": [0, 0, 8, 20]}
          for k, t in enumerate(title.split())]
    ws += [{"text": t, "x": x, "y": y - k * step, "box": [0, 0, 3, 6]}
           for k, t in enumerate(scale_toks)]
    return ws


def test_every_titled_detail_on_a_sheet_is_found_with_its_own_scale():
    from app.pdf_import import find_details
    ws = (_detail("MAIN COLUMN FRONT ELEVATION", ['1/4"', "=", "1'-0\""], 24.2, 115.3)
          + _detail("WAYFINDING SIGN", ['3/8"', "=", "1'-0\""], 205.2, 115.3))
    got = {d["title"]: d["scale"] for d in find_details(ws)}
    assert got == {"MAIN COLUMN FRONT ELEVATION": 48.0, "WAYFINDING SIGN": 32.0}, (
        "a sheet may mix scales and both must survive — L406 does exactly this")


def test_a_scale_bar_and_a_north_arrow_are_not_details():
    """FOUND ON THE REAL L201B. A plan sheet prints its scale under a scale bar and a north
    arrow, and reading a title back from those gave two phantom details, "N" and "SCALE:". A
    label ends in a colon; a north arrow is one letter. A real title is neither."""
    from app.pdf_import import find_details
    # EACH IN ITS OWN COLUMN, as the real sheet lays them out — L406's anchors sit at
    # x 24.2, 205.2, 394.6. Sharing one x made the second walk-back collect the FIRST
    # detail's scale text as its title, which is a fixture artefact and not a real layout.
    ws = (_detail("N", ['1"', "=", "20'-0\""], 24.2, 100.0)
          + _detail("SCALE:", ['1"', "=", "20'-0\""], 205.2, 100.0))
    assert find_details(ws) == [], "a plan sheet has no titled details"


def test_a_single_word_detail_survives_the_filter():
    """LOGO is detail 10 on the real L404. A two-word rule would have dropped it, which is why
    the filter tests for a label rather than for word count."""
    from app.pdf_import import find_details
    got = find_details(_detail("LOGO", ['1/4"', "=", "1'-0\""], 24.2, 50.0))
    assert [d["title"] for d in got] == ["LOGO"]


def test_each_detail_is_measured_at_its_own_scale_not_the_sheets():
    """THE REAL L406 MIXES SCALES: eight column sections at 1/4"=1'-0" and a wayfinding sign at
    3/8". Measuring the sign at the sheet's 1:48 understates it by a third, the arithmetic
    check then rejects the match, and the sign's dimensions VANISH rather than arrive wrong —
    which is worse, because nothing signals a problem. Per detail, they came back: six of them,
    three at 0.00% error."""
    from app.pdf_import import link_dimensions_by_detail
    details = [{"title": "COLUMN", "scale": 48.0, "x": 0.0, "y": 0.0},
               {"title": "SIGN", "scale": 32.0, "x": 500.0, "y": 0.0}]
    strokes, words = [], []
    strokes.append(_ln(0, 0, 1219.2 / 48.0, 0))                    # 4'-0" at 1:48
    words.append({"text": "4'-0\"", "x": 1219.2 / 48.0 / 2, "y": 2.0})
    strokes.append(_ln(500, 0, 500 + 1219.2 / 32.0, 0))            # 4'-0" at 1:32
    words.append({"text": "4'-0\"", "x": 500 + 1219.2 / 32.0 / 2, "y": 2.0})
    got = link_dimensions_by_detail(strokes, words, details, 48.0)
    by = {m["detail"]["title"]: m for m in got}
    assert set(by) == {"COLUMN", "SIGN"}, "both details must yield their dimension"
    assert by["SIGN"]["detail"]["scale"] == 32.0
    assert all(m["error"] < 1e-6 for m in got), "each measured at its own scale is exact"
    # the sheet scale alone finds only the one drawn at it
    from app.pdf_import import link_dimensions
    assert len(link_dimensions(strokes, words, 48.0)) == 1, (
        "a single sheet scale loses the other detail entirely — that is the bug")


def test_a_sheet_with_no_titled_details_falls_back_to_the_sheet_scale():
    """A plan sheet has no details. It must behave exactly as before, and say so by reporting
    a null detail rather than inventing one."""
    from app.pdf_import import link_dimensions_by_detail
    strokes = [_ln(0, 0, 1219.2 / 240.0, 0)]
    words = [{"text": "4'-0\"", "x": 1219.2 / 240.0 / 2, "y": 1.0}]
    got = link_dimensions_by_detail(strokes, words, [], 240.0)
    assert len(got) == 1 and got[0]["detail"] is None
    assert link_dimensions_by_detail(strokes, words, [], None) == []


# =====================================================================================
# WHICH STROKES BELONG TO WHICH DETAIL. A sheet holds 163,293 of them and nine details; a
# builder needs the few thousand that are one column. THE SHEET DRAWS THE ANSWER — a details
# sheet frames each detail, and on the real L406 the frames are an exact 181.0 x 368.3mm grid.
# =====================================================================================
def _rect(x0, y0, w, h):
    return [[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h], [x0, y0]]


def test_frames_are_found_and_the_outer_border_is_dropped_by_containment():
    """Dropping the LARGEST rectangle would also drop a legitimately large detail on a sheet
    with no border. The border is the one that holds the others."""
    from app.pdf_import import detail_frames
    strokes = [_rect(0, 0, 725, 952),          # the border
               _rect(19, 0, 181, 368), _rect(200, 0, 181, 368),
               _rect(5, 5, 10, 10)]            # too small to be a frame
    got = detail_frames(strokes)
    assert len(got) == 2, f"border and crumbs must go, frames must stay: {len(got)}"
    assert all(abs(f["w"] - 181) < 1 for f in got)


def test_every_detail_lands_in_exactly_one_frame_and_no_frame_takes_two():
    """MEASURED ON L406, AND THE PADDING WAS THE WHOLE FAULT:
         pad  0mm -> 9 of 9 details inside exactly one frame
         pad 12mm -> 3 of 9, with SIX inside several
    Frames abut with no gutter, so any padding puts an anchor inside its neighbour too. That
    caused one detail to claim two frames while two others got none."""
    from app.pdf_import import segment_by_frame
    strokes = [_rect(0, 0, 181, 368), _rect(181, 0, 181, 368)]
    # ANCHORS SIT NEAR THEIR FRAME'S EDGE, as on the real sheet: L406's frame starts at
    # x 19.4 and its scale text is at x 24.2, FOUR POINT EIGHT mm inside. A fixture with 20mm
    # of clearance survives a 12mm padding and proves nothing — the mutation passed it.
    details = [{"title": "COLUMN", "scale": 48.0, "x": 5.0, "y": 20.0},
               {"title": "SIGN", "scale": 32.0, "x": 186.0, "y": 20.0}]
    segs = segment_by_frame(strokes, details)
    titles = [s["title"] for s in segs if s["title"]]
    assert sorted(titles) == ["COLUMN", "SIGN"], f"one each, got {titles}"
    assert len(titles) == len(set(titles)), "no detail may claim two frames"


def test_a_frame_with_no_title_keeps_its_geometry():
    """On a real sheet an untitled frame is a detail whose title did not parse. Dropping it
    would discard that geometry silently, which is the failure this whole module exists to
    avoid — an absent answer looks like an empty sheet."""
    from app.pdf_import import segment_by_frame
    strokes = [_rect(0, 0, 181, 368), _ln(20, 20, 60, 60)]
    segs = segment_by_frame(strokes, [])
    assert len(segs) == 1 and segs[0]["title"] is None
    assert segs[0]["strokes"], "the strokes inside it are still reported"


# =====================================================================================
# CROPPING ONE DETAIL FOR A PERSON TO TRACE. The silhouette cannot be extracted automatically
# — a construction detail draws the thing IN ITS CONTEXT, and on L406 the ink covers six times
# the object's area. So the trace stays, and this is what makes it cheap.
# =====================================================================================
def test_a_plan_sheet_is_not_offered_as_a_detail_to_trace():
    """MEASURED: L201B and L400 each yield two frames — the 725 x 951.8mm sheet border and a
    61mm seal box. Neither contains the other, so containment drops neither and both survive
    untitled. Handing a whole site plan back as "detail 0" would be worse than a 404.

    The refusal is STRUCTURAL rather than a special case: the listing carries only TITLED
    details, so a plan sheet produces an empty list and there is nothing to index. That is the
    better shape — a guard that has to recognise a plan sheet is a guard that can fail to.

    THIS USED TO BE A SOURCE-STRING ASSERTION (`'if not segs:' in src`), which this file's own
    rules say not to write: it survives any rewrite that keeps the string and breaks the
    behaviour, and it went red on a rename that fixed a real bug. Now it drives the endpoint."""
    from fastapi.testclient import TestClient
    from app.main import app
    raw = _plan_only_pdf()
    c = TestClient(app)
    listed = c.post("/import/pdf/sheet", files={"file": ("p.pdf", raw, "application/pdf")},
                    data={"page": 0}).json()
    assert listed["details"] == [], "a plan sheet has no titled details to offer"
    r = c.post("/import/pdf/detail", files={"file": ("p.pdf", raw, "application/pdf")},
               data={"page": 0, "detail": 0, "dpi": 72})
    assert r.status_code == 404, "a whole site plan handed back as 'detail 0' is worse than a 404"
    assert "plan or a schedule" in r.json()["detail"]




# =====================================================================================
# A REAL PDF, BUILT IN THE TEST. The checks above for rotation and for the endpoints were
# source-string assertions — they would survive a rewrite that kept the strings and broke the
# behaviour. PyMuPDF can WRITE a PDF, so the fixture is a genuine one: a framed detail with a
# title, its own scale, and a dimension of known length, rendered at rotation 0 and 270.
#
# **ROTATION 270 IS THE POINT.** Every sheet in the real set carries it, and it hid a y-flip
# bug through the entire build: nothing RELATIVE could see a uniform 304.8mm offset. With the
# flip reverted, the upright page still passes and the rotated one returns a crop 892px wide
# where 1960 is right — which is exactly how the bug behaved.
# =====================================================================================
def _sheet_pdf(rotation: int = 0) -> bytes:
    fitz = pytest.importorskip("fitz")
    from app.pdf_import import PT_MM
    doc = fitz.open()
    page = doc.new_page(width=2160, height=3024)        # the shape of a real mediabox here
    page.draw_rect(fitz.Rect(100, 100, 700, 1500), color=(0, 0, 0), width=1)
    page.insert_text((120, 1400), "MAIN COLUMN FRONT ELEVATION", fontsize=14)
    page.insert_text((120, 1430), '1/4" = 1\'-0"', fontsize=9)
    L = 1219.2 / 48.0 / PT_MM                            # 4'-0" at 1:48, in points
    page.draw_line(fitz.Point(200, 400), fitz.Point(200 + L, 400), color=(0, 0, 0), width=1)
    page.insert_text((200 + L / 2 - 10, 392), "4'-0\"", fontsize=8)
    if rotation:
        page.set_rotation(rotation)
    return doc.tobytes()


@pytest.mark.parametrize("rotation", [0, 270])
def test_a_whole_sheet_reads_end_to_end_at_either_rotation(rotation):
    from app.pdf_import import read_sheet
    sh = read_sheet(_sheet_pdf(rotation), page_index=0)
    assert len(sh["details"]) == 1
    d = sh["details"][0]
    assert d["title"] == "MAIN COLUMN FRONT ELEVATION" and d["scale"] == pytest.approx(48.0)
    assert d["frame"], "a listed detail carries the frame its geometry lives in"
    assert len(sh["dimensions"]) == 1
    m = sh["dimensions"][0]
    assert m["mm"] == pytest.approx(1219.2) and m["error"] < 1e-6
    assert m["detail"]["title"] == "MAIN COLUMN FRONT ELEVATION"

    # THE FRAME'S ABSOLUTE POSITION, which is the only thing that catches the y flip.
    # The fixture draws it at PDF points (100, 100, 700, 1500) on an unrotated page 3024 tall,
    # and our millimetres measure y UPWARD from the page bottom, so:
    #     y0 = (3024 - 1500) * PT_MM = 537.8    y1 = (3024 - 100) * PT_MM = 1031.9
    # Flipping against `page.rect.height` (2160 on this rotated page) shifts every y by
    # 304.8mm. **Nothing relative can see that** — the frame, the strokes and the crop all move
    # together, so sizes, spans, errors and even a crop's ink content survive it. Only an
    # absolute check does, which is why it hid through the entire build.
    from app.pdf_import import PT_MM
    f = d["frame"]
    assert f["x0"] == pytest.approx(100 * PT_MM, abs=1.0)
    assert f["y0"] == pytest.approx((3024 - 1500) * PT_MM, abs=1.0)
    assert f["y1"] == pytest.approx((3024 - 100) * PT_MM, abs=1.0)


@pytest.mark.parametrize("rotation", [0, 270])
def test_a_crop_covers_its_frame_at_either_rotation(rotation):
    """THIS IS THE ONE THAT CATCHES THE FLIP. Reverted to `page.rect.height`, rotation 0 still
    passes and rotation 270 returns 892px where 1960 is right — a plausible-looking image of
    the wrong part of the page."""
    from app.pdf_import import read_sheet, render_detail
    raw = _sheet_pdf(rotation)
    d = read_sheet(raw, page_index=0)["details"][0]
    r = render_detail(raw, 0, d["frame"], dpi=100)
    w_mm, h_mm = r["frame_mm"]["w"], r["frame_mm"]["h"]
    if r["axes_swapped"]:
        w_mm, h_mm = h_mm, w_mm
    assert r["width"] == pytest.approx(w_mm / 25.4 * 100, abs=3)
    assert r["height"] == pytest.approx(h_mm / 25.4 * 100, abs=3)
    assert r["rotation"] == rotation and r["axes_swapped"] == (rotation in (90, 270))

    # AND IT MUST CONTAIN THE DRAWING, not merely be the right SIZE. Size survives a
    # translation, so a crop that lands on blank paper passes a size check — which is exactly
    # what happened: mutating `extract_geometry`'s flip shifts the frame and the crop TOGETHER
    # by 304.8mm, the size stays right, and only the content shows the miss.
    Image = pytest.importorskip("PIL.Image", reason="needs Pillow to inspect the crop")
    import io
    im = Image.open(io.BytesIO(r["png"])).convert("L")
    px = im.load()
    dark = sum(1 for yy in range(0, im.height, 3) for xx in range(0, im.width, 3)
               if px[xx, yy] < 200)
    assert dark > 20, (
        f"the crop is blank ({dark} dark pixels) — it is the right size and the wrong place")


def test_the_listing_and_the_crop_agree_on_which_detail_is_which():
    """These indexed DIFFERENT lists — the listing from `find_details`, the crop from the frame
    segmentation — so `detail=0` returned an untitled frame while the listing's first entry was
    MAIN COLUMN FRONT ELEVATION. A client picking by index would have displayed one drawing and
    traced another, with nothing to signal it."""
    from fastapi.testclient import TestClient
    from app.main import app
    raw = _sheet_pdf(270)
    c = TestClient(app)
    files = {"file": ("t.pdf", raw, "application/pdf")}
    listed = c.post("/import/pdf/sheet", files=files, data={"page": 0}).json()["details"]
    got = c.post("/import/pdf/detail", files={"file": ("t.pdf", raw, "application/pdf")},
                 data={"page": 0, "detail": 0, "dpi": 100}).json()
    assert got["title"] == listed[0]["title"], "index 0 must be the same detail in both"
    assert got["scale"] == listed[0]["scale"]
    import base64
    assert base64.b64decode(got["png_base64"])[:4] == b"\x89PNG"


def _plan_only_pdf() -> bytes:
    """A sheet with line work and a scale bar but no titled detail — a site plan.

    A plan prints its scale under a SCALE BAR and a north arrow, which is what gave L201B two
    phantom details called "N" and "SCALE:" before the title rules were tightened. So the
    fixture carries both, and a plan that yields an empty listing is the property under test.
    """
    doc = fitz.open()
    page = doc.new_page(width=2160, height=3024)
    page.draw_rect(fitz.Rect(60, 60, 2100, 2960), color=(0, 0, 0), width=1)   # sheet border
    page.insert_text((200, 1500), "N", fontsize=12)
    page.insert_text((400, 1500), "SCALE:", fontsize=9)
    page.insert_text((470, 1500), '1" = 20\'-0"', fontsize=9)
    page.draw_line(fitz.Point(300, 800), fitz.Point(900, 800), color=(0, 0, 0), width=1)
    return doc.tobytes()


def _mixed_sheet_pdf(rotation: int = 0) -> bytes:
    """Two titled details, and ONLY THE SECOND IS BOXED.

    This is the fixture the index test was missing. `read_sheet` lists every titled detail and
    attaches a frame to the ones it can place, so a sheet where one detail is drawn without a
    border — or whose frame did not parse — leaves a listed entry with `frame: None`. The crop
    used to index a FILTERED copy of that list, so everything after the unframed entry shifted
    by one. A fixture where every detail is framed cannot see that, which is why the bug came
    back: the old fixture reproduced the shape of the sheet, not the geometry that caused it.

    The unframed one is drawn FIRST so it takes index 0 and shifts the other.
    """
    doc = fitz.open()
    page = doc.new_page(width=2160, height=3024)
    # 1. unboxed — no rectangle around it
    page.insert_text((120, 400), "WAYFINDING SIGN", fontsize=14)
    page.insert_text((120, 430), '3/8" = 1\'-0"', fontsize=9)
    # 2. boxed, the way a details sheet draws one
    page.draw_rect(fitz.Rect(100, 900, 700, 2300), color=(0, 0, 0), width=1)
    page.insert_text((120, 2200), "MAIN COLUMN FRONT ELEVATION", fontsize=14)
    page.insert_text((120, 2230), '1/4" = 1\'-0"', fontsize=9)
    L = 1219.2 / 48.0 / PT_MM
    page.draw_line(fitz.Point(200, 1200), fitz.Point(200 + L, 1200), color=(0, 0, 0), width=1)
    page.insert_text((200 + L / 2 - 10, 1192), "4'-0\"", fontsize=8)
    if rotation:
        page.set_rotation(rotation)
    return doc.tobytes()


@pytest.mark.parametrize("rotation", [0, 270])
def test_an_unframed_detail_does_not_shift_every_index_after_it(rotation):
    """THE SAME FAULT AS BEFORE, WEARING THE FIX FOR IT.

    `/import/pdf/sheet` publishes every titled detail; `/import/pdf/detail` used to index
    `[d for d in sheet["details"] if d.get("frame")]`. One unplaceable detail and the two lists
    part company. Measured on this fixture at both rotations before the fix:

        listing index 0 = WAYFINDING SIGN            crop returned MAIN COLUMN FRONT ELEVATION
        listing index 1 = MAIN COLUMN FRONT ELEVATION  ->  404 "detail 1 of 1"

    Both halves are pinned here, because they fail in opposite directions: the first hands back
    the wrong drawing with a title and scale that agree with it, and the second refuses the one
    detail on the page that can actually be cropped.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    raw = _mixed_sheet_pdf(rotation)
    c = TestClient(app)

    def files():
        return {"file": ("m.pdf", raw, "application/pdf")}

    listed = c.post("/import/pdf/sheet", files=files(), data={"page": 0}).json()["details"]
    titles = [d["title"] for d in listed]
    assert titles == ["WAYFINDING SIGN", "MAIN COLUMN FRONT ELEVATION"], titles
    assert not listed[0]["frame"] and listed[1]["frame"], "the fixture must reproduce the cause"

    # the framed one is at index 1 in the listing, so index 1 has to crop it
    ok = c.post("/import/pdf/detail", files=files(), data={"page": 0, "detail": 1, "dpi": 72})
    assert ok.status_code == 200, ok.text
    assert ok.json()["title"] == "MAIN COLUMN FRONT ELEVATION"
    assert ok.json()["scale"] == pytest.approx(48.0)

    # and index 0 must refuse rather than hand back its neighbour's picture
    bad = c.post("/import/pdf/detail", files=files(), data={"page": 0, "detail": 0, "dpi": 72})
    assert bad.status_code == 404, (
        "an unboxed detail has no frame to crop — returning the next one is the bug")
    assert "not boxed" in bad.json()["detail"]
    assert "WAYFINDING SIGN" in bad.json()["detail"], "say WHICH detail could not be cropped"


@pytest.mark.parametrize("rotation", [0, 270])
def test_a_crop_reports_the_paper_it_actually_covers(rotation):
    """`frame_mm` is what the other end DIVIDES A TRACED SPAN BY, so it has to describe the
    image rather than the request.

    `get_pixmap(clip=)` intersects the clip with the page, and a frame drawn at the sheet edge
    runs off it as soon as the 2mm margin is added. Reporting the requested rectangle then
    overstates the paper and `drawnSpanToReal` returns a building that is plausible and quietly
    small — the same silent-size failure as the axes swap and the 304.8mm offset.

    Measured on a frame at x0 = 0 before the fix: the image came back 842px where the reported
    215.67mm wanted 849px. Small here because the margin is 2mm of 215; it is bounded only by
    how far the frame runs off the sheet.
    """
    from app.pdf_import import read_sheet, render_detail
    doc = fitz.open()
    page = doc.new_page(width=2160, height=3024)
    page.draw_rect(fitz.Rect(0, 100, 600, 1500), color=(0, 0, 0), width=1)   # ON the page edge
    page.insert_text((20, 1400), "EDGE DETAIL ELEVATION", fontsize=14)
    page.insert_text((20, 1430), '1/4" = 1\'-0"', fontsize=9)
    if rotation:
        page.set_rotation(rotation)
    raw = doc.tobytes()

    d = read_sheet(raw, page_index=0)["details"][0]
    assert d["frame"] and d["frame"]["x0"] == pytest.approx(0.0, abs=0.5), (
        "the fixture must put the frame ON the edge, or the clip is never truncated")
    r = render_detail(raw, 0, d["frame"], dpi=100)
    w_mm, h_mm = r["frame_mm"]["w"], r["frame_mm"]["h"]
    if r["axes_swapped"]:
        w_mm, h_mm = h_mm, w_mm
    assert r["width"] == pytest.approx(w_mm / 25.4 * 100, abs=1.5)
    assert r["height"] == pytest.approx(h_mm / 25.4 * 100, abs=1.5)
    # and the origin has to stay on the page, not one margin off the left of it
    assert r["origin_mm"]["x"] >= -1e-6, "a crop cannot start at negative paper"
