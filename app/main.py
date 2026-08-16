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
    try:
        data, mime, name = export_bytes(profile, fmt=fmt, hollow=hollow)
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
