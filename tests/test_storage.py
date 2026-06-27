"""SQLite index tests — no network, run anywhere."""
import os, tempfile, importlib

def test_project_and_version_roundtrip():
    d = tempfile.mkdtemp()
    os.environ["LEE3D_DATA_DIR"] = d
    # reimport config + storage so they pick up the temp data dir
    import app.config as config; importlib.reload(config)
    import app.storage as storage; importlib.reload(storage)

    storage.init_db()
    p = storage.create_project("charger-body", "1968 frame")
    assert p["id"] >= 1 and p["name"] == "charger-body"

    storage.record_version(p["id"], '{"length":180}')
    storage.record_file(p["id"], "generated", "generated/charger-body/charger.stl", "abc123")

    got = storage.get_project(p["id"])
    assert len(got["versions"]) == 1
    assert got["files"][0]["path"].endswith("charger.stl")
    assert storage.library_path("drawing", "1968 charger", "side.png") == "drawings/1968-charger/side.png"
    print("storage roundtrip OK")

if __name__ == "__main__":
    test_project_and_version_roundtrip()
