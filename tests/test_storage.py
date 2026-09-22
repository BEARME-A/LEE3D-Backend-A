"""SQLite index tests — no network, run anywhere."""
import os, tempfile, importlib


def test_project_and_version_roundtrip():
    """THIS TEST RELOADS TWO MODULES AND HAS TO PUT THEM BACK.

    `config.DATA_DIR` is computed at IMPORT time from the environment, so pointing the index at
    a temp dir means reloading `app.config` and then `app.storage`. A reload rebinds the module
    GLOBALLY — for every test that runs afterwards, at a path this one is about to abandon — and
    it leaves `LEE3D_DATA_DIR` set in the process environment on the way out.

    It was harmless only because pytest collects alphabetically and this file sorts last. That
    is a property of the FILE NAMES, not of the code, and nobody should have to know it: adding
    `tests/test_vision.py` puts a test after this one, and `-p randomly` removes the guarantee
    outright. Worse, `app.main` already holds a reference to the pre-reload `storage` module, so
    after the reload two different module objects are live at once — the two-copies-of-one-thing
    shape this project keeps getting caught by, in a test rather than in the product.

    So: save, and restore in a finally.
    """
    prev = os.environ.get("LEE3D_DATA_DIR")
    d = tempfile.mkdtemp()
    os.environ["LEE3D_DATA_DIR"] = d
    import app.config as config; importlib.reload(config)
    import app.storage as storage; importlib.reload(storage)
    try:
        assert str(config.DATA_DIR) == os.path.realpath(d), (
            "the reload has to have taken, or this test is measuring the real data dir")

        storage.init_db()
        p = storage.create_project("charger-body", "1968 frame")
        assert p["id"] >= 1 and p["name"] == "charger-body"

        storage.record_version(p["id"], '{"length":180}')
        storage.record_file(p["id"], "generated", "generated/charger-body/charger.stl", "abc123")

        got = storage.get_project(p["id"])
        assert len(got["versions"]) == 1
        assert got["files"][0]["path"].endswith("charger.stl")
        assert storage.library_path("drawing", "1968 charger", "side.png") == \
            "drawings/1968-charger/side.png"
        print("storage roundtrip OK")
    finally:
        if prev is None:
            os.environ.pop("LEE3D_DATA_DIR", None)
        else:
            os.environ["LEE3D_DATA_DIR"] = prev
        importlib.reload(config)
        importlib.reload(storage)


def test_the_storage_test_leaves_no_trace():
    """The guard for the guard. Runs the roundtrip, then asks whether the process was left the
    way it was found — because a cleanup that silently stops working is worth exactly as much as
    no cleanup, and this one is invisible from inside the test it protects."""
    import app.config as config
    before_env = os.environ.get("LEE3D_DATA_DIR")
    before_dir = str(config.DATA_DIR)

    test_project_and_version_roundtrip()

    assert os.environ.get("LEE3D_DATA_DIR") == before_env, \
        "LEE3D_DATA_DIR was left pointing somewhere else for every test after this one"
    assert str(config.DATA_DIR) == before_dir, \
        "app.config was left reloaded against a temp dir that no longer matters"


if __name__ == "__main__":
    test_project_and_version_roundtrip()
