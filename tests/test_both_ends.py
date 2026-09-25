"""THE TWO ENDS MUST NOT DISAGREE ABOUT THE PART — checked by building it, on both.

Every other contract in this repo checks a CLAIM. `check_schema_coverage.py` greps two
codebases for a key name and says so itself: "it is a floor and not a ceiling".
`test_schema_contract.py` is stronger, but it mutates a key and watches `plan()` — one end.
Nothing has ever built the same profile with the studio's mesher AND the exact kernel and asked
whether they agree about the object.

Run by hand for the first time on 2026-09-21, that comparison found two live divergences in an
afternoon, both invisible to every existing test on either side:

    the underside taper      the studio thins its side walls to 2.64mm against a 14mm ask at
                             the rim of an open underside; this end keeps the full 14mm.
                             14.2% of the material, and FLAT across resolution, which is what
                             separates a shape disagreement from mesh faceting.
    a pocket through a wall  a pocket deeper than its wall cuts into the cavity here and not in
                             the preview. On the real traced car at 2.5mm pockets in a 2.1mm
                             wall, a roof of 86.9-88.9 becomes NOTHING at one station.

**COMPARE THE SOLIDS BEFORE ANYTHING CARVED OUT OF THEM.** The two ends legitimately differ on
a box: a dual contour rounds off its twelve sharp edges and loses ~3.1%, where the kernel has
exact planes. An earlier run of this comparison reported a 42% non-convergent divergence that
was simply a fixture built 120mm wide against the backend's 60 — caught only by checking the
solids first. So the solid case is the CALIBRATION and every hollow figure is compared with
that deficit carried, which is what makes the remaining numbers mean anything.
"""
import json
import os
import shutil
import subprocess
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _studio_dump():
    """Ask the STUDIO what it builds. Skips rather than guesses when it cannot be run."""
    if shutil.which("node") is None:
        pytest.skip("node is not installed — the studio half cannot be built")
    for cand in (os.path.join(os.path.dirname(ROOT), "LEE3D-Frontend", "test", "bothends.mjs"),
                 os.path.join(os.path.dirname(ROOT), "LEE3D-Frontend-main", "test", "bothends.mjs")):
        if os.path.exists(cand):
            script = cand
            break
    else:
        pytest.skip("LEE3D-Frontend is not checked out beside this repo")
    r = subprocess.run(["node", script], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"the studio dump failed:\n{r.stderr[-2000:]}"
    data = json.loads(r.stdout)
    assert not data["missing"], (
        f"the studio harness could not extract {data['missing']} out of index.html. It shares "
        f"core.test.mjs's extractor, so this means the suite cannot either — fix that first, "
        f"because everything below would otherwise compare against a phantom.")
    return data["cases"]


def _block(**kw):
    """`_block_with([])`, as the KERNEL builds it — the same body bothends.mjs describes."""
    from tests.test_hull import _block_with
    p = _block_with([])
    p.update(kw)
    return p


CASES = {
    "block solid":             dict(hullHollow=False),
    "block hollow w5":         dict(hullHollow=True, wallThickness=5),
    "block hollow w5 floor15": dict(hullHollow=True, wallThickness=5, wallTop=5, wallSide=5, wallBottom=15),
    "block hollow w5 roof15":  dict(hullHollow=True, wallThickness=5, wallTop=15, wallSide=5, wallBottom=5),
    "block hollow w5 side12":  dict(hullHollow=True, wallThickness=5, wallTop=5, wallSide=12, wallBottom=5),
    "block hollow w5 open":    dict(hullHollow=True, wallThickness=5, closedBottom=False, openUnderside=True),
    "block hollow w14 open":   dict(hullHollow=True, wallThickness=14, closedBottom=False, openUnderside=True),
}

# Measured 2026-09-21, not guessed. With the solid deficit carried, the block cases land at
# +5.6 / -6.1 / -4.3 / +4.0 / +0.5 percent — mesh faceting on an inner wall, which is real and
# is not a shape disagreement. 8% admits all of those with room and still fails the one case
# that matters at -14.2%. **If a case here goes red, the question is which end is right, not
# what the tolerance should be.**
TOLERANCE_PCT = 8.0

# KNOWN AND DELIBERATE, so the gate is green on arrival rather than teaching people to ignore
# it. This file's own rule: a gate that arrives red is a gate nobody reads. Each entry is a
# DECISION waiting on Collin, written up in STATUS.md, and removing one when it is settled is
# how this list is meant to shrink.
KNOWN_DISAGREEMENTS = {
    "block hollow w14 open":
        "the underside taper: the studio thins its side walls toward an open rim (2.64mm "
        "against a 14mm ask) and this end keeps the full wall. -14.2%, flat across resolution. "
        "Whether an opening should fair into the body is a decision, not a defect.",
}


def test_both_ends_agree_about_the_part():
    # A plain importorskip, not a decorator computing HAS_CQ inside a walrus. The first draft
    # of this line did that and it was the same cleverness this file records replacing with two
    # plain stubs — a guard nobody can read is a guard nobody can check.
    pytest.importorskip("cadquery", reason="needs OpenCascade")
    from app import hull
    studio = _studio_dump()

    # 1. THE SOLID IS THE CALIBRATION. Nothing carved is worth comparing until the two ends
    #    agree about the body it was carved from.
    s_solid = studio["block solid"]["cm3"]
    k_solid = hull.build_solid(_block(**CASES["block solid"])).val().Volume() / 1000.0
    deficit = k_solid - s_solid
    assert abs(deficit) < k_solid * 0.10, (
        f"the two ends disagree about the SOLID BLOCK by {100*deficit/k_solid:.1f}% "
        f"(studio {s_solid:.2f}, kernel {k_solid:.2f}). A dual contour rounding twelve sharp "
        f"edges costs about 3%; ten is a different body, and every comparison below would be "
        f"measuring that instead of what it claims to.")

    failures, noted, stale = [], [], []
    for name, kw in CASES.items():
        if name == "block solid":
            continue
        s = studio[name]
        assert "error" not in s, f"{name}: the studio could not build it — {s['error']}"
        k = hull.build_solid(_block(**kw)).val().Volume() / 1000.0
        gap = 100.0 * ((s["cm3"] + deficit) - k) / k
        line = f"{name}: studio {s['cm3']:.2f} (+{deficit:.2f} deficit) vs kernel {k:.2f} -> {gap:+.1f}%"
        if abs(gap) <= TOLERANCE_PCT:
            # COLLECTED, NOT RAISED HERE. A stale exemption used to assert inside the loop, and
            # the first one short-circuited the run before the accumulated real failures were
            # reported — so a change that fixed one case and broke three showed only the fixed
            # one. Measured: a mutant that shrank the cavity 20% broke `block hollow w5` by 35%
            # and the output named only `block hollow w14 open`. Gather everything, report once.
            if name in KNOWN_DISAGREEMENTS:
                stale.append(line)
        elif name in KNOWN_DISAGREEMENTS:
            noted.append(f"{line}\n    known: {KNOWN_DISAGREEMENTS[name]}")
        else:
            failures.append(line)

    if noted:
        print("\nKNOWN, and each one a decision waiting rather than a defect:\n  "
              + "\n  ".join(noted))
    # ONE REPORT, NOT TWO ASSERTIONS. Two in a row means the first hides the second: the run
    # that proved this caught a mutant which broke `block hollow w5` by 35% AND made the known
    # w14 case agree, and printed only the second. Whoever reads a red gate should see every
    # problem it found, not the first one in declaration order.
    problems = []
    if failures:
        problems.append(
            "THE TWO ENDS BUILD DIFFERENT PARTS:\n  " + "\n  ".join(failures)
            + "\n  Ask which end is RIGHT before touching the tolerance. Every number in this "
              "file was measured, and the last two times a case like this appeared it was a "
              "real bug.")
    if stale:
        problems.append(
            "STALE EXEMPTIONS — on the KNOWN_DISAGREEMENTS list and now AGREEING:\n  "
            + "\n  ".join(stale)
            + "\n  Good news, and a stale exemption: delete the entry, or the gate stops "
              "watching a case it is supposed to watch.")
    assert not problems, "\n\n".join(problems)
