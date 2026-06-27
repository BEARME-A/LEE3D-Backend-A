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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
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


@app.get("/health")
def health():
    return {"ok": True}


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
