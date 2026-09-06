"""Does the exact build actually READ what the schema says it reads?

`profile.schema.json` marks each key with `x-read-by`. The coverage checker in LEE3D-Lib
verifies that claim by grepping the source, which is a floor: a key named only in a comment
counts as read. This is the stronger version for the one end that can be executed here —
change the key, and see whether the answer changes.

It exists because four bugs in one month were the same shape: one end knowing about a key the
other did not, with nothing raising an error. Pockets dropped from every STEP export. Extra
views ignored. Per-face wall honoured by one builder and not the other.

THREE HONEST REASONS a key can matter without changing plan() on a given profile, all of which
this test has to allow or it becomes noise:

  CONDITIONAL   `sepBottom` only decides anything when `hullHollow` is absent — the studio has
                written hullHollow for a long time, so on a modern profile sepBottom is inert.
                Tested on a profile with hullHollow removed instead.
  REPORTED      `sidePolyR` cannot be used by the exact build, and it says so: `plan()` sets
                `ignored_second_side`. A key that is read in order to be honest about not being
                usable is read.
  ELSEWHERE     `name` never reaches plan(); it names the exported file. Checked by source.

Each of those was a false positive on the first run of this test. Writing them down is the
point — the next person to see one should not have to rediscover that it is fine.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app import hull

HERE = Path(__file__).resolve().parent
# The schema lives in LEE3D-Lib. If it is not checked out beside this repo the test skips
# rather than guessing, and says so.
SCHEMA_CANDIDATES = [
    HERE.parent.parent / "LEE3D-Lib" / "schema" / "profile.schema.json",
    HERE.parent.parent / "lib" / "schema" / "profile.schema.json",
    HERE.parent / "schema" / "profile.schema.json",
]
FIXTURES = [
    HERE / "fixtures" / "profile.json",
    HERE.parent.parent / "LEE3D-Lib" / "schema" / "fixture-charger.profile.json",
    HERE.parent.parent / "lib" / "schema" / "fixture-charger.profile.json",
]


def _load(paths):
    for p in paths:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf8")), p
            except Exception:
                continue
    return None, None


# a plausible change for each key: enough to move the answer if it is really being read
MUTATE = {
    "length": lambda v: (v or 200) * 1.5,
    "topProfile": lambda v: [[a, b * 1.4] for a, b in (v or [[0, 50]])],
    "widthProfile": lambda v: [[a, b * 1.4] for a, b in (v or [[0, 30]])],
    "wallThickness": lambda v: (v or 2) + 3,
    "wallTop": lambda v: (v or 2) + 5,
    "wallSide": lambda v: (v or 2) + 5,
    "wallBottom": lambda v: (v or 2) + 5,
    "hullHollow": lambda v: not bool(v),
    "features": lambda v: [],
    "sidePoly": lambda v: None,
    "topPoly": lambda v: None,
    "frontPoly": lambda v: None,
    "extraViews": lambda v: [{"dir": [0, 1, 1], "poly": [[0, 0], [10, 0], [10, 10]]}],
    # Numeric, and deliberately tolerant of junk: a saved profile can carry anything in these,
    # and `plan()` swallowing a string rather than throwing is the wanted behaviour. So the
    # default "CHANGED" mutation is not a test of whether they are read — it is a test of the
    # junk guard, which has its own test. Mutate them with real numbers.
    "modelScale": lambda v: (v or 1) + 199,
    "realLength": lambda v: (v or 1000) * 7,
}

# keys that legitimately do not move plan() on a modern profile — see the docstring
CONDITIONAL = {"sepBottom"}
REPORTED = {"sidePolyR"}
ELSEWHERE = {"name",
             # A TURNED OBJECT SKIPS plan() ENTIRELY. `build_solid` dispatches on shape=="lathe"
             # before plan() is reached, because every line below it assumes the body is the
             # intersection of three silhouettes — the one thing that cannot make a round object
             # round. So these two are read by the exact build and are invisible to plan(), which
             # is what this list is for. `shape` itself is NOT here: it is read by the studio and
             # its x-read-by says so.
             # "shape" joins them: the exact build reads it (that is the dispatch itself) but
             # plan() never does, and the default mutation to "CHANGED" is not "lathe" so the
             # dispatch correctly does not fire. Its x-read-by names both ends truthfully.
             "shape", "revProfileV", "revHeight"}


def test_every_key_the_schema_says_we_read_actually_changes_the_answer():
    schema, spath = _load(SCHEMA_CANDIDATES)
    if schema is None:
        pytest.skip("profile.schema.json not found — check out LEE3D-Lib beside this repo")
    base, bpath = _load(FIXTURES)
    if base is None:
        pytest.skip("no profile fixture found to mutate")

    props = schema.get("properties", {})
    claimed = sorted(k for k, v in props.items() if "exact" in v.get("x-read-by", []))
    assert claimed, "the schema claims the exact build reads nothing — that cannot be right"

    ref = json.dumps(hull.plan(base), sort_keys=True, default=str)
    dead = []
    for key in claimed:
        if key in CONDITIONAL or key in REPORTED or key in ELSEWHERE:
            continue
        p = copy.deepcopy(base)
        p[key] = MUTATE.get(key, lambda v: "CHANGED")(p.get(key))
        try:
            after = json.dumps(hull.plan(p), sort_keys=True, default=str)
        except Exception:
            continue          # raising IS reading it
        if after == ref:
            dead.append(key)
    assert not dead, (
        f"the schema says the exact build reads {dead}, and changing them changes nothing. "
        f"Either the backend has stopped reading them — which is the divergence bug, and is how "
        f"pockets went missing from every STEP export — or the schema's x-read-by is wrong. "
        f"(schema: {spath}, profile: {bpath})")


def test_a_per_face_wall_actually_reaches_the_build():
    """The gap the mutation test above CANNOT see, and it is worth knowing why.

    That test changes one key at a time on a real profile. The reference car has a uniform
    wall, so `wall_varies` is False whatever wallTop is set to — switching the whole per-face
    branch off changes nothing and the test passes. I found this by reinstating the real bug
    and watching it slip through.

    A key can therefore be read and still be unreachable, because a DIFFERENT key gates it.
    So this asserts the gate itself: three different face values must be recognised as varying,
    and must reach `plan()` as such."""
    base, _ = _load(FIXTURES)
    if base is None:
        pytest.skip("no profile fixture")
    uniform = {**base, "wallThickness": 4, "wallTop": 4, "wallSide": 4, "wallBottom": 4}
    perface = {**base, "wallThickness": 4, "wallTop": 4, "wallSide": 4, "wallBottom": 12}
    assert hull.plan(uniform)["wall_varies"] is False
    assert hull.plan(perface)["wall_varies"] is True, \
        "a thick floor with thin walls must be recognised — this is the load-bearing control"
    # and the spec that reaches the build must carry the three values, not one
    spec = hull.plan(perface)["wall_spec"]
    assert spec["bot"] == 12 and spec["top"] == 4, f"the faces did not survive: {spec}"
    # the cavity maths must then actually use them
    out = hull.offset_inward([(0, 0), (100, 0), (100, 60), (0, 60)], "XZ", spec)
    bottom = min(z for _, z in out)
    assert abs(bottom - 12) < 1e-6, \
        f"the floor should be pulled in by 12mm, not {bottom:.2f} — the thick value is not reaching the cavity"

    # WHAT THIS TEST STILL CANNOT SEE, stated because a gap you know about is worth more than
    # one you have quietly left. Disabling the per-face branch inside `build_solid` — the line
    # `if wall_varies(spec):` — leaves everything above PASSING: plan() still reports
    # wall_varies True with the right spec, and offset_inward still computes the right cavity.
    # The plan stays honest while the build stops using it, and plan() is the only thing that
    # runs without OpenCascade. Verified by reinstating exactly that.
    # Only the kernel-gated tests in test_hull.py can see the difference, and they skip
    # wherever CadQuery is absent. That is a real limit of testing a CAD build without a CAD
    # kernel, not something a cleverer assertion here would fix.


def test_sepBottom_still_decides_hollowness_when_hullHollow_is_absent():
    """CONDITIONAL, and worth its own test rather than an exemption on trust. Older profiles
    carried only sepBottom, where 'no separate bottom piece' implied a single hollow body. That
    fallback is what this checks; it is also the bug that once returned a solid litre of
    material against a 95cc shell in the preview beside it."""
    base, _ = _load(FIXTURES)
    if base is None:
        pytest.skip("no profile fixture")
    p = {k: v for k, v in base.items() if k != "hullHollow"}
    assert hull.plan({**p, "sepBottom": False})["hollow"] is True
    assert hull.plan({**p, "sepBottom": True})["hollow"] is False


def test_a_second_side_outline_is_reported_rather_than_silently_dropped():
    """REPORTED. The exact build cannot use a separate right flank, and the whole lesson of
    this month is that a limitation must be loud. `plan()` sets `ignored_second_side` — a key
    read in order to be honest about not being usable is read."""
    base, _ = _load(FIXTURES)
    if base is None:
        pytest.skip("no profile fixture")
    assert hull.plan(base).get("ignored_second_side") is False
    p = copy.deepcopy(base)
    p["sidePolyR"] = [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert hull.plan(p).get("ignored_second_side") is True, \
        "a right flank that cannot be used must be reported, not dropped in silence"


def test_the_model_name_reaches_the_export_even_though_plan_ignores_it():
    """ELSEWHERE. `name` never moves plan(); it names the file that comes out. Asserted against
    the source so the exemption above is not simply taken on faith."""
    src = (HERE.parent / "app" / "hull.py").read_text(encoding="utf8")
    src += (HERE.parent / "app" / "main.py").read_text(encoding="utf8")
    assert 'profile.get("name")' in src or "profile.name" in src, \
        "nothing reads the model name any more — then the schema should stop claiming it does"
