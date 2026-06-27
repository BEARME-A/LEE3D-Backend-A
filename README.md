# LEE3D-Backend-A

FastAPI service that does the heavy lifting the browser can't: **true
boolean-cut wheel openings**, OpenCascade shelling, **STEP** export, drawing/PDF
import via OpenCV/PyMuPDF, a SQLite index, and committing artefacts into
`LEE3D-Lib`.

Repo: `https://github.com/BEARME-A/LEE3D-Backend-A`

## Setup

CadQuery needs OpenCascade, which is **not** reliable via `pip`. Use conda:

```bash
conda env create -f environment.yml     # python 3.11 + cadquery 2.4 + everything
conda activate lee3d
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for interactive API docs.

> The API **boots without the CAD kernel** too (e.g. `pip install -r
> requirements.txt`). In that mode every endpoint works except `/generate`,
> which returns a clear `503` telling you to set up the conda env. This keeps
> imports, storage, and library commits usable while you sort CAD out.

## Endpoints

| Method | Path | Does |
|---|---|---|
| GET | `/health`, `/` | liveness + service info |
| POST | `/projects` · GET `/projects` · GET `/projects/{id}` | project index (SQLite) |
| POST | `/generate?fmt=stl\|step` | **Profile → printable body.** Body is the exported `profile.json`; options are query params (`open_bottom`, `cut_wheels`, `section`, `commit_to_library`). |
| POST | `/import/image` | drawing/photo → suggested outline (OpenCV) |
| POST | `/import/pdf` | PDF → page PNGs to trace (PyMuPDF) |
| POST | `/library/commit` | write a base64 file into `LEE3D-Lib` |

Example:
```bash
curl -X POST "http://localhost:8000/generate?fmt=step&cut_wheels=true" \
     -H "Content-Type: application/json" \
     --data @../LEE3D-Lib/projects/example-charger/example-charger.profile.json \
     -o charger.step
```

## Configuration (env vars)

Copy `.env.example` → `.env`. Key ones:

- `LEE3D_GITHUB_TOKEN` — fine-grained PAT with **Contents: read & write on
  `LEE3D-Lib` only**. Enables library commits. Never commit this.
- `LEE3D_CORS_ORIGINS` — where the frontend is served, e.g.
  `https://bearme-a.github.io`.
- `LEE3D_DATA_DIR` — where SQLite + generated files live (default `./data`).

## Deploy

**Local Docker (free, always-on):**
```bash
docker build -t lee3d .
docker run -p 8000:8000 -v $PWD/data:/data \
  -e LEE3D_GITHUB_TOKEN=*** lee3d
```

**Render (free tier, sleeps when idle):** push with `render.yaml`, then set
`LEE3D_GITHUB_TOKEN` in the dashboard.

## Tests

```bash
PYTHONPATH=. python tests/test_storage.py   # SQLite, no network
PYTHONPATH=. python tests/test_cad.py       # CAD smoke test (skips without cadquery)
```

## How the body is built

`app/cad.py` lofts the profile's cross-sections into a solid, shells the
underside to a wall thickness for a printable body shell, then boolean-cuts a
cylinder per wheel (axis across the width) for true openings, and exports STL or
STEP. It mirrors the browser's loft but with a real B-rep kernel, so the result
stays editable in any CAD package.
