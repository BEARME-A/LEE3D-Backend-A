"""Runtime configuration, read from environment variables (12-factor style)."""
import os
from pathlib import Path

# --- storage ---
def _writable_dir(preferred: str) -> Path:
    """The data dir, or somewhere that actually works.

    This runs at import time, so a directory that can't be created takes the whole app
    down before it serves a single request — and the traceback says PermissionError on
    mkdir, which doesn't obviously mean "your host has a read-only root filesystem".
    Cloud Run is exactly that host, and render.yaml names it as the free alternative for
    the CAD image. Everything in here is a cache (a SQLite index and generated files);
    the models themselves live in Supabase and LEE3D-Lib. So losing the preferred
    location is worth a warning, never a crash.
    """
    import tempfile
    for candidate in (preferred, "/tmp/lee3d", tempfile.gettempdir() + "/lee3d"):
        try:
            p = Path(candidate).resolve()
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".writable"
            probe.touch()
            probe.unlink()
            if str(p) != str(Path(preferred).resolve()):
                print(f"[config] {preferred!r} isn't writable; caching in {p} instead. "
                      f"Nothing here is worth persisting — set LEE3D_DATA_DIR to silence this.")
            return p
        except Exception:
            continue
    raise RuntimeError("no writable data directory: tried "
                       f"{preferred}, /tmp/lee3d, {tempfile.gettempdir()}/lee3d")


DATA_DIR = _writable_dir(os.getenv("LEE3D_DATA_DIR", "./data"))
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
