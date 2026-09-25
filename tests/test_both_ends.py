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


def _car(**kw):
    """The real traced car, **from LEE3D-Lib**, which is the copy bothends.mjs reads too.

    Not this repo's or the frontend's nearest fixture: there are two copies of
    `fixture-hollow.json`, one in LEE3D-Frontend/test and one in LEE3D-Lib/schema, and as of
    2026-09-25 they have DRIFTED (c058374f against 68f75b4a). Each end loading whichever is
    nearest would compare two different cars, which is precisely the fault that made an earlier
    run of this comparison report a 42% divergence."""
    import json
    for base in ("LEE3D-Lib", "LEE3D-Lib-main"):
        f = os.path.join(os.path.dirname(ROOT), base, "schema", "fixture-hollow.json")
        if os.path.exists(f):
            p = json.load(open(f))
            p.update(kw)
            return p
    pytest.skip("LEE3D-Lib is not checked out beside this repo")


POCKET = lambda d: [{"name": "roof panel", "view": "top", "depth": d,
                     "poly": [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]}]

# `body` groups cases for CALIBRATION, and it has to: a dual contour's edge rounding is a
# property of the SHAPE. A box loses ~3.1% to twelve sharp edges; a traced car ~0.5%, because a
# car is mostly curve. One global deficit would under-correct the block or over-correct the car
# and every number below would be measuring that instead of the thing it claims to.
CASES = {
    "block solid":             ("block", _block, dict(hullHollow=False)),
    "block hollow w5":         ("block", _block, dict(hullHollow=True, wallThickness=5)),
    "block hollow w5 floor15": ("block", _block, dict(hullHollow=True, wallThickness=5, wallTop=5, wallSide=5, wallBottom=15)),
    "block hollow w5 roof15":  ("block", _block, dict(hullHollow=True, wallThickness=5, wallTop=15, wallSide=5, wallBottom=5)),
    "block hollow w5 side12":  ("block", _block, dict(hullHollow=True, wallThickness=5, wallTop=5, wallSide=12, wallBottom=5)),
    "block hollow w5 open":    ("block", _block, dict(hullHollow=True, wallThickness=5, closedBottom=False, openUnderside=True)),
    "block hollow w14 open":   ("block", _block, dict(hullHollow=True, wallThickness=14, closedBottom=False, openUnderside=True)),
    "block solid pocket5":     ("block", _block, dict(hullHollow=False, features=POCKET(-5))),
    "block hollow w5 pocket2": ("block", _block, dict(hullHollow=True, wallThickness=5, features=POCKET(-2))),
    "block hollow w5 pocket5": ("block", _block, dict(hullHollow=True, wallThickness=5, features=POCKET(-5))),
    "car solid":               ("car", _car, dict(hullHollow=False, features=None)),
    "car hollow w4.2":         ("car", _car, dict(hullHollow=True)),
    "car hollow w2.1":         ("car", _car, dict(hullHollow=True, wallThickness=2.1, wallTop=2.1, wallSide=2.1, wallBottom=2.1)),
    "car hollow w2.1 nofeat":  ("car", _car, dict(hullHollow=True, wallThickness=2.1, wallTop=2.1, wallSide=2.1, wallBottom=2.1, features=None)),
}

# Each body needs a SOLID case, or its carved cases have nothing to be calibrated against.
CALIBRATION = {"block": "block solid", "car": "car solid"}

# Measured, not guessed. With each body's solid deficit carried, the BLOCK cases land at
# +5.6 / -6.1 / -4.3 / +4.0 / +0.5 — inner-wall faceting, real and not a shape disagreement.
# 8 admits all of those with room and still fails the cases that matter.
TOLERANCE_PCT = 8.0

# The OUTER SKIN, on the other hand, is not faceted: it is the same isosurface whether the body
# is hollow or not, and this project's standing invariant is that hollowing must not move it.
# So the bounding box is compared on every case at a much tighter bound, and it is what keeps
# the car cases honest while their hollow VOLUME is exempted below.
BBOX_TOLERANCE_MM = 1.5

KNOWN_DISAGREEMENTS = {
    "block hollow w14 open":
        "the underside taper: the studio thins its side walls toward an open rim (2.64mm "
        "against a 14mm ask) and this end keeps the full wall. -14.7%, FLAT across resolution. "
        "Whether an opening should fair into the body is a decision, not a defect.",
    "block hollow w5 pocket5":
        "a pocket as deep as its wall: the studio pushes the cavity down and keeps the wall "
        "beneath, this end cuts into the cavity and leaves a hole. +10.9%. Measured on a ray "
        "up the pocket centre: the kernel's roof runs 35.0-40.0 without the pocket and is GONE "
        "with it.",
    # THE CAR'S HOLLOW VOLUME IS DOMINATED BY FACETING, AND THAT IS MEASURED RATHER THAN
    # ASSUMED. A thin wall on a big traced body has an enormous inner surface, the studio meshes
    # it in facets where the kernel offsets smoothly, and area times wall is material. The
    # discriminator this project established twice is CONVERGENCE — faceting shrinks as the grid
    # tightens, a shape disagreement does not:
    #
    #     car hollow w2.1 nofeat   res 50 +37.0%   res 72 +22.4%   res 108 +14.7%
    #     car hollow w2.1          res 50 +50.4%   res 72 +34.4%   res 108 +27.0%
    #
    # The first converges. The second converges too, toward a residual of about 12% that is FLAT
    # (13.4 / 12.0 / 12.3) — and that flat part is the pocket divergence above, arriving at the
    # same magnitude on a real car as it does on the block. Two independent measurements of one
    # bug is the strongest evidence in this file.
    #
    # **This is the gate's weakest point and it is written down rather than papered over:** with
    # these exempted, a genuine new divergence in the car's cavity would not show up in its
    # volume. The feature-delta check below is what covers that, and the bbox check covers the
    # outer skin. If the car's hollow volume is ever wanted as a gate, it needs a build at fine
    # resolution and a tolerance derived from a convergence sweep, not a bigger number.
    "car hollow w4.2":
        "faceting of the meshed inner wall on a thin-walled traced body. +19.2% at res 72, and "
        "it CONVERGES with the grid, which is what says faceting rather than shape.",
    "car hollow w2.1":
        "faceting plus the pocket divergence. +34.4% at res 72; the faceting part converges "
        "(37.0 -> 22.4 -> 14.7) and the remainder is flat at ~12%, which is the pocket case.",
    "car hollow w2.1 nofeat":
        "faceting alone, no features. +22.4% at res 72, converging 37.0 -> 22.4 -> 14.7.",
}

# PAIRS THAT DIFFER ONLY BY FEATURES. Comparing (without - with) on each end cancels most of the
# faceting, because both builds carry a similar inner surface at the same grid — so this is the
# check that can see a carving divergence on a body whose absolute hollow volume cannot be
# compared at all. Measured on the real car: the studio removes 4.94-6.94 cm3 for its 153
# pockets and the kernel removes 13.54, a factor of two to three, and that IS the hole.
FEATURE_PAIRS = {
    # THE CONTROL, and the only pocket pair the two ends agree on: carving a SOLID. Both simply
    # remove the prism — 4.60 cm3 studio against the kernel's 4.80. Without it the check below
    # would report every row and prove nothing.
    "solid pocket 5mm":                 ("block solid", "block solid pocket5"),
    "block pocket 2mm into a 5mm wall": ("block hollow w5", "block hollow w5 pocket2"),
    "block pocket 5mm into a 5mm wall": ("block hollow w5", "block hollow w5 pocket5"),
    "car 153 pockets at a 2.1mm wall":  ("car hollow w2.1 nofeat", "car hollow w2.1"),
}
KNOWN_FEATURE_GAPS = {
    # CORRECTING THE EARLIER FRAMING. This was written up as "a pocket DEEPER than its wall
    # leaves a hole", which is true and is not the whole of it. Measured here: a 2mm pocket into
    # a 5mm wall — which cannot break through anything — already diverges. The studio ADDS
    # 0.21 cm3 where the kernel removes 1.92.
    #
    # So the divergence is not about breaking through. **The two ends treat every pocket on a
    # hollow body differently**: the studio's field carve pushes the cavity down so the wall
    # beneath keeps its thickness, and the pocket's own lining is extra material, which is
    # deliberate and is Curtis's safety issue. This end does neither. Breaking through is simply
    # where that difference stops being material and becomes topological — a hole.
    "block pocket 2mm into a 5mm wall":
        "a pocket too shallow to break through, and the ends still disagree: the studio adds "
        "0.21 cm3 (cavity pushed down, pocket lining) where the kernel removes 1.92. The "
        "difference is the carve model itself, not the depth.",
    "block pocket 5mm into a 5mm wall":
        "the pocket is as deep as the wall, so it opens into the cavity here and not in the "
        "preview. The kernel removes 4.80 cm3 and the studio ADDS 0.25 — it pushes the cavity "
        "down and the pocket's own lining is the extra material.",
    "car 153 pockets at a 2.1mm wall":
        "the same thing 153 times on a real car: the kernel removes 13.54 cm3 and the studio "
        "4.94-6.94. Every one of his pockets is 2.5mm into a 2.1mm wall.",
}
FEATURE_TOLERANCE_PCT = 25.0   # a carve is a small difference of two big numbers; be generous

def test_both_ends_agree_about_the_part():
    # A plain importorskip, not a decorator computing HAS_CQ inside a walrus. The first draft
    # of this line did that and it was the same cleverness this file records replacing with two
    # plain stubs — a guard nobody can read is a guard nobody can check.
    pytest.importorskip("cadquery", reason="needs OpenCascade")
    from app import hull
    studio = _studio_dump()

    # 1. EACH BODY IS CALIBRATED ON ITS OWN SOLID. Nothing carved is worth comparing until
    #    the two ends agree about the body it was carved from — and the correction is per
    #    shape, not a constant, because edge rounding depends on how many sharp edges there are.
    deficit = {}
    for body, solid_case in CALIBRATION.items():
        s_solid = studio[solid_case]
        if "skipped" in s_solid:
            continue
        _, mk, kw = CASES[solid_case]
        k_solid = hull.build_solid(mk(**kw)).val().Volume() / 1000.0
        d = k_solid - s_solid["cm3"]
        deficit[body] = d
        assert abs(d) < k_solid * 0.10, (
            f"the two ends disagree about the SOLID {body.upper()} by {100*d/k_solid:.1f}% "
            f"(studio {s_solid['cm3']:.2f}, kernel {k_solid:.2f}). A dual contour rounding a "
            f"box's twelve sharp edges costs about 3% and a traced car about 0.5%; ten per cent "
            f"is a different body, and every comparison below would be measuring that instead "
            f"of what it claims to.")

    failures, noted, stale, skipped = [], [], [], []
    for name, (body, mk, kw) in CASES.items():
        if name in CALIBRATION.values():
            continue
        s = studio[name]
        if "skipped" in s:
            skipped.append(f"{name}: {s['skipped']}")
            continue
        assert "error" not in s, f"{name}: the studio could not build it — {s['error']}"
        assert body in deficit, f"{name} is on body {body!r}, which has no calibrated solid"
        k = hull.build_solid(mk(**kw)).val().Volume() / 1000.0
        gap = 100.0 * ((s["cm3"] + deficit[body]) - k) / k
        line = (f"{name}: studio {s['cm3']:.2f} (+{deficit[body]:.2f} {body} deficit) "
                f"vs kernel {k:.2f} -> {gap:+.1f}%")
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

    if skipped:
        print("\nnot compared, and the reason is environmental rather than geometric:\n  "
              + "\n  ".join(skipped))
    if noted:
        print("\nKNOWN, and each one a decision waiting rather than a defect:\n  "
              + "\n  ".join(noted))

    # 2. THE OUTER SKIN, which faceting does not touch. Hollowing must not move the outside —
    #    that invariant is why an auto-raise was removed from the studio and why a wLoc fix was
    #    rejected. It is also what keeps the car cases watched while their volume is exempt.
    for name, (body, mk, kw) in CASES.items():
        sc = studio[name]
        if "skipped" in sc or "error" in sc:
            continue
        bb = hull.build_solid(mk(**kw)).val().BoundingBox()
        kbox = [bb.xlen, bb.ylen, bb.zlen]
        for axis, a, b in zip("xyz", sc["bbox"], kbox):
            if abs(a - b) > BBOX_TOLERANCE_MM:
                failures.append(
                    f"{name}: the {axis} EXTENT differs by {abs(a-b):.2f}mm "
                    f"(studio {a:.2f}, kernel {b:.2f}). The outer skin is not faceted and does "
                    f"not depend on the wall, so this is the two ends disagreeing about the "
                    f"body itself, not about what was carved out of it.")

    # 3. WHAT A CARVE REMOVES, which cancels most of the faceting and is the only comparison
    #    that can see a carving divergence on a body whose absolute hollow volume cannot be
    #    compared at all.
    for label, (plain, carved) in FEATURE_PAIRS.items():
        if any("skipped" in studio[n] or "error" in studio[n] for n in (plain, carved)):
            continue
        s_del = studio[plain]["cm3"] - studio[carved]["cm3"]
        k_del = (hull.build_solid(CASES[plain][1](**CASES[plain][2])).val().Volume()
                 - hull.build_solid(CASES[carved][1](**CASES[carved][2])).val().Volume()) / 1000.0
        base = max(abs(k_del), 0.05)
        gap = 100.0 * (s_del - k_del) / base
        line = (f"{label}: the studio removes {s_del:+.2f} cm3 and the kernel {k_del:+.2f} "
                f"-> {gap:+.0f}%")
        if abs(gap) <= FEATURE_TOLERANCE_PCT:
            if label in KNOWN_FEATURE_GAPS:
                stale.append(line)
        elif label in KNOWN_FEATURE_GAPS:
            noted.append(f"{line}\n    known: {KNOWN_FEATURE_GAPS[label]}")
        else:
            failures.append(line + "  <- the two ends disagree about what a carve REMOVES, and "
                                   "that is not faceting: it is a difference of two builds at "
                                   "the same grid, where the mesh error largely cancels.")

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
