"""
LEE3D-Backend-A — FastAPI service.

Run locally:
    conda env create -f environment.yml && conda activate lee3d
    uvicorn app.main:app --reload --port 8000

Interactive docs at http://localhost:8000/docs

Endpoints
    GET  /health
    GET  /                      -> tiny service info
    POST /projects              -> create a project
    GET  /projects              -> list projects
    GET  /projects/{id}         -> project detail (files + versions)
    POST /generate              -> Profile -> STL or STEP (streamed download)
    POST /import/image          -> drawing/photo -> suggested outline
    POST /import/pdf            -> PDF -> page PNGs to trace
    POST /library/commit        -> push a file into LEE3D-Lib
"""
from __future__ import annotations
import base64
import io
import json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from . import config, storage
from .schemas import Profile, GenerateOptions, ProjectIn, CommitFile

app = FastAPI(title="LEE3D-Backend-A", version=config.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    storage.init_db()


@app.get("/")
def root():
    return {
        "service": "LEE3D-Backend-A",
        "version": config.APP_VERSION,
        "library": f"{config.GITHUB_OWNER}/{config.GITHUB_LIB_REPO}",
        "library_writable": storage.library_configured(),
        "docs": "/docs",
    }


def _cad_available() -> bool:
    """Is the CAD kernel in THIS image? Checked without importing it — OpenCascade is
    slow and heavy to load, and the answer is only needed to report a capability."""
    import importlib.util
    try:
        return importlib.util.find_spec("cadquery") is not None
    except Exception:
        return False


@app.get("/health")
def health():
    """Health, plus what this image can actually DO.

    The studio used to probe /health, get {"ok": true} and report "connected" — which was
    true and useless: the light image answers /health perfectly and cannot build a STEP.
    So "connected" appeared and then exact build failed, with nothing linking the two.
    Now the capabilities ride along and the studio can say which image it reached.
    """
    return {
        "ok": True,
        "version": config.APP_VERSION,
        "cad": _cad_available(),          # False on the light image -> no exact build
        "library_writable": storage.library_configured(),
        "image": "full" if _cad_available() else "light",
    }


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------
@app.post("/projects")
def create_project(body: ProjectIn):
    return storage.create_project(body.name, body.notes)


@app.get("/projects")
def list_projects():
    return storage.list_projects()


@app.get("/projects/{pid}")
def get_project(pid: int):
    p = storage.get_project(pid)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


# --------------------------------------------------------------------------
# Exact build (OpenCascade) — the "make it real" pass
# --------------------------------------------------------------------------
@app.post("/solid")
def solid(
    profile: dict = Body(...),
    fmt: str = Query("step", pattern="^(step|stl)$"),
    hollow: bool | None = Query(None),
    plan_only: bool = Query(False),
):
    """
    The studio's traced outlines -> one exact solid, via OpenCascade.

    The browser builds the same shape on a voxel grid, which is fast and always watertight
    but can only ever *move* the surface it has: a window gets dished, never cut through,
    and a corner is only as sharp as the grid. Here the outlines are extruded and
    intersected for real, and a feature marked "through" becomes an actual hole.

    Takes the profile exactly as the studio exports it — no separate schema to drift.
    `plan_only=true` reports what the build would do without needing OpenCascade, which is
    handy for checking the wiring on the light image.
    """
    from .hull import plan, export_bytes, CadUnavailable
    try:
        p = plan(profile)
    except Exception as e:
        raise HTTPException(400, f"Couldn't read that profile: {e}")

    # The profile already says whether this is a shell or a lump, so an unset query flag
    # means "do what the studio asked". It used to default to False, and since the studio
    # never sent the flag at all, every exact build came back solid next to a hollow
    # preview. Passing ?hollow=true/false still overrides, for anyone driving the API
    # directly.
    if hollow is None:
        hollow = bool(p["hollow"])

    if plan_only:
        # SAY WHAT WILL ACTUALLY BE BUILT, feature by feature. This used to report two buckets
        # and a note claiming the skipped ones were "dishes/bosses the studio already does" —
        # which stopped being true when the studio started cutting them as real geometry, and
        # left someone able to download a STEP with none of their detail in it and no warning.
        built = len(p["through_cuts"]) + len(p["pockets"]) + len(p["raises"])
        return {
            "dims": p["dims"],
            "through_cuts": [f["name"] for f in p["through_cuts"]],
            "pockets": [f["name"] for f in p["pockets"]],
            "raises": [f["name"] for f in p["raises"]],
            "surface_only": [f["name"] for f in p["surface_only"]],
            "features_built": built,
            "features_skipped": len(p["surface_only"]),
            # the studio can carve from silhouettes at any angle; this build intersects the
            # three axis outlines only, so it would come out FATTER. Say so.
            "unusable_views": p["unusable_views"],
            # SCALE. `dims` is the MODEL, which is what gets printed; these say what the model
            # stands for. Without them the scale a profile carries is computed here and thrown
            # away, and nothing downstream can tell a 120mm building at 1:200 from a 120mm one
            # at 1:100 — which is the whole point of keeping the real figure.
            "real_dims": p.get("real_dims"),
            # A real length and a scale can contradict the model length, and then the model is
            # not the scale it claims. Reported the way unusable_views is, never resolved here.
            "scale_mismatch": p.get("scale_mismatch"),
            "hollow": hollow,
            "wall": p["wall"],
            "ignored_second_side": p["ignored_second_side"],
            "note": (
                "Cuts, pockets and raises are all built as real geometry. "
                "surface_only covers masks and text labels, which have no solid meaning."
                if not p["surface_only"] and not p["unusable_views"] else
                f"This model carves from {p['unusable_views']} extra view(s) that the exact "
                "build cannot use — it intersects the three axis outlines only, so the result "
                "will be FATTER than the preview. Everything else is built."
                if p["unusable_views"] else
                f"{len(p['surface_only'])} feature(s) are masks or labels with no depth, so they "
                "have no solid meaning and are not in the exact build. Everything else is."
            ),
        }
    # WHAT THE PLAN CANNOT KNOW. `plan()` reports hollow:true because the profile asked for a
    # shell — not because one was built. When the cavity comes out empty the build catches it,
    # prints, and hands back a SOLID; until now that never left `build_solid`, so the studio
    # could download a solid lump from a request that reported hollow:true and nothing said so.
    # Same lesson as the pockets and the extra views: a quiet difference between the two ends
    # is worse than a loud limitation.
    report: dict = {}
    try:
        data, mime, name = export_bytes(profile, fmt=fmt, hollow=hollow, report=report)
    except CadUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Exact build failed: {e}")

    return StreamingResponse(
        io.BytesIO(data), media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{name}"',
                 "X-LEE3D-Through-Cuts": str(len(p["through_cuts"])),
                 # so the studio can say "this STEP has your 153 pockets in it" — or, if it
                 # ever cannot build something, say THAT instead of shipping it silently
                 "X-LEE3D-Pockets": str(len(p["pockets"])),
                 "X-LEE3D-Raises": str(len(p["raises"])),
                 "X-LEE3D-Skipped": str(len(p["surface_only"])),
                 "X-LEE3D-Unusable-Views": str(p["unusable_views"]),
                 # "1" only when a shell was ASKED FOR and the cavity could not be built, so
                 # this file is solid. "0" covers both "hollowed fine" and "never asked" —
                 # the studio only needs to warn about the one case where what it got is not
                 # what the plan said it would get.
                 "X-LEE3D-Hollow-Failed": "1" if report.get("hollow_failed") else "0",
                 # the studio reads this and tells the user, rather than the STEP quietly
                 # being a different shape from the preview it was built beside
                 "X-LEE3D-Symmetric-Only": "1" if p["ignored_second_side"] else "0"},
    )


# --------------------------------------------------------------------------
# Generate (CadQuery)
# --------------------------------------------------------------------------
@app.post("/generate")
def generate(
    profile: Profile,
    fmt: str = Query("stl", pattern="^(stl|step)$"),
    open_bottom: bool = Query(True),
    cut_wheels: bool = Query(True),
    section: str = Query("super", pattern="^(ellipse|super)$"),
    commit_to_library: bool = Query(False),
    project_id: int | None = Query(None),
):
    """
    Turn a Profile into a printable body. The request body is exactly the
    profile.json the frontend exports; generator options are query params.
    Returns the STL/STEP as a download, optionally committing a copy to
    LEE3D-Lib (generated/).
    """
    options = GenerateOptions(
        fmt=fmt, open_bottom=open_bottom, cut_wheels=cut_wheels,
        section=section, commit_to_library=commit_to_library, project_id=project_id,
    )
    from .cad import generate_bytes, CadUnavailable
    try:
        data, mime, name = generate_bytes(profile, options)
    except CadUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {e}")

    # record a version row regardless
    vid = storage.record_version(options.project_id, profile.model_dump_json(by_alias=True))

    headers = {"Content-Disposition": f'attachment; filename="{name}"',
               "X-LEE3D-Version-Id": str(vid)}

    if options.commit_to_library and storage.library_configured():
        path = storage.library_path("generated", profile.name, name)
        try:
            info = storage.commit_file(path, data, f"LEE3D: generate {name}")
            storage.record_file(options.project_id, "generated", path, info.get("sha"))
            headers["X-LEE3D-Library-Url"] = info.get("commit_url") or ""
        except Exception as e:
            headers["X-LEE3D-Library-Error"] = str(e)[:200]

    return StreamingResponse(io.BytesIO(data), media_type=mime, headers=headers)


# --------------------------------------------------------------------------
# Imports
# --------------------------------------------------------------------------
@app.post("/import/image")
async def import_image(file: UploadFile = File(...),
                       commit: bool = Form(False),
                       project: str = Form("misc")):
    from .vision import extract_outline, VisionUnavailable
    raw = await file.read()
    try:
        result = extract_outline(raw)
    except VisionUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(422, f"Could not process image: {e}")

    if commit and storage.library_configured():
        kind = "photo" if (file.content_type or "").endswith(("jpeg", "jpg")) else "drawing"
        path = storage.library_path(kind, project, file.filename or "drawing.png")
        try:
            info = storage.commit_file(path, raw, f"LEE3D: import {file.filename}")
            storage.record_file(None, kind, path, info.get("sha"))
            result["library"] = info
        except Exception as e:
            result["library_error"] = str(e)[:200]

    return result


@app.post("/import/pdf")
async def import_pdf(file: UploadFile = File(...), dpi: int = Form(150)):
    from .pdf_import import render_pages, PdfUnavailable
    raw = await file.read()
    try:
        return render_pages(raw, dpi=dpi)
    except PdfUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(422, f"Could not read PDF: {e}")


@app.post("/import/pdf/geometry")
async def import_pdf_geometry(file: UploadFile = File(...), page: int = Form(0),
                              curve_steps: int = Form(12)):
    """The line work and the callouts, not a picture of them.

    /import/pdf rasterises, which is right for showing someone a page and wrong for building
    from one. A plotted drawing carries its geometry as real paths and its dimensions as real
    text with real coordinates — so a site plan can be built to the numbers on it rather than
    traced off pixels, and the height callouts can be read rather than typed. Strokes come
    back in millimetres on the page with y reading upward, which is the frame the studio's
    stitcher already works in.
    """
    from .pdf_import import extract_geometry, PdfUnavailable
    raw = await file.read()
    try:
        return extract_geometry(raw, page_index=page, curve_steps=curve_steps)
    except PdfUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(422, f"Could not read PDF: {e}")


@app.post("/import/pdf/sheet")
async def import_pdf_sheet(file: UploadFile = File(...), page: int = Form(0),
                           want_geometry: bool = Form(False)):
    """Everything one plotted page can tell you, in the shape LEE3D-Lib publishes.

    /import/pdf/geometry returns raw line work; this returns what it MEANS — which sheet it is,
    what scale each detail is drawn at, which dimensions belong to which detail, and any survey
    points. The contract is `LEE3D-Lib/schema/sheet.schema.json`, so the studio and the exact
    build read a drawing the same way rather than each calling the parsers their own way.

    Bulk geometry is omitted unless asked for: a real sheet carries 163,000 strokes, and a
    client that only wants to know what is on the page should not be sent them.
    """
    from .pdf_import import read_sheet, PdfUnavailable
    raw = await file.read()
    try:
        return read_sheet(raw, page_index=page, want_geometry=want_geometry)
    except PdfUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(422, f"Could not read PDF: {e}")


@app.post("/import/pdf/detail")
async def import_pdf_detail(file: UploadFile = File(...), page: int = Form(0),
                            detail: int = Form(0), dpi: int = Form(300)):
    """One framed detail as an image, for a person to trace.

    **The silhouette cannot be extracted automatically.** A construction detail draws the thing
    IN ITS CONTEXT — measured on L406, the ink covers six times the object's area, because the
    frame holds the column plus its footing, the finished grade and the compacted subgrade.
    Which of those is "the object" is a judgement the geometry does not carry. So the trace
    stays; this makes it cheap by handing over ONE detail at its own known scale instead of a
    725 x 952mm sheet.

    `detail` indexes the frames `/import/pdf/sheet` reports, so a client picks from what it was
    already shown. The scale comes back with the image because it belongs to THAT detail and
    may differ from the sheet's — L406 mixes 1/4" and 3/8" on one page.
    """
    from .pdf_import import read_sheet, render_detail, PdfUnavailable
    import base64
    raw = await file.read()
    try:
        sheet = read_sheet(raw, page_index=page)
        # ONE LIST, ONE INDEX — and this is the list `/import/pdf/sheet` publishes.
        #
        # This used to index `[d for d in sheet["details"] if d.get("frame")]`, a FILTERED copy.
        # `read_sheet` attaches a frame to each listed detail but keeps the ones it could not
        # place, so the moment a single detail lands in no frame every index after it shifts by
        # one and the crop returns somebody else's drawing — the exact fault this project
        # already fixed once between these two endpoints, reintroduced by the fix for it.
        # Reproduced on a built two-detail sheet at rotation 0 and 270: the listing showed
        # WAYFINDING SIGN at index 0 and the crop handed back MAIN COLUMN FRONT ELEVATION,
        # while index 1 — the detail that IS croppable — 404'd as "detail 1 of 1".
        #
        # So index `sheet["details"]` itself, and say which of the two things went wrong.
        details = sheet["details"]
        # A PAGE WITH NO TITLED DETAIL IS NOT A DETAILS SHEET. Measured: L201B and L400 each
        # yield two frames — the 725 x 951.8mm sheet border and a 61mm seal box — which do not
        # contain one another, so neither is dropped by containment and both survive as
        # untitled. Handing back a whole site plan as "detail 0" would be worse than a 404.
        # The titled test is what separates them: real details sheets title nearly all of
        # theirs (9 of 10 on L406, 10 of 11 on L405, 10 of 13 on L404).
        if not details:
            raise HTTPException(404, "this page has no titled details — it is a plan or a schedule")
        if detail < 0 or detail >= len(details):
            raise HTTPException(404, f"detail {detail} of {len(details)} on this page")
        seg = details[detail]
        # A DETAIL THE SHEET NEVER BOXED CANNOT BE CROPPED, and that is its own answer rather
        # than the next detail's picture. Returning a neighbour here is worse than a 404: the
        # title and scale would come back consistent with the image and nothing downstream
        # could tell it was the wrong drawing.
        if not seg.get("frame"):
            raise HTTPException(
                404, f"{seg.get('title') or 'that detail'} is not boxed on this sheet, "
                     f"so there is no frame to crop — trace the page as an image instead")
        img = render_detail(raw, page, seg["frame"], dpi=dpi)
        return {"title": seg["title"], "scale": seg["scale"],
                "png_base64": base64.b64encode(img["png"]).decode("ascii"),
                **{k: v for k, v in img.items() if k != "png"}}
    except HTTPException:
        raise
    except PdfUnavailable as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(422, f"Could not read PDF: {e}")


# --------------------------------------------------------------------------
# Library
# --------------------------------------------------------------------------
@app.post("/library/commit")
def library_commit(f: CommitFile):
    """Write any base64 file into LEE3D-Lib (used by the frontend 'Save to library')."""
    if not storage.library_configured():
        raise HTTPException(503, "Library not configured (set LEE3D_GITHUB_TOKEN).")
    try:
        content = base64.b64decode(f.content_base64)
    except Exception:
        raise HTTPException(400, "content_base64 is not valid base64.")
    try:
        info = storage.commit_file(f.path, content, f.message)
    except Exception as e:
        raise HTTPException(502, f"GitHub commit failed: {e}")
    storage.record_file(None, "export", f.path, info.get("sha"))
    return JSONResponse(info)
