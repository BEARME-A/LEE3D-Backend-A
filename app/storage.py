"""
Storage = local index (SQLite) + the model library (the LEE3D-Lib GitHub repo).

SQLite keeps a queryable record of every project, every imported drawing, and
every generated body. The actual binary artefacts (drawings, STLs, STEPs,
profile JSON) are committed into LEE3D-Lib via the GitHub Contents API, so the
library *is* a normal, browsable, version-controlled GitHub repo — exactly the
folder layout the brief asked for:

    drawings/  photos/  json/  generated/  exports/  versions/
"""
from __future__ import annotations
import base64
import sqlite3
import time
from typing import List, Dict, Optional

from . import config


# --------------------------------------------------------------------------
# SQLite index
# --------------------------------------------------------------------------
def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS files(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                kind TEXT NOT NULL,          -- drawing|photo|json|generated|export
                path TEXT NOT NULL,          -- repo-relative path in LEE3D-Lib
                sha TEXT,                    -- git blob sha returned by GitHub
                created_at REAL NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            CREATE TABLE IF NOT EXISTS versions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                profile_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            """
        )


def create_project(name: str, notes: str = "") -> Dict:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO projects(name, notes, created_at) VALUES(?,?,?)",
            (name, notes, time.time()),
        )
        pid = cur.lastrowid
    # `with` has committed here, so a fresh read sees the row
    return get_project(pid)


def list_projects() -> List[Dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_project(pid: int) -> Optional[Dict]:
    with _conn() as c:
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        if not r:
            return None
        p = dict(r)
        p["files"] = [dict(x) for x in c.execute(
            "SELECT * FROM files WHERE project_id=? ORDER BY created_at DESC", (pid,)).fetchall()]
        p["versions"] = [dict(x) for x in c.execute(
            "SELECT id, created_at FROM versions WHERE project_id=? ORDER BY created_at DESC", (pid,)).fetchall()]
        return p


def record_file(project_id: Optional[int], kind: str, path: str, sha: Optional[str]) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO files(project_id, kind, path, sha, created_at) VALUES(?,?,?,?,?)",
            (project_id, kind, path, sha, time.time()),
        )


def record_version(project_id: Optional[int], profile_json: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO versions(project_id, profile_json, created_at) VALUES(?,?,?)",
            (project_id, profile_json, time.time()),
        )
        return cur.lastrowid


# --------------------------------------------------------------------------
# GitHub library (LEE3D-Lib) via the Contents API
# --------------------------------------------------------------------------
class LibraryError(RuntimeError):
    pass


def _httpx():
    try:
        import httpx
        return httpx
    except Exception as e:  # pragma: no cover
        raise LibraryError("httpx not installed. `pip install httpx`. " + repr(e))


def library_configured() -> bool:
    return bool(config.GITHUB_TOKEN)


def commit_file(path: str, content_bytes: bytes, message: str) -> Dict:
    """
    Create or update a file in LEE3D-Lib. Returns the GitHub commit info,
    including the html_url you can open in a browser.
    """
    if not library_configured():
        raise LibraryError(
            "No GitHub token set. Export LEE3D_GITHUB_TOKEN (a fine-grained PAT "
            "with Contents read+write on LEE3D-Lib) to enable library commits."
        )
    httpx = _httpx()
    owner, repo, branch = config.GITHUB_OWNER, config.GITHUB_LIB_REPO, config.GITHUB_BRANCH
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    with httpx.Client(timeout=30) as client:
        # If the file already exists we must pass its sha to update it.
        sha = None
        r = client.get(api, headers=headers, params={"ref": branch})
        if r.status_code == 200:
            sha = r.json().get("sha")

        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        r = client.put(api, headers=headers, json=payload)
        if r.status_code not in (200, 201):
            raise LibraryError(f"GitHub commit failed [{r.status_code}]: {r.text[:300]}")
        data = r.json()

    blob_sha = data.get("content", {}).get("sha")
    return {
        "committed": True,
        "path": path,
        "sha": blob_sha,
        "commit_url": data.get("commit", {}).get("html_url"),
        "download_url": data.get("content", {}).get("download_url"),
    }


# Map a file kind to its folder in LEE3D-Lib.
LIB_FOLDERS = {
    "drawing": "drawings",
    "photo": "photos",
    "json": "json",
    "generated": "generated",
    "export": "exports",
    "version": "versions",
}


def library_path(kind: str, project: str, filename: str) -> str:
    folder = LIB_FOLDERS.get(kind, "generated")
    safe_project = project.strip().replace(" ", "-") or "misc"
    return f"{folder}/{safe_project}/{filename}"
