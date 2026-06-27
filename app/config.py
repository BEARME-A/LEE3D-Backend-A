"""Runtime configuration, read from environment variables (12-factor style)."""
import os
from pathlib import Path

# --- storage ---
DATA_DIR = Path(os.getenv("LEE3D_DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "lee3d.db"
OUTPUT_DIR = DATA_DIR / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- model library repo (LEE3D-Lib) ---
GITHUB_OWNER = os.getenv("LEE3D_GITHUB_OWNER", "BEARME-A")
GITHUB_LIB_REPO = os.getenv("LEE3D_LIB_REPO", "LEE3D-Lib")
GITHUB_BRANCH = os.getenv("LEE3D_LIB_BRANCH", "main")
# A fine-grained PAT with Contents:read+write on LEE3D-Lib. Never commit this.
GITHUB_TOKEN = os.getenv("LEE3D_GITHUB_TOKEN", "")

# --- CORS: where the frontend is served from ---
# e.g. "https://bearme-a.github.io,http://localhost:3000"
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "LEE3D_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://bearme-a.github.io",
).split(",") if o.strip()]

APP_VERSION = "0.1.0"
