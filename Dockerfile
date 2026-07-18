# FULL image — bundles the OpenCascade CAD kernel (conda-forge `cadquery`), so the
# "make it real" endpoints return genuine geometry:
#     POST /solid          -> exact STEP/STL, real cut-through openings
#     POST /generate?fmt=step
# The light ./Dockerfile deploys in ~2 min and runs everything EXCEPT those two, which
# return a clear 503. Use this image when you want CAD export.
#
# HEADS UP: OpenCascade is large. This image is multi-GB and will NOT fit Render's free
# tier (512 MB). Options:
#   * Render paid instance — in render.yaml set `dockerfilePath: ./Dockerfile.full`
#     and a paid `plan:` (e.g. starter), then redeploy.
#   * Google Cloud Run / Fly.io / any box that allows a big image.
#   * Locally:
#       docker build -f Dockerfile.full -t lee3d-backend-full .
#       docker run -p 8000:8000 -e LEE3D_GITHUB_TOKEN=ghp_xxx lee3d-backend-full
#     then point the studio's Backend URL at http://localhost:8000
#
# WHY conda and not pip: cadquery pulls OpenCascade (OCP), which has no reliable wheels
# across platforms. conda-forge ships prebuilt binaries, so the env just resolves. This
# uses the SAME environment.yml the repo already documents for local dev — one source of
# truth, nothing to keep in sync.

FROM mambaorg/micromamba:1.5.8

# Runtime shared libs that OpenCV (headless) and OpenCascade expect on the slim base.
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*
USER $MAMBA_USER

WORKDIR /app

# Solve the environment FIRST so this heavy layer is cached and app edits don't re-solve it.
# Install into the base env (-n base); micromamba's entrypoint activates base at runtime,
# so CMD runs with cadquery importable. `clean --all` drops package tarballs to slim the image.
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes

# App code last — the cheap, frequently-changing layer.
COPY --chown=$MAMBA_USER:$MAMBA_USER app ./app

# /tmp is always writable and ephemeral, which is exactly right for the SQLite index cache
# (everything that matters lives in Supabase and LEE3D-Lib, off this box).
ENV LEE3D_DATA_DIR=/tmp/lee3d
EXPOSE 8000

# The base image ENTRYPOINT (/usr/local/bin/_entrypoint.sh) activates the conda env, then
# this CMD runs inside it. Bind to the platform's $PORT when set (Render/Cloud Run), else 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
