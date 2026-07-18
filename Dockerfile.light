# LIGHT image — deploys in ~2 min on any free tier and gets the backend ONLINE:
#   /health, /import/image, /import/pdf, /projects, /library/commit all work.
# STEP generation (/generate?fmt=step) returns a clear 503 because CadQuery/OpenCascade
# aren't pip-reliable — use ./Dockerfile.full (conda) when you want CAD export.
FROM python:3.11-slim

WORKDIR /app
# runtime libs opencv-python-headless / pymupdf may need on slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
ENV LEE3D_DATA_DIR=/data
EXPOSE 8000
# bind to the platform's $PORT (Render/Railway/Fly set it); default 8000 locally
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
