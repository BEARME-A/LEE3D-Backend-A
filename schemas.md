# LEE3D — STATUS
_Last updated: **2026-08-30** (underside open 2.1-5mm; plank, carve tearing and the missing level-base cut all fixed)._
_Live: https://bearme-a.github.io/LEE3D-Frontend/ — deploy gated on the core suite._

A dated CHANGELOG is at the bottom of this file. Add to it every session — it is the only
record of why things are the way they are, and it has already saved re-deriving the same
findings twice.

======================================================================
# READ FIRST — REBUILT AFTER A WORKSPACE RESET. These md5s are authoritative.
======================================================================
My container was reset and several shipped files were lost from my side. They were **rebuilt
from the reasoning recorded in this document — they are NOT the original bytes.** The md5s
below supersede every earlier md5 in this file.

    FILE                  SHIP THIS   verified
    index.html            e02a3f99    277 passed, 0 failed
    test/core.test.mjs    28d0f7e5    (the 5 per-face tests are back in it)
    app/hull.py           802fb10c -> now 2e44686f (see 2026-08-29)
    tests/test_hull.py    49fa0846 -> STALE; was already 619ebd3d, now 1279dc33
    conftest.py           75d923b5    byte-identical to the original

**Functionally equivalent, not byte-equivalent.** Every behaviour was re-verified by
measurement rather than assumed:
  - per-face wall: a 16mm floor builds 16.00mm against 6mm walls; each of roof/side/floor
    changes the volume; a uniform wall is unchanged
  - thin-wall grid refinement reproduces the original table (2mm and 3mm fall back and warn,
    4mm refines and takes field hollow)
  - the offset maths in hull.py gives bottom z=16, top z=54, sides x=6 and 94, as before
  - both sign traps are back (surface normal not travel direction; signed area computed
    locally because poly_area is abs()-ed)

### A near miss worth recording
The uploaded zip predated the per-face wall feature as well as the three later fixes, and my
first rebuild pass **silently omitted it** — I rebuilt the three fixes I had been thinking
about and did not check what else the zip was missing. It was caught by grepping the shipped
file for `perFace` before moving on. **After any reset, diff the repo against the FULL list of
shipped work, not against the last thing you remember doing.**

======================================================================
# CONFTEST.PY — FIXED. Backend CI runs. (was the READ FIRST blocker)
======================================================================
_Collin moved it. Verified 2026-08-29 against fresh zips: `LEE3D-Backend-A/conftest.py` is at
the repo root at md5 75d923b5, and there is no copy left in `app/`. `pytest -q` from the root
collects and runs. Kept here as a one-line record so the next session does not go looking for
an emergency that is over._

The reason, worth keeping: pytest only auto-loads the conftest at its **rootdir**. In `app/`
it did nothing, so a bare `pytest -q` — what CI runs — died with
`ModuleNotFoundError: No module named 'app'`.

======================================================================
# FULL AUDIT — 2026-08-29, all three repos, every recorded md5
======================================================================
Every one of the ten contract files matches. `index.html` e02a3f99 and `app/hull.py` 4e4c26c5
match. **One md5 in this document was STALE, and the file was fine:**

    tests/test_hull.py    recorded 49fa0846    actually 619ebd3d    <- the NOTE was wrong

619ebd3d contains `test_a_real_traced_car_comes_back_hollow` and
`test_per_face_walls_work_on_a_real_traced_car` — the cont. 17/18 work. It moved together with
`hull.py` (802fb10c -> 4e4c26c5) and only the hull md5 got updated here. The file was newer,
not corrupted. **When two files change as a pair, update both md5s or neither** — a stale note
costs the next session a corruption hunt that finds nothing.

======================================================================
# THE CONTRACT FILES — one place, all ten, verified together 2026-08-23
======================================================================
Attached as a set because they only make sense together: the schema declares the profile, the
checker enforces the declaration, the tests enforce it by execution, and the workflows run all
of it. Paths are relative to each repo's root.

    LEE3D-Frontend/
      test/core.test.mjs                       28d0f7e5   277 passed, 0 failed

    LEE3D-Backend-A/
      conftest.py                              75d923b5   without it pytest cannot import `app`
      requirements.txt                         62d4dba6   conda-only note corrected
      app/schemas.py                           02364ebe   names the traced shape (35 -> 62 fields)
      tests/test_schema_contract.py            2bf2c4da   5 passed
      .github/workflows/ci.yml                 60dc37d2   jobs: test (fast gate) + cad (kernel)

    LEE3D-Lib/
      schema/profile.schema.json               83a60ca8   54 properties, every one x-read-by
      app/schemas.py                           02364ebe   IDENTICAL to the backend's, by design
      tools/check_schema_coverage.py           32e2bae1   clean against all three repos
      .github/workflows/schema.yml             5d286d36   job: agree (checks out all three)

Verified as a set, not one at a time:
    coverage checker across all three repos    clean
    backend contract tests                     5 passed
    frontend suite                             277 passed, 0 failed
    both workflows                             parse; jobs as listed above
    the two schemas.py                         byte-identical (02364ebe)

Two notes the checker prints deliberately, neither a failure:
  - `app/schemas.py names 62 fields; 13 schema keys are not among them` — the 13 are
    studio-only (revolve, reference images, size overrides) and contain no geometry.
  - `app/schemas.py is duplicated here and in the backend` — **the library's copy is imported
    by nothing.** Deleting it removes a drift risk at no cost; if it is kept, the checker fails
    the build the moment the two differ.

======================================================================
# HOW THIS PROJECT IS RUN — read before anything else
======================================================================
**Live site:** https://bearme-a.github.io/LEE3D-Frontend/
Served by GitHub Pages from `LEE3D-Frontend`, published by `.github/workflows/deploy.yml`
on every push to `main`. The backend runs separately on Render.

### The deploy gate
Both `ci.yml` and `deploy.yml` run `node test/core.test.mjs` before anything is published.
**A red suite means nothing ships** — the deploy job runs the tests as a step, so a failure
stops it before the Pages upload.

**The suite takes about 10 minutes and that is fine.** Collin's call, stated plainly: length
does not matter as long as it catches bugs. Do NOT trim it by lowering fidelity — this project
lost multiple sessions to false all-clears from verifying at the wrong resolution. GitHub's
default job limit is 6 hours, so there is no timeout pressure at all. If it ever needs to be
faster, split it into a fast subset for iteration and keep the full suite as the gate; never
weaken what the gate checks.

Pages must be set to **Source: "GitHub Actions"**, not "Deploy from a branch" — with the
latter, GitHub's own pages-build-deployment owns the site and this workflow queues forever.

### Connections are wired at build time
`deploy.yml` substitutes placeholders in index.html from repo secrets and variables:
    secrets:   SUPABASE_URL, SUPABASE_ANON_KEY     -> cloud saves
    variables: BACKEND_URL (Render), LIB_REPO      -> exact STEP export, shared library
Anything left unset simply stays switched off in the app. Supabase SQL is unchanged and is
not tracked in these handoffs.

### Working agreement for these sessions
1. **Read this file first, every chat.** It is the guide to the project, not a log.
2. **Ship STATUS.md every turn**, with what the focus was, what worked, and what failed.
   The failures matter as much as the fixes — several entries here exist only to stop a wrong
   idea being tried a third time.
3. **Do not re-ship a file that has not changed.** Only changed bytes go out, md5-verified
   against what is already in the repo.

======================================================================
# REPO STATE — checked 2026-08-16 against Collin's zips
======================================================================
Everything I have shipped is in the repos, byte for byte:

    LEE3D-Frontend/index.html            ee6362ba   MATCHES
    LEE3D-Frontend/test/core.test.mjs    eded7a0f   MATCHES
    LEE3D-Frontend/test/fixture-hollow.json         same content (one trailing newline
                                                    differs; semantically identical, fine)
    LEE3D-Backend-A/app/hull.py          56b0261d   MATCHES
    LEE3D-Backend-A/app/main.py          5a29638a   MATCHES
    LEE3D-Backend-A/tests/test_hull.py   e45d6e7a   MATCHES

**Nothing is out of date and nothing needs re-shipping.** The backend fix (pockets, raises,
batched booleans, extraViews reporting) is already in place — it still needs verifying on a
CadQuery image, which is listed in the STEP section and cannot be done from here.


======================================================================
## TWO MOBILE BUGS FROM A SCREENSHOT — both mine, both fixed
======================================================================
Reported from an iPhone: tapping **Auto-trace detail** on any face made the whole app look
like it had fallen apart, and **the side view always came up dark**.

### 1. The layout collapse was the thin-wall warning I added
I put the banner INSIDE `<header>`. A header is a flex ROW with `align-items:center` and, on
mobile, `height:auto`. The moment the warning appeared its text wrapped to several lines in a
phone's width, the header grew to that height, and every control in it floated in the middle of
a huge empty band — which is exactly what the screenshot shows.

It fired on Auto-trace detail because that is what adds features, triggers a rebuild, and finds
a thin patch to warn about. Nothing to do with tracing; the trace was just the trigger.

**Fix:** moved it out of the header into the page flow, full width, `flex:0 0 auto` so it
cannot take space from the stage, with `max-height` and its own scroll so a long message can
never grow the layout around it. **A banner belongs in the page flow, not in a toolbar.**

### 2. The dark side view is a canvas measured before it has been laid out
`fitTrace()` reads `host.clientWidth/clientHeight` and sets the canvas to that size. Those are
**0** while an element is `display:none` or before the browser has laid the panel out — and
several call sites do `switchTab("trace"); fitTrace();` in the same tick, so the measurement
happens before the tab is laid out. Setting a canvas to 0x0 is not a no-op: it throws the
drawing away, and nothing recomputes it until something else forces a resize.

`activeView` starts as **"side"**, which is why it was always that view.

**Fix:** if the host cannot say how big it is yet, keep the size the canvas already had, or ask
again on the next animation frame when the layout has settled. Never write a 0x0 canvas.

### What this says about the check list
Both were in code I shipped, and neither could have been caught by the test suite — it builds
geometry headlessly and has no layout at all. **This is what the FOR COLLIN TO CHECK list is
for**, and item 1 on it (the thin-wall banner) is precisely the thing that broke. A screenshot
found in seconds what I had no way to see.


======================================================================
## THE PLANK WAS NEVER FIXED AT THE WALL COLLIN ACTUALLY USES
======================================================================
_Found 2026-08-17 from screenshots of a real car at a **2 mm wall**. Collin drew arrows at a
flat shelf spanning the middle of the car, visible through the open wheel arches — the plank,
on a FEATURELESS body, after several sessions of it being "fixed"._

### Why it came back
Field hollow needs about one and a half cells across the wall or its two surfaces land in the
same cell and cancel. Below that the build **fell back to the vertex-push path** — and that is
the path that plants the plank: on a thin section it pushes the two surfaces at each other
until they weld into a flat plate with open air beneath.

    profile_7, 200mm long, res 72, cell 2.78mm
      wall 2.0mm  -> fieldHollow FALSE   fallback   <- Collin's setting
      wall 3.0mm  -> fieldHollow FALSE   fallback
      wall 4.2mm  -> fieldHollow TRUE    correct

Cross-section of the deck at x=30%:

    wall 2.0mm   z=52.2  |  .#.##..........###########......#.........#...## |   a bare strip
    wall 4.2mm   z=52.2  |  .######################################## ###### |   a closed box

**So every plank fix was verified at 4.2mm and none of them applied at 2mm.** The whole reason
field hollow was written stopped applying at exactly the wall thickness a toy car uses, and
nothing said so — the readout showed "2 mm wall" and a watertight solid either way.

### What changed
1. The grid is now refined to fit the wall before giving up, so 4mm reaches res 74 and builds
   correctly where it used to fall back.
2. Where even the cap cannot carry it, the build **says so**: a 2mm wall on a 200mm car would
   need res 146 and about 181,000 triangles, past the Fine cap of 120. The warning now reads
   "a 2 mm wall is thinner than this build can hollow properly... thin sections may come out as
   a flat shelf instead of a hollow box."

### The lesson, and it is the sharpest one of the campaign
**A fix that is gated is not a fix until you check the gate against real settings.** I verified
the plank fix on profile_7's saved 4.2mm wall for session after session while the gate silently
excluded the value being used in practice. The fallback was watertight, so no test caught it,
and the readout looked normal.


======================================================================
## THE "SMOOTH MODE IS FLIPPED" REPORT — the geometry is not flipped
======================================================================
_Collin reported that switching to Smooth produced a flipped body, "but the inside of the body
is still perfect"._

### Measured three ways, on the same profile, and they agree
    bounding box        projection 200.1 x 115.0 x 83.3   loft 200.0 x 115.0 x 84.7
    width by height     10% 110.9 / 35% 113.2 / 60% 115.0 / 90% 81.4
                        10% 114.1 / 35% 115.0 / 60% 112.0 / 90% 89.6
    height along length 49.1 / 60.2 / 88.8 / 87.3 / 67.3
                        49.0 / 59.5 / 88.7 / 87.1 / 66.5
The tall end is at the same end, the wide end is at the same end, and the sizes match. **The
geometry is not turned around in any axis.**

### What it almost certainly is
`frameModel()` — which resets the camera to a fixed 3/4 angle and frames the body — **ran only
once, at startup.** Switching shape style rebuilds from a completely different method but left
the camera wherever it had been orbited to. Someone who had turned the model over to look at
its underside and then switched styles saw the new build from below and read it as flipped.

**Fixed:** the shape-style buttons now reframe after the rebuild.

### Stated honestly
This is a hypothesis that fits the evidence, not something I have watched happen — I have no
browser. The geometry claim IS measured and solid: nothing is mirrored. If a flip is still
visible after this, it is in the display and not the model, and the next thing to check is
whether it survives pressing **Recenter** — if Recenter fixes it, this diagnosis was right and
something else also needs reframing; if it does not, the diagnosis is wrong and I should be
told rather than left to guess again.


======================================================================
## SMOOTH vs FOLLOW MY DRAWING AT A 2 mm WALL — I OVER-CLAIMED. Corrected.
======================================================================
**An earlier version of this section said the exact builder plants a plank at 2 mm while Smooth
builds a proper cavity. That was wrong, and it was written from ASCII cross-sections rendered
at ~5 mm row spacing — far too coarse to tell a 2 mm roof from a solid slab.**

### What the rays actually say, at x=30% of the length
    FOLLOW MY DRAWING 2mm   2 runs, walls 2.3mm and 2.8mm     hollow, correct for a 2mm ask
    SMOOTH 2mm              2 runs, walls 5.6mm and 5.2mm     hollow, but ~3x over the ask
Both are hollow. Neither has a plank there. And the exact builder is the ACCURATE one — Smooth
overshoots the wall by nearly three times.

### And the thing that looked like a plank is a roof
A full-width run at x=20%, z=51.5 appears in the exact build at 2 mm AND at 4.2 mm AND in
Smooth — which was the clue that it is not a defect. Vertical runs at that station read
**[36.1 + 5.3] and [48.8 + 4.2]**: a floor, a cavity, and a 4.2 mm roof, which is exactly the
wall requested. The deck is simply low there, so a horizontal ray through the roof crosses the
whole width. **A single wide horizontal run is not a plank on its own — a plank is a wide run
with NOTHING under it.** The original plank detector always paired the two; I dropped that
pairing and mis-read my own tool.

### So what remains true from the 2 mm investigation
The gate finding stands and is measured: at 2 mm the exact builder does NOT run field hollow,
it falls back to the vertex push, and that fallback is worth warning about. What is NOT
established is that the fallback visibly ruins this model. The warning shipped in 68a90bb9
says "thin sections MAY come out as a flat shelf", which is the right strength of claim.

### What Collin is seeing in his screenshots is still unexplained
He drew arrows at something in the middle of his car and says it persists on a featureless
body. I have not reproduced it on the fixtures available here. **The next useful step is his
model**, not more probing of mine — the profile JSON for the car in those screenshots would
settle in one build what I have now spent two turns circling.

======================================================================
## THE "SMOOTH OVERSHOOTS THE WALL BY 3x" CLAIM — wrong. Both modes are accurate.
======================================================================
_Measured 2026-08-23 on the rebuilt harness, against ee6362ba (the loft path is untouched by
any of the 2026-08-17 fixes, so the reading is valid for the current build too)._

### Smooth, wall asked vs wall built, across the width at mid height and length
    asked 1.0  -> 1.02mm      asked 4.2 -> 4.26mm
    asked 2.0  -> 2.03mm      asked 6.0 -> 6.09mm
    asked 3.0  -> 3.05mm      asked 8.0 -> 8.12mm
**A flat 1.02x at every thickness.** Not a 3x overshoot, and not an offset either — a 2%
scale, which is a fillet/normal-averaging effect and is fine.

### And sampled properly across 58 stations at a 2 mm wall
    loft        p10 2.03   median 2.18   p90 3.70   max 6.89
    projection  p10 1.44   median 2.26   p90 3.86   max 4.16
Both build a median of about 2.2 mm on a 2 mm ask. **The 5.6 mm reading that started this was
one ray in the p90 region, where two walls meet** — a corner is not a wall, and a single sample
cannot tell them apart.

### The method rule this is the second instance of
On 2026-08-17 I called a roof a plank from one wide run. Here I called a corner a wall from one
thick run. **Both times a single ray was treated as a measurement.** A ray gives one number;
a distribution over many stations gives a fact. `shellWallStats` already does the latter and
already had `worstPatch` for exactly this reason — use it, or sample a grid, but do not
conclude from one.


======================================================================
## WHY A PLANK IS HARD TO DETECT AUTOMATICALLY — and what it means for the report
======================================================================
_Worked out 2026-08-23 while trying to build a reliable plank detector. This is the reason
every quick check I have made in the last week cried wolf._

### A wheel arch looks exactly like a plank to a naive test
At a wheel station on a **solid** body — which cannot contain a plank by definition — walking
the full height at x=140:

    z=83  [-36 +73]      z=59  [-52 +105]
    z=77  [-40 +81]      z=53  (nothing)
    z=71  [-43 +87]      z=47  (nothing)
    z=65  [-46 +93]      ...down to the ground: nothing

Material from z=59 to z=83, air below it all the way down. That is the cabin sitting above an
open wheel arch — **correct**, and it satisfies every naive plank test: one wide run, nothing
underneath.

### So "wide run with nothing below" is NOT sufficient
The pairing rule I wrote on 2026-08-17 is necessary but not sufficient. An open underside and
open arches are deliberate features of these models, and they legitimately leave material
floating over air at exactly the stations a plank would appear.

A real plank is narrower than that: the DECK section building as a single plate about one wall
thick where it should have been a hollow box — top skin, wall, cavity, wall, bottom skin. The
distinguishing feature is the missing UNDERSIDE OF THE DECK, not air somewhere below.

### What this means for Collin's screenshots — worth him checking in one look
He drew arrows at something in the middle of his car, seen through the wheel arches. **A body
above an open arch is supposed to be there.** The question that separates the two, and it takes
one glance on the device:

  - Is the thing he sees **connected upward** to the roof/cabin? Then it is the body above the
    arch, and it is correct.
  - Or is it a **thin plate floating with clear air both above AND below it**? Then it is a
    plank and I need his profile JSON.

I cannot tell these apart from a screenshot, and I have now twice convinced myself I found a
plank in geometry that turned out to be a roof or a cabin.


======================================================================
## THE SHARED PROFILE SCHEMA — rewritten from the code. 18 -> 54 properties.
======================================================================
    LEE3D-Lib/schema/profile.schema.json    md5 83a60ca8   (was 198 lines, now 656)

The old file declared 18 properties and **none of the 21 keys the engine actually runs on** —
no outlines, no features, no hollowing, no wall settings, no carve mode. Its required list was
from before tracing existed.

### Derived from the code, not from memory
The key list came from three sources cross-referenced: every `p.xxx` the studio reads (79
candidates, filtered to the real ones), every `profile.get()` the backend reads (18), and every
key present in the nine real saved profiles (47). Writing it from what I remembered would have
reproduced my own blind spots.

### `x-read-by` on every key is the point of the file
    54 properties — 54 read by the studio, 16 by the exact backend, 16 by both
Four bugs in one month were all the same shape: **one end knowing about a key the other did
not.** Pockets dropped from every STEP export. Extra views ignored without a word. Per-face
wall honoured by one builder and not the other, then not by the backend either. None raised an
error. `x-read-by` puts that in the contract: if a key says `[studio, exact]` and only one of
them reads it, that is the bug, written down.

### It catches real malformations, and lets unknown keys through
Ten deliberate breakages, all caught: missing length, length as a string, a negative wall, a
misspelled carveMode, an invalid quality step, a feature view that does not exist, an outline
point with one coordinate, a two-point "outline", an extraViews entry with no poly, a mode no
builder implements. And an unknown key is correctly NOT rejected — `additionalProperties` stays
true, because a saved model must never fail to load over something the schema has not been
taught yet.

**All nine real profiles validate**, across the library, the projects folder and the frontend
fixtures.

### THE CHECKER — the schema is now enforced, not just written down
    LEE3D-Lib/tools/check_schema_coverage.py   md5 32e2bae1   (API + copy-drift checks)
    LEE3D-Lib/.github/workflows/schema.yml     md5 5d286d36

A claim nobody checks is worth nothing, so `x-read-by` is now checked. The script reports three
kinds of disagreement:

    UNREAD      the schema says an end reads a key and that end's source never mentions it.
                THIS IS THE DIVERGENCE BUG.
    UNDECLARED  the studio reads a key that real profiles carry and the schema has never heard
                of. The schema drifting behind the product — the state it was found in.
    ORPHANED    declared but nobody reads it. Usually a rename left behind.

### It was tested by reinstating the actual bugs, not by hoping
A checker that passes on its first run may simply not be checking. So each of this month's real
divergences was put back and the checker run against it:

    removed extraViews from the backend (its state before 2026-08-15)
      -> UNREAD  'extraViews' is marked [exact] but the exact backend never reads it
    removed wallTop/wallSide/wallBottom from the backend (its state before 2026-08-16)
      -> UNREAD  x3, one per face
    added a new p.ribSpacing to the studio and to a saved car, schema untouched
      -> UNDECLARED  'ribSpacing' is read by the studio and saved in real profiles

**All three caught, including one that has not happened yet.** Against the repos as they stand:
5/5 profiles validate and no disagreements.

### The workflow checks out all three repos, because no single repo can answer the question
`schema.yml` clones the studio and the backend alongside the library. It also runs weekly on a
timer, because the other two repos can drift without anything happening in this one. If a
checkout is skipped the profiles are still validated, so the step is never a no-op that quietly
passes.

### THE API CONTRACT NOW NAMES THE TRACED SHAPE — fixed
    app/schemas.py    md5 02364ebe    -> BOTH LEE3D-Backend-A/app/ AND LEE3D-Lib/app/
                                         (they must stay identical; they were, and are)

It named 35 fields; it now names **62**, and the undeclared count against the schema went
**40 -> 13**. Everything still missing is studio-only — revolve mode, reference images, size
overrides — and **none of it is traced shape**.

All the new fields are `Optional[...] = None`, because ABSENT and NULL have to mean the same
thing here. That is not an assumption: `_hollow_wanted` was tested with hullHollow absent,
hullHollow null, sepBottom null, and both null together — hollow=True in every case. Declaring
these does not reopen the sepBottom/hullHollow trap.

**Round trip verified, not asserted:** a real 228-pocket car through
`plan(Profile(**car).model_dump())` gives byte-equal pockets, wall, hollow and cuts.

### And the historical bug is now structurally closed
The comment in that file records what it once did: `extra="ignore"` meant every unnamed field
was dropped on the way in — "sidePoly, topPoly, features, hullCrisp, hullHollow, wallTop... the
entire traced shape". Nothing errored. `/generate` then wrote the stripped object into the
versions table, so restoring a saved version handed back a model with no tracing in it.

Tested in a separate tree with `extra` genuinely set to `"ignore"`: **all 228 pockets and the
full traced shape now survive.** The contract no longer depends on `extra="allow"` being left
alone.

### A THIRD declaration of the profile — `app/schemas.py`
There are three places the profile is written down: this schema, the code that reads it, and
the pydantic model the backend validates requests against. That model exists as **identical
copies in the backend and the library** (both a595b9c3, so no drift between them) and it names
**35 fields against the schema's 54**.

**Nothing is broken by it.** `model_config` sets `extra="allow"`, so every unnamed key passes
through untouched — a real car round-trips through `Profile(**car).model_dump()` with all 228
of its pockets and the same wall settings. Verified, not assumed.

But a contract that does not name `features`, `hullHollow` or `carveMode` is not documenting
the thing it guards. **If `extra` is ever tightened to "ignore" or "forbid", all 40 unnamed
keys vanish silently from every request** — every pocket, every outline, every wall setting.
The checker therefore reports it as a note today and **fails the build the moment `extra`
changes**, with the list of what would be lost. Both directions tested.

### The checker caught ME with its own stated limit
My first version of that test searched the file for `extra="ignore"` and found it — **inside a
comment** explaining that ignore is pydantic's default. It reported a strict contract on a file
whose real setting is "allow". That is exactly the grep limitation written at the top of the
tool, and it bit inside the tool itself. Fixed by reading the `ConfigDict(...)` line and only
that line. Worth recording: a documented limitation is not a handled one.

### DONE 2026-08-30: `LEE3D-Lib/app/schemas.py` is deleted
_Collin removed it. `app/` went with it, which is correct — it was the only file there. The
checker no longer prints COPY-NOTE; API-NOTE is unaffected because it always read the
BACKEND's copy. The rest of this section is kept as the reasoning, and as the record of what
was verified before the delete._

### The case for it, as it stood
That file is a byte-identical copy of the backend's, and **nothing in the library imports it** —
not the README, not a workflow, not one file. It is the only Python in that repo besides this
checker. A copy nobody reads cannot be caught being wrong, so it is pure liability: the day the
backend's version gains a field and this one does not, the two disagree and only a reader
looking at the wrong one would ever find out.

Deleting it costs nothing and removes a drift risk.

**RE-VERIFIED 2026-08-30, and the answer to "does a schemas.py need to go somewhere else?" is
NO — nothing replaces it, not at the Lib root, not anywhere.** Tested by actually deleting it
from a scratch copy of the repo and running the workflow's exact command:

    checker exit 0, "clean — the schema and both codebases agree on what a profile is"
    COPY-NOTE  gone (the block is guarded by `mine.exists()`; absent means skipped, not failed)
    API-NOTE   UNCHANGED — it reads `Path(args.backend)/"app"/"schemas.py"`, the BACKEND's copy
    backend suite unaffected: 62 passed, 1 skipped

The reason it needs no replacement: the library repo contains no Python that imports anything.
`app/schemas.py` was the only file under `app/`, so deleting it removes the folder entirely —
git does not track empty directories, and that is correct, not a loss. The pydantic contract
lives in `LEE3D-Backend-A/app/schemas.py`, which is the copy that actually guards requests and
the copy the checker has always read for its API-NOTE.

**Leave the checker's 3c block in place.** It becomes dormant, not dead: it is what catches the
copy coming back and drifting.

**If the copy is kept anyway, it is now enforced.** The checker byte-compares the two and
**fails the build if they differ** — tested by adding a field to the backend copy alone:

    DRIFTED  app/schemas.py differs between this repo and the backend (6846 bytes vs 6923).
             One of them is telling somebody the wrong thing about what a profile is.

### A stated limit
The checker greps source text rather than parsing two languages. Grep can be fooled — a key
named only in a comment counts as read — so it is a floor and not a ceiling. Everything it
reports is real; it will not catch every possible divergence.

### Two things the code corrected me on while writing it
  - **`frontHull` is an outline, not a number.** The name reads like a scalar. I typed it as
    one and a real file said otherwise. Assuming a type from a name is how a schema ends up
    describing somebody's idea of the format rather than the format.
  - **`null` is how "not set" is stored** for the traced outlines, hullRes and the optional
    profiles. My first version rejected it and failed five of the nine files it was meant to
    describe — which is exactly the right test of whether a schema records reality.

======================================================================
## THE CONTRACT IS NOW CHECKED BY RUNNING IT, not just by grepping
======================================================================
    LEE3D-Backend-A/tests/test_schema_contract.py    md5 2bf2c4da    (5 tests)

The coverage checker in LEE3D-Lib greps: a key named only in a comment counts as read, and it
says so. For the one end that can be executed here, this does the stronger thing — **change the
key and see whether the answer changes.**

### Caught, by reinstating the actual bugs
    backend stops building pockets (its state before 2026-08-15)   -> assert not ['features']
    backend stops reading extraViews (before 2026-08-15)           -> assert not ['extraViews']

The first is the bug that dropped all 153 pockets from every STEP export of profile_7.

### Three false positives on the first run, all real behaviour, all now documented
A key can matter without moving `plan()` on a given profile, and a test that does not allow
for this becomes noise:
    CONDITIONAL  `sepBottom` only decides anything when `hullHollow` is ABSENT. Tested on a
                 profile with hullHollow removed: True -> hollow=False, False -> hollow=True.
    REPORTED     `sidePolyR` cannot be used by the exact build and it SAYS so — plan() sets
                 `ignored_second_side`. A key read in order to be honest about not being
                 usable is read.
    ELSEWHERE    `name` never reaches plan(); it names the exported file. Checked by source.
Each has its own test rather than a bare exemption, so none is taken on trust.

### A hole the mutation test could not see, found by testing the test
Switching the per-face wall branch off **was not caught.** The reference car has a uniform wall,
so `wall_varies` is False whatever wallTop says, and changing one key at a time never reaches
the branch. **A key can be read and still be unreachable, because a DIFFERENT key gates it.**
Added a test that asserts the gate itself.

### And a limit that cannot be closed here, stated rather than left quiet
Disabling the per-face branch INSIDE `build_solid` still passes everything above: plan() keeps
reporting `wall_varies` True with the right spec, and the cavity maths still computes the right
offset. **The plan stays honest while the build stops using it** — and plan() is all that runs
without OpenCascade. Only the kernel-gated tests can see that difference, and they skip
wherever CadQuery is absent. That is a real limit of testing a CAD build without a CAD kernel,
not something a cleverer assertion would fix.


======================================================================
## CADQUERY RUNS HERE NOW — and the first thing it found was a year-old trap
======================================================================
    pip install cadquery   works. 2.8.0. The "not pip-reliable" note in requirements.txt is
    out of date, and the kernel tests have never been run until 2026-08-23.

### The trap: `build_solid(profile)` returned a SOLID BLOCK in silence
    def build_solid(profile, hollow: bool = False)
`hollow` was a PARAMETER defaulting to False, not read from the profile. So calling it directly
on a profile that says `hullHollow: true` gave back a solid lump and raised nothing.

**The real export path was never affected** — it passes the flag. But every test written
against `build_solid` directly was measuring a solid, **including the four kernel tests I wrote
to check the pocket geometry.** They were named for hollowing they were not checking.

    build_solid(blk)                      240000 mm3   <- a solid block, silently
    build_solid(blk, hollow=True)         105000 mm3   <- what the profile asked for
Fixed: `hollow=None` now means ASK THE PROFILE. An explicit True or False still wins, so the
export path is byte-unchanged.

### And the skip guard was inverted, which is why none of it had ever run
    @pytest.mark.skipif("cadquery" not in [m for m in sys.modules] and True, ...)
That skips whenever cadquery has not ALREADY been imported — which in a fresh pytest run is
always, even with CadQuery installed. Replaced with `importlib.util.find_spec`.

### What the kernel confirmed, finally, by executing it
    pocket over a 30x18mm footprint, 5mm deep     removed exactly 2700 mm3   (predicted 2700)
    the same as a raise                             added exactly 2700 mm3
    all six views                                 envelope unchanged; top/bottom, side/sideR
                                                  and front/rear pair exactly
    per-face cavity, 5mm walls with a 15mm floor  105000 -> 150000 mm3, +45000 (predicted ~45000)
**The per-face cavity I shipped blind is correct.** So is the pocket work. Neither had ever
been built.

### Two tests added for what nobody had written
`test_a_hollow_profile_comes_back_hollow` and `test_a_thick_floor_really_is_thicker_in_the_solid`.
The first exists because a test that cannot fail is worse than no test — it is counted.

**Backend suite: 31 passed in tests/test_hull.py, kernel tests running for real.** The full
suite takes ~5.5 minutes now that OpenCascade is actually doing the work, up from seconds.


======================================================================
## THE CAD KERNEL NOW RUNS IN CI — in its own job, so the gate stays fast
======================================================================
    .github/workflows/ci.yml   md5 60dc37d2    (new `cad` job alongside `test`)
    requirements.txt           md5 62d4dba6    (the conda-only note corrected)
    tests/test_hull.py         md5 91d6511d    (skip guard hardened)

### Why this had never happened
`requirements.txt` said cadquery was "NOT pip-reliable across platforms" and pointed at conda;
`ci.yml` said the CAD path "is exercised locally". Between those two, **the kernel tests ran
nowhere at all** — and the inverted skip guard meant they would not have run locally either.
The exact build's geometry went unchecked for months while its plan was tested thoroughly.

### The shape of the fix
A separate `cad` job, `continue-on-error: true`, so a heavy dependency can never slow or break
the merge gate. It installs cadquery, **asserts the kernel is really there** (a silent absence
would turn every test into a skip and look like a pass), then runs the suite for real. About
five minutes, against seconds for the fast job.

### The guard, hardened after it bit twice
    was:  "cadquery" not in sys.modules and True     -> skipped unless already imported: never
    then: importlib.util.find_spec(...) is None      -> better, but find_spec can RAISE
    now:  a try/except helper, evaluated once
`find_spec` raising at module level kills COLLECTION and takes every test in the file with it,
not just the ones needing the kernel — a worse failure than the skip it was meant to produce.
Found by simulating a broken install rather than by reasoning about it.

### Both paths verified
    with the kernel      31 passed, 1 skipped   (real OpenCascade geometry)
    without it           29 passed, 3 skipped   (clean skips, nothing broken)


======================================================================
## STEP EXPORT OF A REAL CAR — was coming out SOLID. FIXED.
======================================================================
    app/hull.py         md5 4e4c26c5
    tests/test_hull.py  md5 619ebd3d

### What was wrong
`shell()` offsets every face at once and needs them all to offset consistently. A traced car has
**188 faces** against a plain block's 6, many near-tangent, and one bad offset returns a Null
TopoDS_Shape. The code caught it, printed a line nobody reads, and **returned the solid** — so a
real car exported as 807 cm3 of material where a 4.9mm shell was asked for. Valid file, no
error, wrong part. It predates every change made here; it went unseen because the kernel tests
had never run, which is the thing fixed three turns ago.

### The fix: build the cavity, do not offset the faces
Intersect the three outlines pulled inward, cut that out. The same carving principle as the
body itself, one level in — and it never calls `shell()`.

    a real 228-pocket car
      before   807,208 mm3   solid, silently
      after    347,497 mm3   a genuine shell, one valid solid, 29.9s
      plain body (no features)   812,242 -> 352,531 mm3 in 1.7s

### Why `offset2D` and not our own `offset_inward`
Pulling a polygon inward by hand creates loops wherever an edge is SHORTER than the wall. On
this car a **4.22mm edge against a 4.9mm wall** folded past its neighbour and produced a
self-intersecting outline, which OpenCascade will build and then refuse to intersect — every
pair of inset prisms came out empty while each had healthy volume. `offset2D` removes those
loops itself.

### PER-FACE NOW WORKS ON A REAL CAR TOO — by offsetting nothing
`offset2D` takes one distance, so per-face cannot use it directly, and the hand-rolled offset
tangles a traced outline. The way through is to offset NO polygon at all:

**Build the cavity at the THINNEST face, where offset2D is reliable, then trim it back with
half-spaces for the faces that want more.** Trimming can only make a wall thicker, never
thinner, and roof/floor/flanks are axis-aligned — which is exactly what wallTop, wallBottom and
wallSide mean. No polygon arithmetic to go wrong.

    reference car, 5mm walls
      uniform          358,965 mm3
      floor 15mm       394,796   +35,831   1.7s
      roof  15mm       390,077   +31,111   1.8s
      side  12mm       379,280   +20,315   1.8s
    and all together: 228 pockets + a 12mm floor with 4.9mm walls
      369,530 mm3, one valid solid, 30.3s

### Reported, not swallowed
When the cavity genuinely cannot be built, `p["hollow_failed"]` is set. The API should surface
that the way it surfaces `unusable_views` and `surface_only`; right now `plan()` says
`hollow: true` because the profile asked and the build can still disagree.

### Pinned
`test_a_real_traced_car_comes_back_hollow` loads an actual traced profile rather than a box,
because a six-faced block shells fine and every existing test passed while this was broken.

======================================================================
# ON THE HORIZON — HOLOGRAPHIC VIEW (Collin's big bet). NOT IN PROGRESS.
======================================================================
_Recorded 2026-08-16 at Collin's request so it is understood and not lost. **Do not start work
on this** — it is behind the photo-to-3D groundwork and the items already open. Collin will
explain it more fully at a later point; what follows is my understanding so far, and it should
be corrected by him rather than treated as settled._

**The idea as I understand it:** view and work with a model as something occupying real space
rather than a picture of a solid on a flat screen. It is described as a big bet on the project
— a direction, not a feature.

**Why it is not a detour from what is already built.** Everything this engine does is already
volumetric. The body is a signed distance field on a 3D grid, not a surface that happens to
look solid; features are carved into that field; hollowing is a second isosurface of it. A
display that wants to know what is at a point in space is asking exactly the question the field
already answers, and `makeVisualHull` could serve it without a mesh at all.

**What already points this way, if it turns out to be the direction:**
  - `p.extraViews` carves from silhouettes at ANY angle, orthographic or perspective, with a
    real camera model (`from`, `dir`, `up`). That is a scene description, not a modelling knob.
  - point-cloud import/export already exists in both directions (PLY, XYZ, PCD).
  - the `ax, ay, az` face labelling added for per-face walls is the same instinct: points
    carrying which direction they face, so they can be placed and reasoned about in 3D rather
    than per-view.

**What would need answering when it is picked up:** what the display target actually is (a
headset, a light-field or volumetric display, a phone doing stereo or head-tracked parallax);
whether it is for viewing only or for editing in space; and how the exactness this project
insists on — dimensions to the millimetre, printable walls — survives a medium where depth is
perceived rather than measured. That last one is the interesting question and the one worth
Collin's own framing.

======================================================================
# FOR COLLIN TO CHECK — things I cannot verify myself
======================================================================
_I have no browser and no GPU: I can build meshes headlessly and measure them, but I cannot
see the app, click anything, or judge how something reads. Everything below is verified as
far as code and numbers go, and unverified as far as a person using it goes. Tick items off
and delete them once confirmed._

**0a. The thing in the middle of the car — ANSWERED 2026-08-30. NOT A BUG. CLOSED.**
   - Collin: **connected up to the cabin.** That is material above an open wheel arch, which is
     correct geometry and looks exactly like a floating shelf from the side. There is no plank
     and there never was. **Do not reopen this and do not write another plank test** — three
     sessions have now gone into it, two of them producing corrections of my own measurements
     rather than findings. It is answered by the person who can see it.

**0. Recenter does NOT fix the "flipped" Smooth body — ANSWERED 2026-08-30, and the
    DIAGNOSIS THAT CLOSED THIS WAS UNSOUND.**
   - Collin pressed Recenter: **still flipped.** So it is not the camera framing.
   - **The measurement used to rule out an orientation problem could not have detected one.**
     The recorded finding was "the two builders are measurably identical in orientation
     (bounding box, width-by-height, height-along-length agree within a millimetre)". Those are
     DIMENSIONS. A bounding box is invariant under reflection, and it is invariant under
     translation. Reflection and translation are precisely the two things that could cause what
     he is looking at. **The check was blind to the only two answers.**
   - **And on placement the two builders flatly disagree.** Measured on the real 98-point
     traced charger fixture, headlessly, both builders from the same profile:

         smooth   x[-99.5, 99.5]   centre x =   0.00
         hull     x[  0.9, 199.1]  centre x = 100.00

     **Exactly L/2 apart.** The smooth loft centres the body on the origin; the visual hull
     spans 0..L. Reproduced on a synthetic 200mm body too. **Nothing in the app translates
     between them** — the only `L/2` in index.html is extra-view maths inside makeVisualHull.
     The backend agrees with the HULL convention (`hull.py` maps the side outline to
     `(u*L, v*H)`, so 0..L), which makes the smooth loft the odd one out of the three.
   - **What is NOT established: a flip.** I could not reproduce a reflection. A roofline
     comparison came out inconclusive — reversed RMS was marginally lower than forward, but
     only because the smooth roofline is nearly flat, which makes reversing it cheap. That is
     an artifact, not evidence, and it is not being recorded as one.
   - **Features are fine on both.** A pocket drawn at u 0.10-0.20 lands at u=0.13 on the smooth
     body and u=0.13 on the hull. Feature placement is in u-space relative to each body's own
     extent, so the origin offset does not corrupt it.
   - **NEXT, and it needs Collin, not more of my fixtures:** send the profile JSON of the model
     that looks flipped. Three attempts on synthetic and library fixtures have now each turned
     into a correction of my own measurement. His model settles it in one build.
   - **Whether to move the smooth builder to 0..L is a DECISION, not a bug fix.** Two of three
     builders already use it, but the change touches sculpt, section cuts, the export path and
     277 tests. Not started, deliberately.

**1. Thin-wall warning banner** (added 2026-08-11, **layout bug fixed 2026-08-17**)
   - RE-CHECK: it broke the mobile header — see the mobile-bugs section. It now sits below the
     header rather than inside it. Confirm it appears as a full-width band under the top bar
     and does not move anything else.
   - It appears on a model with a thin spot and does NOT appear on a healthy one.
     profile_7 should trigger it immediately: it has 0.55mm and 1.04mm patches against a
     4.2mm wall, so that is a good first test.
   - The wording reads as a decision, not a statistic: "Thin wall: 0.6mm where you asked for
     4.2mm (13%). This spot may snap when printed or handled."
   - **Show me** actually frames the right place. This is the piece most likely to be wrong —
     it converts a mesh-space point into the scene, and I could not test the camera.
   - It does not flicker or jump while dragging a slider (it is meant to be suppressed
     mid-drag).

**2. "How details are cut" selector** (added 2026-08-11)
   - It appears under Shape style, only when **Follow my drawing** is selected, and hides
     when you switch to Smooth.
   - Switching it visibly changes a model that has pockets. Cut into the shape should give a
     deeper, cleaner pocket; Press on the surface is the old look.
   - The labels make sense to someone who has not read any of this. I chose plain words over
     "field carve" and "vertex stamp", but you know the audience.
   - Saving a model and re-opening it keeps the setting.
   - An OLD saved model (one from before today) opens on **Press on the surface** — that is
     deliberate, so re-opening an existing part does not quietly reshape it. Worth confirming
     one of Lee's old files still looks the way he left it.

**3. "Too small to build" warning** (added 2026-08-12)
   - Draw a very small detail on a large model and confirm the banner explains it in words
     that make sense: it names the detail, says how wide it is against what the build can
     resolve, and says what to do (bigger detail, or bigger model).
   - Confirm the **Show me** button hides for this case — a too-small detail is wrong
     everywhere it appears, so there is no single place to fly to. Only the thin-wall warning
     should offer it.
   - Confirm a normal-sized detail does NOT trigger it.

**4. Build quality selector** (added 2026-08-13)
   - **This is the one with a real risk on device.** Fine builds ~103k triangles against
     Normal's ~44k on a 200mm model. That is fine in a Linux container; I cannot tell you what
     it does to an iPhone's memory or to Three.js. Try Fine on the phone before anyone else
     sees it, and if it struggles, lower the `fine` cap from 120.
   - Draw a detail too small to build, confirm the warning now names the step that would fix
     it, switch to that step, and confirm it actually builds correctly and the warning clears.
   - Confirm a detail too small for ANY step says so instead of naming one.
   - Confirm the control shows in both Smooth and Follow my drawing (unlike crispness and
     carve mode, which are Follow-my-drawing only).

**5. Build feel on a phone**
   - Cut into the shape is ~3x slower on a heavily-featured model (7.5s vs 3.3s on profile_7
     in a Linux container; slower on an iPhone). You said this is acceptable for now — but it
     is worth feeling on the device before it goes to Lee or Curtis.

**6. Anything visual, ever.** Rendering, colours, layout, whether a model LOOKS right. Every
   geometry claim in this file is a measurement, never an inspection.

======================================================================
## SHIP THESE THREE (in /mnt/user-data/outputs/)
======================================================================
    index.html            md5 542536fe  ->  LEE3D-Frontend/index.html
    test/core.test.mjs    md5 ebc86514  ->  LEE3D-Frontend/test/core.test.mjs
    test/fixture-hollow.json md5 68f75b4a -> LEE3D-Frontend/test/fixture-hollow.json

**277 passed, 0 failed.** Verified from a clean tree with all three files in place.
NOTE: the suite now takes ~10 minutes (was ~5). Worth trimming before it gets painful.
This build INCLUDES the carve rewrite. Build time on profile_7 with 153 features is ~20s
(vs 3.4s without carve) — accepted for now, deliberately, in exchange for correctness.
(An intermediate build of this same session was 805fd16a / 2b1c2f90 at 205 green — that is
superseded. The only difference is the adaptive wall, which is flag-gated and defaults OFF,
so the two produce identical geometry unless adaptiveWall is turned on.)

This build contains everything: the point-cloud I/O that was shipped last session but
never pushed, plus field hollow ON BY DEFAULT, plus the wall report.

### The repos were behind — check this before assuming anything
The zip of LEE3D-Frontend had `index.html` at md5 **f3a43b5e**, which is the build from
BEFORE point-cloud I/O. All ten point-cloud functions (parsePLY/XYZ/PCD, parsePointCloud,
toPLY/XYZ/PCD, samplePointCloud, dedupeVerts, showCloudInView) were absent from the repo.
The committed `test/core.test.mjs` was the old 189-test suite with zero point-cloud
references. `fixture-hollow.json` IS correctly committed now (68f75b4a) — that trap is
closed and the deploy gate is no longer blocked by it.

The 197-test suite described in the previous handoff exists nowhere. It was not in the
uploads and not in the repo. The suite here was rebuilt from the repo's 189-test version by
re-adding the async runner and writing fresh point-cloud tests. It is a reconstruction, not
a recovery.

======================================================================
## TWO CORRECTIONS TO THE PREVIOUS HANDOFF
======================================================================
**1. "Always verify at res 80" is WRONG, and it is why detectors kept lying.**
The cap line reads:
    const res=Math.max(20,Math.min(80,Math.round(p.hullRes||Math.max(p.stations||48,40))));
profile_7 has **72 stations**, so its real build resolution is **72**. Forcing hullRes:80
gives 47,168 tris / 180.3 cm3 — a different mesh. Building at the profile's own default
gives **37,368 tris, 24,176 verts, 183.0 cm3, bbox 199.7 x 114.8 x 81.3**, watertight,
matching the locked repro and the on-screen readout exactly.
The rule is: **build at the profile's default resolution.** Not a fixed number.

**2. "Solid fraction must drop below 14.5%" was chasing the wrong number.**
That figure came from the broken build's *omissions*, not from efficiency. See below.

======================================================================
## THE PLANK — solved, and it was a DELETION not an addition
======================================================================
Rendering the deck cross-section against a solid reference settles it. At x=30%:

    SOLID    z 44.9 -> 56.1  full-width slab, ~15mm tall
    OLD      z 53.3 -> 56.1  top skin only. THE BOTTOM SKIN IS MISSING.
    FIXED    z 53.3 -> 56.1 top, side walls, z 44.4 bottom skin. A closed box.

The old build kept the hood's top wall and side stubs and simply dropped the deck's
underside. What you see through the arch is that plate hanging with nothing under it.
Field hollow restores it. That is why the fixed build holds MORE material (183 -> 253 cm3)
— the extra is the skin that should always have been there. Any metric that rewards the
old number is rewarding missing geometry.

Detector that works, in /home/claude/probe/: `xsec.py` (ASCII cross-section by ray parity —
this is the one that shows the plank), `fillscan.py` (per-station fill vs the solid body),
`perpwall.py` (true perpendicular wall), `fracv.py` (solid fraction, reproduces the old
14.4%), `section.py`, `harness.mjs` + `build.mjs`.
Rays ACROSS the width inflate wall readings on any sloped wall by up to 1.41x — measure
along the face normal instead.

======================================================================
## WHAT CHANGED IN index.html
======================================================================
**1. Shell field rewritten — the outer skin is now bit-identical to the solid build.**
Step2 used `max(dist, -(dist+wall))` with `dist = b/|grad b|`, normalising BOTH terms. The
mesher finds a crossing by interpolating values along a grid edge, so rescaling those values
by a varying 1/|grad| slides the crossing point — it cost 0.3mm of width, and a coarser
gradient cost 0.9mm. Now: `max(b, -(dist+wall))`. Outer surface governed by raw `b`, inner
by the normalised distance. Outer is exact; inner is still true perpendicular millimetres.

**2. Gradient only computed where it matters** — skipped outside the body and deep in the
core, since the max() picks the other term there regardless. Six F() calls per voxel now
paid in the wall band only.

**3. field hollow ON by default.** `p.fieldHollow !== false`. Passing `fieldHollow:false`
reproduces the legacy build byte for byte (37,368 tris / 183.0 cm3 on profile_7) — kept
because the exact-STEP backend and old saves round-trip through it.

**4. `HOLLOW_WALL_CELLS = 1.45` — the adequacy gate.** A dual contour places ONE vertex per
cell, so a wall thinner than roughly 1.5 cells makes the outer and inner surfaces land in
the same cell and cancel. Measured on the hollow fixture:

    wall/cell 3.2  -> outside exact to 0.00mm
    wall/cell 1.68 -> 0.07mm
    wall/cell 1.5  -> ~0.5mm faired at the open edge
    wall/cell 0.72 -> 3.19mm SHORT, with stretches of skin missing

Below the gate, field hollow declines and the vertex-offset path takes over — it handles a
thin wall fine because it never has to resolve two surfaces on one grid. Set at 1.45 rather
than 1.5 because the three cell sizes differ by rounding and profile_7 lands on 4.2 vs
4.2000001; a hair of floating point must not decide whether the plank comes back.

**5. `shellWallStats(positions, indices, opts)`** — measures the wall that will actually
print, by standing on each face and marching in along its own normal. Optional `zMin`/`zMax`
band for the visible rim. Agrees with the independent Python probe to ~0.1mm, runs in 167ms
on a 46k-tri model. This is the foundation for Curtis's safety gate; the gate itself (a UI
warning when the achieved wall is under spec) is still to build.

**6. `makeVisualHull` now returns `fieldHollow` and `hullRes`** so callers can tell which
path ran and at what grid.

### Wall quality, measured perpendicular, 4.2mm requested
    old build   median 3.68   p10 2.36   p90 4.48   (over-thick on shallow slopes)
    this build  median 3.82   p10 2.10   p90 4.19   (never exceeds the request)
Better than the old build on median and on the over-thick tail. The residual is
discretisation, not a field error — it converges 3.81 -> 4.03 -> 4.15mm at res 72/110/160.
NO fudge factor was added to close it; the honest answer is resolution plus reporting.

======================================================================
## A THING I TRIED AND REMOVED — do not re-add without reading this
======================================================================
I built an auto-raise: when hollowing, lift the grid until it can hold the wall. **It
backfired twice and is gone.**
  - The SOLID build kept the original resolution, so simply ticking "hollow" moved the
    outside by half a millimetre — the exact invariant the whole exercise protects.
  - Where the wall was far too thin the grid climbed to the cap, cost about 7x the build
    time, and was then rejected by the gate anyway, falling through to the path it would
    have taken at the original resolution.
The grid is now whatever the drawing asks for, and the gate simply decides whether that
grid can hold the wall. profile_7 builds in ~3.4s, unchanged.

======================================================================
## STEP 3 — ADAPTIVE WALL. Rebuilt correctly. Flag-gated, defaults OFF.
======================================================================
`p.adaptiveWall`, default **false**. Off, the build is byte-for-byte the non-adaptive one.

### Why the ORIGINAL step-3 probe failed — do not rebuild it
It fired 26 rays and took the nearest outside sample as the local thickness. But for a point
at depth d the nearest outside sample IS d, so it measured depth-to-surface — which the field
already told us — and the wall tracked depth and collapsed to its floor value EVERYWHERE.
Measured: perpendicular wall median 2.63mm, **p10 0.52mm** against a 4.2mm request, and the
body shrank from 199.7 x 114.8 to 195.7 x 112.1. The old notes called this a corner bug. It
was not. It was measuring the wrong quantity.

### What replaced it
Thickness is **bilateral**. Pick a direction, walk to the surface one way, walk to the surface
the other way, add them — that is the thickness along that direction. Take the smallest over
13 opposing pairs. Both sides have to be close for a section to count as thin, so a corner
(one face near, the other the whole width of the body away) correctly reads THICK.

It reads the already-sampled grid instead of calling F again. The 26 neighbours ARE grid
directions, so marching them is plain array indexing with a linear-interpolation refinement
on the last step. The old probe's ~100 F calls per voxel would have made the build unusable;
this one is free — measured 5819ms with it on vs 6338ms with it off, i.e. inside the noise.

### HOLLOW_THIN_CELLS = 2.0 — the floor, and why it is above the global gate
HOLLOW_WALL_CELLS (1.45) is where a shell stops eating itself outright. Sitting exactly on it
costs ~0.5mm of fairing at the open edge — tolerable once for a whole model, not something to
invite locally all over a body. Measured on profile_7 at an 8mm wall:

    thin down to 1.45 cells -> saved 5.9%, width pulled in 0.6mm   (too far)
    thin down to 2.00 cells -> saved 5.3%, width pulled in 0.2mm   (shipped)

Where a section is too thin for even the floor, no cavity is attempted and it stays solid,
which is the right answer for a thin rib.

### What it actually buys, measured on profile_7
    wall 4.2 (default): NOTHING. wallFloor 5.6mm > wall, so thinning is disabled outright.
                        252.9 cm3 either way. On this grid there is no safe room, and the
                        code says so rather than pretending.
    wall 8.0          : 459.7 -> 435.5 cm3, a 5.3% saving. Deck still builds as a closed box.
                        Over-thick tail improves a lot: p90 wall 13.88 -> 9.45mm.
                        Low tail gets worse:            p10 wall  5.50 -> 4.33mm.

**So it is a real trade, not a free win**, and that is why it defaults OFF and should be a
user-facing choice rather than a silent default:
  - Lee (display frames, material cost matters)      -> worth turning ON
  - Curtis (load-bearing, wall thickness is safety)  -> leave OFF
Adaptive wall only has room to act when the wall is thick relative to the voxel. At typical
toy-car settings it does nothing at all, by design.

Five tests pin it, including **"a corner is not a thin section"** — a chunky box with no thin
sections anywhere must come out unchanged. That is the test that would have caught the
original probe on the day it was written.

======================================================================
## A FAILED HOLLOW NOW REACHES THE API — `X-LEE3D-Hollow-Failed`. FIXED.
======================================================================
_2026-08-29. The last item on the previous handoff's open list._

`plan()` reports `hollow: true` because the PROFILE asked for a shell. It has no way of
knowing whether one was built. When the cavity comes out empty, `build_solid` catches it,
prints, and returns the SOLID — which is the right behaviour, and it said so to nobody.

**Why the flag was unreachable, exactly.** `p["hollow_failed"] = True` was written to the plan
dict created *inside* `build_solid` by its own `plan(profile)` call. That dict is a local. It
was discarded on return. `export_bytes` never saw it, so `main.py` never could. The flag had
the right name and the right value and no way out of the function — it read like a feature and
was a dead end. **A value written to a local you are about to drop is not "set internally", it
is not set at all.**

### The shape of the fix
An optional `report` dict, passed IN by the caller and threaded
`build_solid` -> `export_bytes` -> `main.py`, surfaced as a header beside the others:

    X-LEE3D-Hollow-Failed:  "1"  a shell was ASKED FOR and could not be built; this file is solid
                            "0"  hollowed fine, OR never asked

**Out-parameter, not a second return value.** `build_solid` returns a Workplane that is
unpacked at six call sites in the tests plus `export_bytes`; making it a tuple breaks every
one, and a caller that does not care should not have to unpack a report. The old signature
still works untouched.

**It is seeded `False` when hollowing is attempted, and that matters.** An absent key and a
`False` key mean different things — "nobody asked for a shell" versus "asked, and it worked".
If only the failure path ever wrote, the caller would have to guess which it was holding.
Guessing is what put the pockets bug in the field.

### How it is tested, and where
The trigger is real geometry, not a mock: a 40mm wall on the 40mm-tall test block cannot leave
a cavity. `offset2D` raises `No pending wires present`, the build returns 240000mm3 — the solid
unchanged — and `plan()` still says `hollow: true`. That is the bug, reproduced.

    tests/test_hull.py     3 tests, kernel-gated (the `cad` job)   the geometry and the report
    tests/test_deploy.py   1 test, NO kernel needed (the fast gate) the report -> header wiring

The header test is in the FAST job on purpose. The geometry belongs under OpenCascade, but the
wiring from report to header must not be able to rot unnoticed while the kernel is absent —
that is precisely how four kernel tests sat dormant for a year while reporting green.

**Both new tests were mutation-checked before being believed.** Forcing the header to `"0"`
fails the deploy test; deleting the two report writes fails two hull tests. A test that has
never been seen to fail is not evidence.

======================================================================
## THE INRADIUS THROUGH-SLOT — DIAGNOSED AND FIXED 2026-08-30
======================================================================
_Was "an observation, not a finding" on 2026-08-29. It was a finding. The 2026-08-29 sweep
below is left exactly as it was recorded, because the numbers in it were right and only the
conclusion was missing._

On the `_block_with([])` fixture (100 long, 40 tall, 60 wide), sweeping the uniform wall:

    wall  5mm   105000 mm3   hollow_failed False
    wall 12mm   196224 mm3   hollow_failed False
    wall 14mm   212352 mm3   hollow_failed False
    wall 20mm   192000 mm3   hollow_failed False   <- NOT MONOTONIC, and 20 == half the height
    wall 40mm   240000 mm3   hollow_failed True    <- correct: solid, and it says so

240000 is the solid block. At wall 20 the build removed 48000mm3 and reported success. 48000
is exactly 60 x 20 x 40 — the volume of a prism through the FULL height, which is the shape of
a through-slot, not a shell. A cavity inset 20mm from a 40mm-tall body should enclose nothing.

### THE CAUSE: a collapsed offset is not an empty cavity — it is a plane that stopped voting

At `dist` exactly equal to an outline's inradius, `offset2D` **does not raise**. It returns a
wire of area 0.0, and extruding that gives a solid of volume 0.0. **`intersect()` against a
zero-volume solid is a silent no-op in OpenCascade** — the other operand comes back untouched.
So the collapsed planes simply stopped constraining the cavity, and whichever plane survived
became the whole of it.

Measured on the 100x40x60 block at its 20mm wall: side and front both offset to area 0.0000,
top offset to 1200.0 and extruded to 192000, and the "intersection" of all three was the top
prism alone. Cutting it removed 48000mm3 through the FULL height — an open through-slot in a
part whose entire contract is to be closed and hollow — and the build reported success.

### THE RULE, and why one geometry would have got it wrong
**The critical wall is `min(half-height, half-width)`, NOT half-height.** Measured:

    100x40x60   fails at 20.0   (half-height 20, half-width 30)
    100x26x60   fails at 13.0   (half-height 13, half-width 30)
    100x90x60   fails at 30.0   (half-width 30 — NOT 45, its half-height)
     40x10x20   fails at  5.0

The 90-tall block is the one that matters: it fails at 30, which is its half-WIDTH. A sweep on
the 40-tall block alone would have recorded "half the height" and been wrong on three of four
geometries. This is the fixture lesson again, in a new costume.

### THE FIX
`cavity_uniform` now measures each extruded plane and raises if it has collapsed:

    solids = wp.solids().vals()
    if not solids or sum(s.Volume() for s in solids) <= 1e-6:
        raise ValueError(f"the {key} outline collapses to nothing at a {abs(dist):g}mm wall...")

Raising hands it to the caller's existing handler, which returns the SOLID and sets
`hollow_failed` — identical to the behaviour at 20.0001, which was already right.

**The threshold is absolute and tiny on purpose.** A legitimately thin cavity is still a
cavity. At a 19.9999mm wall the tightest surviving plane (front) extrudes to 1.600016mm3 and
the side to 2.880010mm3 — both about six orders of magnitude above 1e-6. Only an exact
collapse is caught. One tick either side, measured:

    wall 19.999    removes 2.4003mm3   hollow_failed False   <- still a real shell
    wall 19.9999   removes 0.2400mm3   hollow_failed False
    wall 20.0      removes 0.0000mm3   hollow_failed True    <- was the through-slot
    wall 20.0001   removes 0.0000mm3   hollow_failed True    <- always was correct

**The per-face path inherits it,** checked rather than assumed: `cavity_per_face` builds at the
thinnest face via `cavity_uniform`, so a collapse there propagates. At the inradius it reports
`hollow_failed` and returns the solid; just under, it removes 243.21mm3 as one valid solid.

**Why the header could not have caught this on its own:** `X-LEE3D-Hollow-Failed` only knows
whether the cavity THREW. It knew nothing about a cavity that built something silly. A guard
that reports honestly about the failures it can see is not the same as a correct build, and
shipping the reporting first made this findable rather than fixing it.

======================================================================
## A ZERO-VOLUME OPERAND IS DISCARDED BY EVERY BOOLEAN — the root cause
======================================================================
_2026-08-30. Three separate bugs have now come from this one fact. It is written here once,
properly, so the fourth does not._

A wire with no area still extrudes to solids. They just have volume 0.0, and **OpenCascade
does not treat that as an error in any boolean operation.** Measured directly, all three:

    a.intersect(zero)  ->  a, untouched     the constraint silently stops applying
    a.cut(zero)        ->  EMPTY            0 solids. the model is destroyed
    a.union(zero)      ->  volume 0.0       the model is destroyed

**They fail in different directions, so no single instinct covers them.** And critically:

    zero.solids().vals()  ->  2 solids, total volume 0.000000

**`solids().vals()` is NON-EMPTY for a collapsed solid.** Every "is there anything there?"
guard in this file was written as a presence check, and a presence check passes precisely when
it matters most. **Test volume, never presence.** That single sentence is the whole lesson.

### The three bugs, all the same mistake
    1. cavity_uniform      offset2D at the inradius collapsed -> the plane stopped voting and
                           the surviving one became the cavity: a 48000mm3 through-slot,
                           reported as a successful shell.        (fixed, section above)
    2. a collinear OUTLINE `_clean` counted POINTS, not area. [[0,0],[0.5,0],[1,0]] is three
                           DISTINCT points and zero area, so it passed. The side view stopped
                           constraining the intersection and the body came out as the full
                           240000mm3 bounding box, silently.
    3. a collinear FEATURE the same guard, and worse. `tool.intersect(slab)` discarded the
                           zero-volume tool and returned the SLAB — 125,000,000mm3 for a 500mm
                           test slab. The slab became the cutter, so a feature with no area
                           cut a 3mm slot clean across the whole part: 240000 -> 228000mm3,
                           exactly 100 x 40 x 3.

### The fix for 2 and 3: one guard, in `_clean`
All four `_clean` call sites already treat `None` as "degenerate — drop it, or fall back to a
box", so the check belongs there and nowhere else:

    if poly_area(out) <= 1e-12:
        return None

**The threshold is bracketed from BOTH sides by tests, deliberately.** Remove the guard and the
two collinear tests fail; widen it to 1e-2 and the thin-sliver test fails along with
`test_every_feature_with_depth_is_built_as_real_geometry`. A guard that also rejected thin
features would be a worse bug than the one it fixed — thin is exactly what a traced panel line
is. These coordinates are normalised 0..1, where a 0.0005-wide sliver still measures 3e-4 in
area, eight orders above the threshold. Only an exact collapse is caught.

### One test asserts on the OUTLINE, not the volume, and that is not laziness
For the collinear outline the box fallback produces **the same body** — 240000mm3 either way.
A volume assertion would pass with or without the fix. It is pinned on
`len(outlines_mm(prof)["side"]) == 4` instead. *Identical output means the code path did not
run*, and that applies to how a fix is verified just as much as to whether it worked.

### THE STUDIO HAD THE SAME HOLE — fixed at the same time, and pinned together
Fixing only the backend would have been **worse than fixing neither.** The studio's `normPoly`
was `if(!pts||pts.length<3)return null` — the identical count-not-area check — and 18 further
`poly.length>2` guards downstream of it. So after the backend fix the two ends disagreed: the
backend fell back to a box while the studio still built from the flat line, and nothing
reported the difference. That is the one failure mode this project cannot tolerate quietly.

**One rejection at the entry point fixes all 18.** `normPoly` is the single place a traced
outline becomes a stored poly, and every downstream `length>2` guard already handles `null`
correctly by falling back to BOX — which is exactly what the backend does with `_UNIT_BOX`:

    const polyAreaN=(p)=>{...shoelace...};
    return polyAreaN(out)<=1e-12?null:out;

Same threshold, same units (normalised 0..1), same meaning. Verified in isolation before the
suite: collinear 3pt and 5pt -> null, two points -> null, real square / thin sliver / traced
blob -> kept.

**`test_the_studio_rejects_a_zero_area_outline_the_same_way_this_end_does` reads index.html
directly** and fails if the studio's guard is removed or its threshold moves. Mutation-tested:
reverting `normPoly` fails it. A comment saying "matches the backend" is exactly the thing that
stops being true first, so this is enforced rather than asserted in prose. It skips cleanly
when the frontend is not checked out beside the backend, like the schema contract tests.

### What was CHECKED AND FOUND SAFE, so nobody re-checks it
- **`tool.intersect(slab)` at line ~471 is fine as written.** Its guard is also a presence
  check, but a tangential touch between two POSITIVE-volume solids returns 0 solids, not a
  zero-volume one — measured on face-abutting, edge-touching and clear-of cases, all 0.
  Zero-volume solids come from extruding a collapsed WIRE, not from solids meeting.
- **The base-body guard at line ~397 is now covered** by the `_clean` fix upstream: a
  degenerate outline can no longer reach `prism()`.
- **The real traced car is unaffected:** 228 pockets planned before and after.

======================================================================
## THE UNDERSIDE SEALS ONCE THE FIELD HOLLOW SWITCHES ON — FIXED 2026-08-30
======================================================================
_Found with Collin's own profile (untitled-object_profile_8.json). Two earlier sessions failed
on fixtures; his model settled it in one build, exactly as the handoff predicted._

### THE CAUSE
The studio has two hollow paths. `fieldHollow` switches on once the wall is thick enough for
the grid (`wallMin >= cell*HOLLOW_WALL_CELLS`); below that the vertex-offset path runs. The
field builds its wall band against every surface in the body field `F` — **including the
base-levelling clip at line ~3122, `max(d, baseCut - z)`. That plane is not a surface anybody
traced.** A wall band grown against it is a FLOOR sealing the underside.

Measured on his car, his exact settings, sweeping the wall:

    wall  field?  vol cm3   material up the middle (x=100,y=0)
     2.1  false    100.0    85.5-86.9                          open
     2.5  true     164.1    5.0-7.5   85.2-86.8                FLOOR
     6.0  true     380.8    5.0-16.8  81.6-85.8                FLOOR

**The floor starts at z=5.0 — his `baseCutZ` is 5.017.** That is the levelling plane, and it is
why "any thickness over 2mm doesn't allow for the underbody to be hollow at all": 2.1mm is
below the field threshold and 2.5mm is above it.

**`baseCutZ` was NOT the difference between his car and the fixtures.** Collin 5.017,
fixture-hollow 5.672, charger 5.375 — all level cleanly. That hypothesis from the previous
session was wrong.

### THE FIX
`F` gains a `noCut` reading that returns the body WITHOUT the clip, and the cavity is drawn
from it while the outer skin keeps the clipped field:

    const bIn = openUnder ? Math.min(b, F(xm,ym,zm,true)) : b;
    const dist = bIn/g;
    shell[o] = Math.max(b, -(dist+wLoc));      // outer term still reads `b`. Unchanged.

    wall 2.5 / 3 / 4 on his car:  floor GONE, underside open
    277 of 277 pass

### REJECTED, MEASURED — DO NOT RETRY: scaling `wLoc` to zero on ground-facing normals
It removes the floor and is watertight at every wall (0 boundary edges, 0 non-manifold). It
also fails **three** guard tests, and the reason is worth keeping: `-(dist+wLoc)` draws BOTH
surfaces, so zeroing it deletes the outer bottom skin along with the floor. The body's outside
moves and the rim band collapses:

    the rim you see at an opening is a clean band, one wall thick
    hollow: the outside is identical at every wall thickness
    hollow: no vertex of the inner shell lies outside the outer skin

**Touch the cavity's INPUT, never the term the outer surface is read from.** That one sentence
is the whole difference between the fix that shipped and the one that did not.

### CORRECTION 2026-08-30: "2.5-4mm now build open" WAS MEASURED AT ONE STATION AND IS WRONG
I checked the centreline at x=100 only and reported the range as fixed. Sampling four stations
on his car with the final build shows the truth:

    wall  field?   x=60   x=80   x=100   x=140    (first material found on a ray straight up)
     2.1  false    54.5   70.9    85.5    82.8    open all through  <- HIS SETTING. Fixed.
     2.5  true     42.7   31.2    85.2    54.3    floor at 3 of 4
     3    true     42.7   31.1    84.7    54.2    floor at 3 of 4
     4    true     42.6   31.1    83.7    54.2    floor at 3 of 4
     5    true     42.6   31.1     5.0    54.2    floor at 4 of 4
     6    true     42.6   31.1     5.0    54.2    floor at 4 of 4

**A single ray is not a measurement — this file says so, and I did it anyway.** x=100 happened
to be the one station the base-plane fix did clear.

### WHAT IS ACTUALLY FIXED, AND WHAT IS NOT
**Fixed: the vertex-offset path (`!fieldHollow`), which is what runs at his 2.1mm wall.** The
ground-facing angle change from -0.5 to -0.35 opens the sloped arch ceilings, and his car is
open at every station. His reported bug is gone.

**Not fixed: the field path (2.5mm and up) still floors the ARCH CEILINGS.** The two paths open
the underside by completely different machinery and only one of them is complete:

    vertex-offset   bottomSkinTris trims every ground-facing triangle -> base AND arch ceilings
    field           the cavity is drawn from the unclipped body -> the BASE PLANE only

The field path has no equivalent of the ground-facing trim, so a ceiling up at z=31 or z=42 is
never opened however thick the wall. The z=5.0 entries at 5mm+ are the separate base-plane
residual described below; the z=31/42 entries are this gap and they are present at EVERY field
thickness.

**FIXED 2026-08-30.** The field path now opens ground-facing ceilings the same way the
vertex-offset path does, and the two paths finally agree about what the tick means.

    if(openUnder && zm > baseCut + Math.max(wLoc, cell*2)){
      const down = -gz/g;
      if(down > 0.30) wLoc *= Math.max(0, 1 - (down - 0.30) / 0.20);
    }

placed AFTER `wLoc` is settled — it is declared below `dist`, and putting the block earlier is
a `Cannot access 'wLoc' before initialization`.

**ONLY ABOVE THE BASE PLANE, and that is what makes it pass where the first attempt failed.**
Ramping everywhere also strips the flat bottom at the levelled base and lifts the body's lowest
material; restricting it above the base plane cannot move the bounding box at all, because the
extremes are set at the base and the roof. The ramp reaches zero at down=0.50 rather than 0.70
because a real arch ceiling measures about -0.5, and the gentler version only took the wall to
57% there — leaving a thinner floor instead of none, and opening at 3mm but not 2.5 or 4.

    his car, first material on a ray up, four stations:
    wall  field?   x=60    x=80    x=100   x=140
     2.1  false    54.5    70.9    85.5    82.8    open all through
     2.5  true     54.2    70.4    85.2    82.5    open all through   <- was floored at 3 of 4
     3    true     53.3    69.6    84.7    82.0    open all through
     4    true     52.5    68.1    83.7    80.9    open all through
     5    true     51.7    66.7     5.0    79.8    base-plane residual only (see below)
    277 of 277

### I REVERTED THIS ONCE FOR A BAD REASON — the lesson is the metric, again
The first time, I measured the fixture's floor as the mesh's minimum z, saw 0.074mm against a
0.05 tolerance at wall 4.2, called it a gate failure and reverted a working fix.

**The shipped build that had already passed 277/277 shows the same 0.074.** It is baseline, not
a regression: the test's own `box(g).floor` is not the raw minimum z, so my proxy was measuring
something the assertion does not check. Two sessions of work were nearly thrown away on it, and
what caught it was running the proxy against a build already known to be green.

**Before trusting a proxy for a test, run the proxy against a build that passes.** If it
disagrees, the proxy is wrong. Cheaper than every other way of finding this out, and it applies
to every measurement in this file that is not the assertion itself. A guard-height hypothesis
was disproved on the way — the failure was identical at 4, 8 and 12mm — which should have been
the first hint the cause was not in the change at all.

### BOTH ENDS AGREE — verified against the kernel, 2026-08-30
Changing the studio's underside behaviour raised the obvious question of whether the exact
build still matched. It does, and no divergence was introduced. `open_the_underside()` sweeps
the cavity downward, and that sweep passes through an arch ceiling as readily as through a
base-plane floor. His car, features stripped, 3mm wall, measured with `isInside` on the exact
solid rather than on a mesh:

    underside CLOSED   229.3 cm3    x=60 [43.1-46.1, 54.1-57.1]   x=80 [32.1-37.1, 70.1-74.1]
    underside OPEN     128.7 cm3    x=60 [54.1-57.1]              x=80 [70.1-74.1]

The ceilings at 43.1, 32.1 and 55.1 are gone with the tick on and the roof is untouched. The
studio at the same wall gives first material at 53.3 / 69.6 / 82.0 against the kernel's
54.1 / 70.1 / 82.1 — about a millimetre, which is mesh against exact and not a disagreement
about the shape.

`test_the_studio_draws_its_cavity_from_the_unclipped_body` now also pins the arch ramp AND its
base-plane guard, so neither can be removed or loosened without this end going red.
Mutation-checked: stripping the ramp from index.html fails it.

### THE BASE-PLANE FLOOR ABOVE A ~4.2mm WALL — CAUSE FOUND 2026-08-30, not yet fixed
Instrumented properly and the numbers retro-predict the threshold, which is the strongest
evidence available here. Column at mesh (100, 0), wall 5, baseCut 5.017:

    z= 5.56  b=-0.545  bIn=-4.19  g=1.00  wLoc=5.00  cav=-0.81   MATERIAL
    z= 7.42  b=-2.400  bIn=-4.51  g=1.00  wLoc=5.00  cav=-0.49   MATERIAL
    z= 9.27  b=-4.254  bIn=-4.80  g=0.90  wLoc=5.00  cav=+0.35   cavity
    z=11.13  b=-5.096  bIn=-5.10  g=1.00  wLoc=5.00  cav=+0.10   cavity

**The cavity term only turns positive once `|bIn| > wLoc`.** `bIn` — the UNCLIPPED body field —
bottoms out at **-4.19** at the lowest band cell above the base plane and climbs only slowly
(-4.19 at z=5.6 to -6.27 at z=18.5, about 0.16/mm). So any wall thicker than about 4.2mm leaves
material, and any wall below it does not. **That predicts the floor appearing between 4.0 and
4.5 — which is exactly where it was measured.** Cause confirmed.

`bIn` is bounded at -4.2 because the body field is a max of three separable 2D fields, and the
side/front silhouettes carry their own lower edge. That edge sits BELOW the base cut and has
been cut away, so it should not constrain the cavity — but the unclipped reading still sees it.

**Why the arch ramp does not rescue it:** `wLoc` is still 5.00 in those rows. The ramp's guard
is `baseCut + max(wLoc, cell*2)`, which at wall 5 is 10.02, so the ramp is switched off across
the whole floor band. That guard is deliberate — it is what keeps the body's bbox floor from
lifting — so it cannot simply be removed.

**FIXED 2026-08-30 by measuring depth from the OPENING instead of from the traced silhouette:**

    if(openUnder && zm < baseCut + wall*2 && -gz/g > 0.35 && bIn < -wall*0.6)
      bIn = Math.min(bIn, -(zm - baseCut) - wall - cell);

    his car, all 153 features:   2.1 / 2.5 / 3 / 4 / 5 mm all OPEN at four stations
                                 6mm still floors at x=100 (see below)
    277 of 277

**Each of the three conditions is load-bearing and each was learned by breaking something:**
- `zm < baseCut + wall*2` — bounded and local. A term that grows without bound turns the whole
  body into cavity; that is recorded above as already tried.
- `-gz/g > 0.35` — ground-facing only, so the SIDE WALLS coming down to the base plane are left
  alone. They hold the body's lowest material, and hollowing them lifts the bbox floor.
- `bIn < -wall*0.6` — **added after a real failure.** Without it, `the rim you see at an opening
  is a clean band, one wall thick` fails: the bottom face of a side wall is ground-facing too,
  so the extension ate the rim. A rim point is still close to a real surface and a floor point
  is not, and that is exactly what this condition separates.

**Still floors at 6mm and above, at one station.** At that thickness the local gradient in the
floor band no longer points at the ground — the nearest surface is elsewhere — so `-gz/g > 0.35`
excludes the cells that would need extending. Two walls of headroom is not the issue; the normal
test is. **This is now well outside any wall anyone builds at** (Collin works at 2.1mm) and the
next attempt should replace the normal test with something that asks "is there open space
directly below this point", not widen a constant.

### BOTH ENDS, RE-CHECKED AT THE NEW RANGE — 2026-08-30
The studio's cavity changed again, so the exact build was re-measured with `isInside` on the
solid. His car, features stripped:

    wall 2.1  CLOSED  163.4 cm3   x=60 [43.1-45.1, 55.1-57.1]   x=100 [2.1-4.1, 86.1-88.1]
    wall 2.1  OPEN     90.5 cm3   x=60 [55.1-57.1]              x=100 [86.1-88.1]
    wall 5.0  OPEN    214.9 cm3   x=60 [47.1-48.1, 52.1-57.1]   x=100 [83.1-88.1]

**At 2.1mm — his actual setting — both ends are fully open and they agree.** At 5mm the backend
leaves a 1mm remnant at x=60 (47.1-48.1) where the studio now clears it. Small, one station, and
above his working range; recorded rather than chased.

**A test trap worth naming:** his profile carries `openArches: true`, so a "closed" case built
by setting only `openUnderside: False` is NOT closed — `open_under` is the OR of both spellings.
That produced a run where CLOSED and OPEN came back byte-identical and looked like the backend
ignoring the flag. Set both, always.

`test_the_studio_draws_its_cavity_from_the_unclipped_body` now pins the floor-band extension and
all three of its guards. Mutation-checked. One of its older assertions had gone stale — the
source moved from `const bIn` to `let bIn` when the extension started reassigning it — and the
test caught that itself on the first run.

### THE FRAME, so nobody loses another session to it
    GRID  px [-1.85, 201.85]   py [-1.85, 116.85]   pz [-1.85, 90.85]
    MESH  x  [-0.05, 200.02]   y  [-57.36, 57.63]   z  [4.98, 88.92]

**x and z share the frame. y DOES NOT: mesh y = py - W/2.** A probe at `py~0` samples the car's
SIDE EDGE, not the centreline, and reports "far outside" for a column that is solidly inside the
body. That cost a session. Also: rewriting the scratch copy from the shipped file wipes any
recorders already in it — re-add them in the same pass, and check the count of matched sites.

### THE BACKEND HAD IT WORSE
`hull.py` never read `openUnderside`/`openArches` at all, at any thickness. `open_the_underside()`
now extends the cavity down through the floor at all three cut sites. Charger at 4.8mm:
341.0 -> 200.0 cm3, one valid solid. The studio's open figure is 203.0 cm3 — 1.5% apart.

======================================================================
## THE PLANK ON COLLIN'S CAR — ROOT CAUSE FOUND 2026-08-30. TOP PRIORITY.
======================================================================
_Found from his own profile. It is NOT the field hollow, NOT resolution, and NOT the depth
sign. It is a 2% threshold in `bottomSkinTris` that was tuned on a different car._

### WHERE THE PLANK IS, from his drawing
His traced side outline at x=80 says material occupies **z 31.2 to 74.0**. The build returns
material at **31.2-34.9 and 71.0-72.7** — i.e. the body's BOTTOM SKIN at 31.2 and its roof skin
at 71. That bottom skin, at the station where the body sits above a wheel arch, is the slab he
sees through the arch. Ticking "leave the underside open" is supposed to remove exactly it.

### THE CAUSE — the GROUND-FACING ANGLE TEST, `bottomSkinTris` line ~1998
    if(fl && fz/fl < -0.5) down[t]=1;        // was: within 60 degrees of horizontal

A surface had to be within 60 degrees of horizontal before the underside trim would open it.
**On a traced car whose underbody SLOPES, that cutoff lands in the middle of the ceiling.**
Measured on his profile_8 at the station above a wheel arch (x=80, |y|<20, z 29-36):

    normal-z bucket   count
        -0.5           126     <- sitting EXACTLY on the boundary; about half fail by a hair
        +0.5..+0.8     216     <- the inside of the floor, correctly facing up into the cavity

The half that failed stayed as a 2.4mm floor at z=31.2 — precisely where his own drawing puts
the body's underside (his traced side outline at x=80 says material runs z 31.2 to 74.0). Seen
through the open arch from the side, that floor IS the plank.

### THE FIX: `-0.5` -> `-0.35`
    his car, ray up at x=80:   before  31.1-33.5 and 70.9-72.7   <- floor + roof
                               after            70.9-72.7        <- roof only
    every station x=20..180 now matches the SMOOTH builder: two crossings, roof skin only
    watertight on his car AND on the same car stripped of features: 0 boundary, 0 non-manifold
    277 of 277

**It cannot cause the pinholes the area gate exists to stop.** Specks are excluded by AREA, not
by this angle test, so loosening the angle grows the real ceilings without promoting a single
speck. -0.25 also works; -0.35 was taken because the extra margin buys nothing measured.

### A WRONG CAUSE I RECORDED HERE FIRST — corrected, and the correction is the lesson
The previous version of this section blamed the 2% area gate at line ~2038, on the strength of
his features shrinking one region from 2.1% to 1.2%. **That observation is true and it is not
the plank.** Going one level deeper showed the failing regions are the levelled BASE pieces at
mean z 5.8-12.7, while the slab is at z=31.2 — a different part of the model entirely. The
region actually covering the underside (89.7% of the down-facing area, mean z 63.3) PASSES the
gate and always did.

I published a root cause after one corroborating measurement instead of after a disconfirming
one. **The question that found the real answer was "which region owns the triangle at x=80,
z=31.2?" — and the answer was "none, it is not classified as down-facing at all."** Ask which
specific element shows the symptom before believing any statistic that merely points the right
way.

### WHAT WAS RULED OUT, each by measurement — do not re-check these
- **NOT the field hollow.** He runs at 2.1mm where `fieldHollow` is OFF (it switches on at
  ~2.5mm). The 2026-08-30 field fix is real but **does not touch his configuration.**
- **NOT resolution.** Forcing the field path by raising the Fine cap gets res 139 and the slab
  at x=80 is STILL THERE (31.2-34.9). Cost: 173k triangles and 22.4s against 105k and 7.5s.
  **Raising the cap does not fix this and is not worth its price here.**
- **NOT the carve-mode sign.** His 153 cuts remove 15.8 cm3 (115.8 -> 100.0); flipping the sign
  adds (154.4). Cut cuts.
- **NOT the tick being ignored.** Tick on vs off gives different meshes (85,426 vs 105,208
  triangles). The trim ran; it just declined that one ceiling on an angle test.
- **NOT the 2% area gate.** See the correction above.

### STILL WORTH KNOWING, but not urgent
His features do shrink one down-facing region from 2.1% to 1.2%, dropping it under the 2% area
gate. That region is a piece of the levelled base at z~6, not the arch ceiling, so it is not
what he was seeing — but the comment above that gate claims "the gap between the smallest
region kept and the largest speck is nineteenfold, so this is not a close call", and on his car
featureless it is 2.1% against 1.1%. **Twofold. The gate is marginal on this geometry even
though it is not the bug.** Leave it alone until something actually breaks on it.

======================================================================
## CARVE MODE — "Cut into the shape" vs "Press on the surface". HIGH PRIORITY, NOT STARTED
======================================================================
_Raised by Collin 2026-08-30 with screenshots. He asked for this to be recorded in detail and
prioritised, and to be handled AFTER the underside. It is the next thing to pick up._

`p.carveMode` picks between two carving engines, both kept deliberately:

    "field" (default)  features are prisms in the distance field, meshed WITH the body.
                       Exact depths; the cavity follows a pocket so the wall under it keeps
                       its thickness. This is "Cut into the shape".
    "stamp"            mesh the plain body, then push vertices under each outline. Much
                       faster, and the ONLY path the exact-STEP backend has ever seen.
                       This is "Press on the surface".

**His report:** cut-into "makes the model look awful", and he believes the logic is backwards —
that cut is adding material rather than removing it.

**MEASURED, and the volume does not support "backwards".** On his own profile, all 153 features
at depth -2.5:

    no features at all          115.8 cm3
    his 153 features as-is      100.0 cm3     <- 15.8 cm3 REMOVED. Cut removes.
    same features, sign flipped 154.4 cm3     <- raise adds. Sign logic is correct.

His screenshots: field 97.3 cm3 / 88,018 tris / 6494 ms, stamp 87.5 cm3 / 85,424 tris /
2499 ms. Both are below the featureless body, so **both engines remove material and neither is
inverted.** The stamp path removes MORE, which is its own question.

### QUANTIFIED 2026-08-30 — it is real, it is 13x, and it is NOT resolution
"Torn" measured as adjacent triangles whose normals disagree by more than 134 degrees, on his
own profile:

    cut into (field), his 153 features    2530 torn edges   1.99%
    press on (stamp), his 153 features     196 torn edges   0.16%
    no features at all, either mode        187 torn edges   0.15%

**Stamp with all 153 features is at baseline. Field is 13x worse.** His complaint is real and
this is the number for it.

**RESOLUTION IS NOT THE CAUSE — measured, so nobody spends a session on it:**

    res 108 (his)   2530 torn  1.99%     7 s   105k tris
    res 139         5860 torn  2.25%    67 s   174k tris
    res 165         7463 torn  2.04%   140 s   244k tris

The percentage is FLAT at about 2% however fine the grid gets; the count just tracks the
triangle count. Step 1 of the old plan below is answered and closed: raising quality makes the
model slower and no cleaner. **The "15 details are too small" warning is true and is a
different problem from the tearing.**

**WALL THICKNESS IS NOT THE CAUSE EITHER.** His pockets are 2.5mm deep into a 2.1mm wall, which
looked like the answer given the UI hint that nothing may go deeper than the frame. It is not:

    wall 2.1mm (pocket deeper than wall)  2530     wall 4mm  3447
    wall 3mm                              3249     wall 6mm  3299

### WHAT IT DOES SCALE WITH: the pockets themselves
    features present  0 -> 187    38 -> 1304    76 -> 2151    153 -> 2530
    pocket depth     -1.0 -> 1435   -1.5 -> 2016   -2.5 -> 2530

Tears scale with how many pockets there are and how deep they are, and vanish with them. **They
are at the pocket rims, not spread over the body.** That is the signature of sharp concave CSG
edges meeting a dual-contour mesher: one vertex per cell cannot represent a sharp step, so the
facets around each rim invert. Stamp does not do this because it pushes existing vertices
smoothly and never creates a sharp edge.

**NOTE: his saved profile is already `carveMode:"stamp"`.** He has switched to the clean one
himself. Every measurement taken on profile_8 before 2026-08-30 was therefore in STAMP mode —
including the plank work, which is fine, but a field-vs-stamp comparison that does not override
`carveMode` explicitly compares stamp against stamp and comes back identical. It did once.

### NEXT, revised
1. ~~Confirm the tearing is resolution~~ **ANSWERED: it is not. Closed.**
2. ~~The blue areas in his 23:19 shot are backface, an open or inverted surface~~ **WRONG, and
   he corrected it: that was the PLANK, the underbody not being opened. Fixed 2026-08-30 by the
   ground-facing angle change. Do not chase a separate backface bug; there is not one.**
3. ~~The live question is the rim inversion~~ **DONE 2026-08-30 — the rim facets are relaxed
   after meshing.** Only the vertices that actually carry an inversion are moved, toward the
   average of their neighbours, capped at half a cell so a rim cannot be rounded away. Three
   passes. Same technique the underside opening's edge already uses.

       cut into (field), his 153 features   2530 -> 465 torn   (88% of the feature tearing)
       press on (stamp), his 153 features    196 ->   4
       no features, either mode              187 ->   4        <- it cleans the baseline too
       watertight throughout: 0 boundary edges, 0 non-manifold
       the OUTSIDE does not move: bbox L 199.503 -> 199.454, W and H unchanged to 3 decimals
       277 of 277

   **COST, measured honestly: field mode goes 15.5s -> 18.0s on his car, about 16%.** Field was
   always the slow path (153 prisms in the field); the repair is not what makes it slow. The
   first cut of this rebuilt the edge map and vertex adjacency on every pass — hoisting them
   out changed nothing measurable, so the cost is the normals and the passes themselves, not
   the maps.

   **A NOTE FOR WHOEVER RUNS THE SUITE NEXT:** slice 160:200 now exceeds a 275s tool call and
   has to be split at 180. The suite itself is unchanged and still passes as one run in CI.
4. **THE DEFAULT — the trade, now with numbers. Collin's call, not mine.**
   Ten of his own features, same profile, same 2.1mm wall, measured as a fraction of each
   end's own body volume so the mesh-vs-exact difference cannot skew it:

       studio "press on the surface" (stamp)   removed 3.26%
       studio "cut into the shape"  (field)    removed 1.34%
       backend, the exact kernel                removed 1.19%

   **Field agrees with the STEP export to within 13%. Stamp over-removes by about 2.7x.** His
   profile is saved as `carveMode:"stamp"`, so the preview has been showing more material gone
   than the export actually removes — the two ends disagree about the part, which is the one
   thing this project does not tolerate quietly.

   That inverts the earlier reading of this question. Stamp looked better only because field
   was tearing at every pocket rim, and **that is fixed** (2530 -> 465 torn edges). Field is now
   both the accurate path and a clean one, which is also what Collin guessed when he said the
   default should be cutting into the model. **Still not changed here** — it costs build time
   (field is the slow path) and the decision is his, but the trade is no longer a matter of
   taste.

5. **THE 22% VOLUME GAP — split, and it is TWO separate things. 2026-08-30.**

       studio SOLID  801.01 cm3   bbox 200.1 x 115.0 x 83.9
       backend SOLID 825.20 cm3   bbox 200.0 x 115.0 x 89.0
       studio HOLLOW 110.98 cm3
       backend HOLLOW 90.54 cm3

   **(a) THE BACKEND HAS NO LEVEL-BASE CUT. AT ALL.** `grep baseCut app/hull.py` returns
   nothing. The studio clips the body flat at `baseCutZ` — 5.017 on his car — so the solid
   stands 83.9 tall. The backend's runs the full 89.0, from z=-0.00, and sampling confirms real
   material down there: 12 of 57 probe points are inside the solid at z=1.5 through 4.5.

   **FIXED 2026-08-30.** `base_cut_z()` in hull.py is a direct port of the studio's `baseCutZ`,
   constants included — 120 columns, 160 levels, 2-means seeded at the extremes, and the same
   8%-of-height separation test. The body is trimmed with a half-space below it right after the
   three silhouettes are intersected, so everything downstream (features, hollow, export) sees
   the levelled body.

       backend base_cut_z 5.0172   against the studio's baseCutZ 5.017
       backend SOLID  804.77 cm3  height 84.0   (was 825.20, height 89.0)
       studio SOLID   801.01 cm3  height 83.9
       -> the two ends now agree on the solid to 0.47%, from 3.0% and 5.1mm of height

   **The `-inf` return means NO CUT, not a cut at minus infinity.** A flat-bottomed body has one
   population of lows and nothing to level; cutting it at the mean of its own bottom face would
   shave the part for nothing. Tested both ways. The cut also refuses to empty the body: if the
   trim leaves nothing, the level was wrong and the untrimmed solid is kept with a printed note,
   rather than handing back a null shape.

   **The test is built so it can fail** — the fixture dips below its own ground line in one
   narrow column, so an unlevelled body reaches lower than a levelled one. A shape that already
   stands flat would have passed whether or not the cut ran, which is the trap that caught the
   first version of this test. Mutation-checked: disabling the cut fails it.

       73 passed, 1 skipped  |  test_cad 1 passed (4:49)  |  schema checker clean

   **(b) THE STUDIO'S VOLUME READOUT OVER-REPORTS. Cause found 2026-08-30; it is a MESH
   RESOLUTION artefact, not a geometry bug.** With the skirt gone the solids agree to 0.47%,
   but the hollow shells do not:

       SOLID    studio area  782.9 cm2  vol 801.01   backend area 792.4  vol 804.77
       HOLLOW   studio area 1084.8      vol 110.98   backend area 915.6  vol  89.73

   Solid areas agree to 1.2%, so the outer surfaces match. The hollow shells differ by **18.5%
   in AREA** and 23.7% in volume, and the wall itself is only about 5% thicker (2.27/2.35/2.15
   against 2.15/2.20/2.10 on matched rays). 1.185 x 1.056 = 1.25, which is the whole gap.

   **It is the meshed inner wall being faceted at grid resolution against an exact smooth
   offset.** The bumps add area, and area times wall is material. Confirmed by prediction: the
   gap should shrink as the grid gets finer, and it does, monotonically —

       fast    res  50   cell 4.00mm   130.76 cm3   +45.7% over the exact 89.73
       normal  res  72   cell 2.78mm   117.37 cm3   +30.8%
       fine    res 108   cell 1.85mm   110.98 cm3   +23.7%

   **WHAT THIS MEANS FOR ANYONE READING THE HEADER: the cm3 in the studio is not the amount of
   material that gets printed, and on Fast it is off by nearly half.** The STEP is right; the
   preview is high. Options, none taken: report the exact figure by asking the backend, apply a
   resolution-derived correction, or say in the UI that the figure is an estimate that tightens
   with quality. Whichever it is, **the number should stop being presented as if it were the
   part.**

   Both matter because the volume in the studio header is what someone estimates filament from,
   and neither number is currently the thing that gets printed.

======================================================================
## HANDOFF.md REWRITTEN 2026-08-30 — the old one is WRONG, delete it
======================================================================
The 2026-08-23 handoff opens with an emergency ("one file is in the wrong folder and it is
breaking CI") that has been fixed for days, and lists questions A and B as open when A is
answered and closed. A pointer document whose first section is stale is worse than none — it
sends the next session at a problem that no longer exists, which is the exact failure this file
keeps recording about its own notes.

The replacement leads with "nothing is broken, start by reading", carries the current md5s and
suite results, and separates the three things that are NOT bugs (the volume readout, the carve
default, the parked holographic view) from the things that are. Ship it over the old one.

======================================================================
## SCALE — first step of the construction build. Shipped 2026-08-30.
======================================================================
_The car keeps building. Every part of this is additive and a profile carrying neither field
behaves exactly as it always has — asserted by a test, not assumed._

    realLength   how long the real thing is, in mm. A 24m building is 24000.
    modelScale   the denominator: 200 means 1:200.

**`length` is and stays the MODEL size.** All geometry is still built from it, so nothing about
the car moves. Verified on his own profile: no scale fields -> `real_dims: None`,
`scale_mismatch: None`, dims unchanged at 200 x 115 x 89.

**A real length ON ITS OWN derives the scale** (`realLength/length`), because that is how
somebody working from a drawing thinks — "this building is 24m, make it fit". His car at
realLength 24000 reports an implied 1:120.

**A scale that contradicts the model size is REPORTED, not resolved.** Given both, they can
disagree, and then the model is not the scale it claims. `scale_mismatch` carries the model
length, the implied length, the real length and the scale — the same treatment as
`unusable_views` and `hollow_failed`. Quietly preferring one is how the ends have gone out of
step before.

**Both fields tolerate junk.** A saved profile can carry anything; `plan()` swallows a string
rather than throwing.

### Two things the contract tests caught, and both were right
- **`realLength` alone changed nothing**, so `test_every_key_the_schema_says_we_read_actually_
  changes_the_answer` failed. That was a real design gap, not a test to appease — it is why the
  field now derives the scale on its own.
- The default mutation in that test sets a key to the string `"CHANGED"`, which these fields
  deliberately swallow. They needed numeric entries in `MUTATE`; the junk guard has its own test.

### THE STUDIO SIDE — shipped 2026-08-30, so scale now works end to end
"Build it at a scale" sits under the length slider. Off by default, and when it is off **none of
this code runs at all** — which is what keeps the car exactly as it was. Give the real length in
metres and the ratio; the model size follows and is shown as you type.

    24m at 1:200 -> 120mm      90m at 1:500 -> 180mm

`S.len` remains the single source of truth for geometry — the scale control only DRIVES it, the
same way the preset buttons do, so no downstream path changed.

**Out of range, it names the ratio that WOULD fit.** Clamping to 5-600mm and saying "held at
600mm" tells you it did not work, not what would; the smallest ratio that fits is
`ceil(real / max)`, and without it somebody guesses denominators until one lands. Checked:

    24m at 1:200  -> 120mm   ok           90m at 1:100  -> 900mm   suggests 1:150 (600mm)
    120m at 1:200 -> 600mm   ok          250m at 1:200  -> 1250mm  suggests 1:417 (600mm)

**The real figure is saved on the profile, not just used and dropped.** `realLength` and
`modelScale` are written ONLY when the user asked for a scale, so an ordinary car profile
carries neither key and is byte-identical to before. Loading a profile with them re-checks the
box and refills the fields; loading one without clears it.

`x-read-by` is now `["studio","exact"]` on both keys and the checker verifies that against both
sources — it was `["exact"]` only until the UI existed, deliberately, because the claim would
otherwise have been a lie the checker catches.

    schema checker clean  |  backend 75 passed, 1 skipped  |  frontend 278 of 278

### NOT VERIFIED THIS TURN: test_cad
`tests/test_cad.py` has grown to about 290s and no longer fits in one tool call here (limit
~300s with overhead). It last ran green at **4:49 on hull.py 3d50756e**, before this change.
This change adds two keys to `plan()`'s return and reads two optional fields; it cannot reach
CAD geometry, and the fast suite covers `plan()` including the new tests. **Collin's CI has no
such limit and will run it.** Worth knowing that the level-base cut pushed this file from ~4:26
to ~4:50 — it is now the slowest thing in the repo.

======================================================================
## LANDSCAPE / CONSTRUCTION BUILD — scoping for Dylan (PM). 2026-08-30
======================================================================
_Buildings and structures, some site layout (plots, roads, services), and objects like an
entry fountain or complex sign. Input: blueprints and photos, NOT sketched in-app. Output:
3D prints AND on-screen for clients. **Terrain and grading are explicitly a LATER build.**_

### THE ENGINE ALREADY SUITS THIS. I doubted it and measured, and I was wrong.
The worry was that a dual contour on a ~1.8mm grid would round the sharp corners architecture
is made of. It does not. On a rectangular block, distance of every surface vertex from the
nearest true plane — 0.00 would be perfect:

    fast    cell 2.40mm   worst off-plane 0.06mm   mean 0.011mm
    normal  cell 1.67mm   worst off-plane 0.05mm   mean 0.013mm
    fine    cell 1.11mm   worst off-plane 0.03mm   mean 0.005mm

Invisible on a print even at the coarsest setting. **An L-shaped plan — the commonest apartment
block footprint — came through with 0 vertices inside the notch of 13,028.** Dual contouring
preserves sharp PLANAR features by design; the rim tearing fixed earlier was sharp CONCAVE CSG
edges, a different failure, and it does not apply here.

**And blueprints are a better input than the car ever had.** Plans and elevations ARE true
orthographic projections. The tracer has spent its life fighting perspective in photographs.

### WHAT ALREADY EXISTS AND CARRIES OVER
- Real-world scale calibration: click two points on the drawing, type the true distance.
- Workshop places multiple meshes with per-instance transform and scale (`wsAddMesh`, `wsAdd`).
- Hollow shell, separate bottom plate, levelled base — exactly what an architectural print needs.

### THE REAL GAPS, in the order they will bite
1. **NO PRINT-SCALE CONCEPT, and this is the big one.** Calibration makes dimensions "true to
   size", but the model length slider is `min=5 max=600` mm. A 24m building cannot be expressed.
   Architects work in NAMED scales — 1:100, 1:200, 1:500 — and the model size follows from the
   real size. Right now the user does that arithmetic in their head and the real dimensions are
   lost. Dylan needs real size in, scale chosen, model size out, and the real figure kept.
2. **Site assembly — CHECKED 2026-08-30, and it is MUCH smaller than feared.** Workshop
   already does nearly all of it:

       wsAdd / wsAddMesh / wsAddBox   place any profile, mesh or box as an instance
       pos{x,y,z}, rot{x,y,z}, scale  full 6-DOF placement plus uniform scale, per instance
       wsPZ / wsRX / wsRY / wsRZ / wsSC   NUMERIC fields, not drag-only
       wsGround + drag                 click-drag placement on the ground plane
       wsExportSTL                     "Export combined STL" — the whole assembly as one file
       wsSaveAssembly                  the arrangement persists
       per-instance colour             a complex reads far better with the buildings coloured

   **The one real gap was that there was nothing to place AGAINST. BUILT 2026-08-30.**
   A plan image now lies on the Workshop floor: choose an image, say how wide it is in real
   life, say the scale it is drawn at. Its width in the model is `real / scale` — the SAME
   arithmetic the buildings use, so a building dropped on a spot on the drawing lands at that
   spot in the model. An 80m plan at 1:200 comes out 400mm across; a 24m building at 1:200
   comes out 120mm. Neither number is guessed from the image.

   **IT IS SCENE FURNITURE, NOT A PART, and that one choice is the whole safety story.** It
   lives in `WS.planMesh` and never enters `WS.inst`, which is what all three leak paths walk:

       wsRecomputeExtent   iterates WS.inst -> the plan cannot blow up the grid or the recenter
       wsPick              iterates WS.inst -> the plan cannot be selected or dragged
       wsExportSTL         iterates WS.inst -> THE PLAN CAN NEVER REACH A PRINTED FILE

   Adding it as an instance would have been less code and wrong in three places at once. There
   is a test pinning it — `site plan: the underlay never enters WS.inst` — which reads the
   source rather than the geometry, because Workshop needs THREE.js and a DOM and cannot be
   built headlessly. The property that matters is statically checkable and a plan in an
   exported STL would be printed.

   Also: `renderOrder = -1` and `y = -0.15` so it draws first and sits a hair under the floor
   grid — parts always render on top and there is no z-fighting.

   **SHARPENED 2026-08-30, before the drawings arrive: the plan can now be ALIGNED.** As first
   shipped it was pinned centred and unrotated, and a scanned plan is neither — north does not
   match X and the origin is wherever the scan started. **You cannot place buildings onto a plan
   you cannot line up**, so it would have blocked on the first real drawing. Now: slide across,
   slide up the page, turn, and fade.

   **`rotation.order = "YXZ"` is load-bearing.** The plane is laid flat by `rotation.x = -PI/2`
   and turned by `rotation.y`. On THREE's default XYZ order the Y is applied FIRST, so the turn
   happens before the plane is flat and tips it out of the floor — the normal comes out at
   `(sin0, cos0, 0)` instead of straight up. YXZ applies the turn about world-up after the
   flattening, so it spins in place. Every control routes through one `sync()` that writes its
   own readout and re-applies, so there is no second copy of the sizing maths to drift.

   **The suite caught a real mobile bug on the way in.** A bare `<input type="file">` fails
   `mobile: every file picker can actually be opened on a phone` — iOS will not open a picker
   without a real `<label for=...>` driving it. Fixed before shipping. **278 of 278.**

   Everything else on this item was already written. **Do not rebuild placement.**
3. **Repeating facade detail.** 153 features already cost about 16s in field mode on a car. A
   facade is windows in rows and could be several hundred. The stamp-vs-field accuracy gap
   (stamp over-removes 2.7x) matters far more when the detail IS the deliverable.
4. **The volume readout over-reports** (see item 5 above). Worse in a client-facing tool where
   somebody may quote material off it.

**NOT a gap: terrain.** Correctly deferred. A hillside's top view is just the site boundary and
its side view is the skyline, so intersecting silhouettes gives a solid block up to the highest
ridge. Terrain is a heightfield and needs its own builder — do not attempt it inside the hull.

======================================================================
## ROUND OBJECTS — a lathe about the vertical axis. Built 2026-08-30.
======================================================================
_Prompted by an example fountain drawing for the roundabout centre. **A visual hull cannot
build a fountain**, and the reason is structural rather than a resolution problem._

### THE HULL GETS ROUND OBJECTS WRONG. Measured, on a fountain-shaped elevation with a
### circular plan:

    base   radius 59.5 to 60.0mm   out of round  1%   round
    stem   radius 26.4 to 35.8mm   out of round 36%   SQUARE
    bowl   radius 26.4 to 35.8mm   out of round 36%   SQUARE

36% is all but a square, which is 41%. **The hull only keeps a round object round at its widest
level**, where the plan circle is the binding constraint. Anywhere it is narrower, the
cross-section is side-width intersected with front-width — a rectangle. **No grid refinement
fixes this**; do not try raising quality at it.

### THE FIX: `makeLathe`, and it reuses what was already there
`makeRevolve` — retired from the UI but kept so old files load — already builds a watertight
surface of revolution. It turns about X, which suits a wheel; a fountain turns about vertical.
So the axes are permuted **cyclically, (y,z,x)**, whose determinant is +1, which is why the
winding `makeRevolve` already fixed stays correct and the solid stays outward-facing. Nothing
about the revolve maths was rewritten.

`revProfileFromElevation` reads the radius straight off the traced side elevation: at each
height, half the outline's horizontal span. That is exactly what an elevation of a turned object
IS, so the drawing needs no special preparation.

    same fountain elevation, through the lathe:
    tris 5376   boundary edges 0   non-manifold 0   z [0.0, 100.0], base on the floor
    base 0.00%   stem 0.00%   flange 0.00%   bowl 0.00% out of round

**A first reading said the stem was 127% out of round.** It was a sampling band straddling a
real diameter step at v=0.55, not a defect — bands kept inside a single segment of the profile
all read 0.00%. Same class of error as the corner-rounding metric earlier in this file: measure
across a feature and the feature is what you measure.

    278 of 278

### NOT DONE YET, and deliberately
- **No UI.** `shape:"lathe"` is reachable from a profile but there is no control for it. Wiring
  it needs a decision about where it sits beside "follow my drawing" and the smooth loft.
- **Detecting roundness.** Collin suggested reading "diameter"/"radius" off the drawing. **A
  circularity test on the TRACED OUTLINE is far more robust than OCR** — the app already has the
  polygon, and one of his two examples is a hand-annotated survey sheet whose text no OCR would
  read. Comparing the top outline against a best-fit circle is a few lines and cannot be fooled
  by handwriting. Text should be a hint at most, never the mechanism.

======================================================================
## OPEN ITEMS
======================================================================
**1. Bad directed edges — SOLVED. See the FINS section below.** Was 61 on profile_7;
now 0 at every wall thickness, and pinned by three tests.

**2. Rim test coverage is genuinely thinner than it was.** The old version read the mesh as
two stacked vertex copies (`vc = P.length/6`, pairing v with v+vc) — the vertex-offset
layout. On a dual-contoured mesh that arithmetic picked unrelated vertices and reported a
4.2mm rim as 111mm. Rewritten to measure the band geometrically on BOTH paths. But the old
test also measured how far the rim WANDERED in z, and that needed the rim identified as a
ring; both shells are closed so there is no boundary ring to walk. That half is not
reproduced. Flagged in the test file rather than left as a green tick over nothing.

**3. Curtis's safety gate** — `shellWallStats` exists and is tested; the UI warning is not
built.

**4. Carve — PORTED, one real bug fixed, still parked.** See the CARVE section below.
`WIP-do-not-deploy/carve-port-WIP.html` md5 **7cb474a7**. 206/210, DO NOT DEPLOY.

**5. Adaptive wall UI — CONTRADICTED BY THIS FILE. Do not act on this item.**
This entry asks for a labelled toggle. The **ADAPTIVE WALL — RETIRED** section below says
plainly "do not give it a UI", and backs it with ten geometries in which the flag saved 0.0%
at a 4mm wall and opened a thin patch in EVERY case at 8mm. The retirement is later and it is
the one carrying a measurement, so it wins. Left visible rather than deleted, because two
sessions could each read only one of them and ship opposite things. **Awaiting Collin's
confirmation, then one of the two gets removed.**

**6. Lee/Dylan/Curtis feature work** — unchanged from before.

======================================================================
## TRAPS (add to the list, these cost time this session)
======================================================================
- **A new top-level CONST is the same trap as a new top-level function.**
  `HOLLOW_WALL_CELLS` threw ReferenceError until added to the test PRELUDE. It presents as a
  pile of unrelated geometry failures, not as "you forgot to list it."
- **`grabConst` matches `^const NAME=` with NO SPACES.** Writing `const X = 1.45;` makes
  extraction fail silently. Match the codebase style: `const X=1.45;`.
- **Do not splice the test file by searching for the next `t(`.** Doing that ate a block
  opener and the shared `dent` / `blockProfile` helpers, and surfaced only as a syntax error
  hundreds of lines away. The file was rebuilt from the pristine repo copy and every edit
  re-applied with brace-aware boundaries. Use a brace matcher, or edit by unique anchor.
- The test runner now awaits async tests (PENDING[] + Promise.all before the report). Before
  that an async test passed the moment it returned a Promise.
- Solid FRACTION alone is not enough — it hid the plank for sessions. The ASCII
  cross-section against a SOLID reference is what actually shows it.


======================================================================
## CARVE — GREEN AND SHIPPED. 225/225.
======================================================================
Seven bugs found and fixed. All six views carve, symmetrically, at the depth drawn.

### The last one, and the hardest to see: `depth < 0` rejected the face itself
`side` and `rear` removed 0.000 cm3 while `sideR`, `top`, `bottom`, `front` all worked.
outerAt refines its crossing by interpolation, so on a flank sitting exactly at the field's
own y=0 it returns something like 1e-16 instead of a clean zero — and every sample ON that
surface came out at -1e-16 and was discarded. **1694 of `side`'s 2350 samples thrown away at
one line**, leaving too few to change the mesh at all, even at a 12mm depth. The right flank
never hit it because its face is at y=W, where interpolation lands cleanly inside the domain.
Fix: half a cell of tolerance. Anything closer than that to the face IS the face, and a hair
in front returns zero depth rather than a rejection.
Found by counting rejections at every gate, per view: the gates were innocent (bbox and
footprint rejected identically across views) but the march rejected 86% for `side` against
37% for `sideR`. Three measurements, no guessing. NOTE: my own logger printed those depths as
"0" because it rounded to 2 decimals — the value was never actually zero.

    view      before -> after (cm3 removed from a test block)
    side      0.000  -> 0.578        sideR   0.550 -> 0.550
    rear      0.000  -> 0.330        front   0.330 -> 0.330
    top       0.841  -> 0.841        bottom  0.840 -> 0.840

### THE VOLUME RISE IS CORRECT — and the old behaviour was the bug
A carved shell holding MORE material looked wrong for several sessions. It is right, and the
reason matters. Straight down through a 3mm pocket in a 5mm-wall box:

    shipped   outer skin 57.5, cavity roof 55.0  -> 2.5mm of wall under the pocket
    carve     outer skin 57.0, cavity roof 51.9  -> 5.1mm of wall under the pocket

The vertex-push path pushes the skin in and leaves the cavity where it was, so the wall under
a pocket is thinner by the pocket's depth — a weak spot exactly where a detail was drawn.
Nothing catches it: the mesh is watertight, and shellWallStats reports a 5.00mm MEDIAN in
both builds because the thin patch is a small part of a big surface. The field carve pushes
the cavity down too, keeps a uniform 5.1mm wall, and the pocket's own lining is the extra
material. **A shell that gets LIGHTER when you carve it has taken the difference out of its
wall.** Pinned by three `carved shell:` tests.
This is Curtis's safety issue, not a cosmetic one.

### Measured state
    pocket depth   4.00 / 6.00mm at res 44, 2.01 / 4.01 / 6.01 at res 80    (exact)
    raise height   2.000 / 4.002 / 6.004mm                                   (exact)
    saddle test    3.00mm on BOTH a 60mm roof and a 21mm floor               (exact)
                   the ray-cast path cuts both at 0.90mm on the same 3mm ask
    wall under a pocket   5.1mm on a 5mm ask (ray-cast path: 2.5mm)
    featureless    bit-identical to the previous build: 45,316 tris, 300.6 cm3
    build time     ~20s on profile_7 with 153 features (3.4s featureless)

### Still open
- **Build time.** ~6x on a heavily-featured model. Accepted for now by the user's decision.
  The cost is the per-sample march; bisection already took it from 68M body-field evaluations
  to 14M, and the next lever is caching outerAt per (line, axis) more aggressively.
- **Sub-cell features.** A 2mm badge on a 2.86mm grid builds 9.29mm proud, converging to
  5.78mm at 1.43mm cells. Inherent to voxel meshing. Worth a user warning when a feature is
  narrower than the grid.

======================================================================
## CARVING FROM ANY ANGLE — `p.extraViews`. The bridge to photographs.
======================================================================
The engine already carved the intersection of what the outlines allow: material only where a
point lands inside side AND top AND front. **Nothing in that rule needed the views to be
axis-aligned.** `p.extraViews` accepts silhouettes from arbitrary directions and folds them
into the same max().

    p.extraViews = [ { dir:[x,y,z], up:[x,y,z] (optional), poly:[[u,v],...] }, ... ]
    poly is in MILLIMETRES about the object's centre, in that view's own image plane.

Empty or absent, nothing changes — existing models take exactly the path they always did
(verified: profile_7 identical at every wall thickness).

### Why this is the photo path
Current image-to-3D pipelines (InstantMesh, Unique3D, Wonder3D) work by generating several
consistent ORTHOGRAPHIC views of an object and reconstructing from those. That intermediate
product is precisely this input format. Three axis views is a person tracing; N arbitrary
views is a camera, or a model that imagined them. The ML piece is likely to be a commodity
API; the printable-solid guarantee is not.

### The test that proves the projection maths
A sphere is a circle from EVERY direction, so the right answer is known in closed form and
every view is the same outline. Three orthogonal views of a sphere do NOT give a sphere —
they give the intersection of three cylinders, 8(2-sqrt2)r^3, about 12% too fat. Adding views
must shrink it monotonically toward 4/3 pi r^3 and never past it:

    true sphere                  268.1 cm3
    three-cylinder (theory)      299.9 cm3
      0 extra views              298.6 cm3   (+11.4%)   <- matches theory
      4 extra views              277.0 cm3   (+3.3%)
     10 extra views              269.9 cm3   (+0.7%)
     26 extra views              267.5 cm3   (-0.2%)
     60 extra views              266.8 cm3   (-0.5%)
Watertight at every count. One number checks the whole projection: a wrong axis frame would
flatten the wrong direction, and a sign error would make the intersection grow.

### KNOWN LIMIT — a visual hull cannot see concavities
This is architectural, not a bug to fix. A silhouette says where an object CANNOT be, so
carving recovers an upper bound. A dip that never appears on any silhouette is never removed:
a cup's bowl, or the gap between a bent arm and a torso. More views tighten the bound but
never break it. The eventual answer is hull as the base solid plus predicted normals/depth to
push concavities in — which is roughly what the good ML pipelines already do internally.

### A DETAIL TOO SMALL FOR THE GRID — now reported, not silently mis-built
`makeVisualHull` returns `tooSmall: [{name, span, cell}]` for any feature narrower than one
and a half cells, and the warning banner says so. On a 200mm body at 2.86mm cells, asking for
a 6mm-tall badge:

    20mm wide -> 6.00mm proud   correct
    10mm wide -> 6.00mm proud   correct
     4mm wide -> 6.00mm proud   correct
     2mm wide -> 9.29mm proud   WRONG, and with no indication
     1mm wide -> 0.15mm proud   effectively gone

**There is no setting that fixes this**, which is what makes reporting the only honest option.
Two wrong assumptions, both caught by tests written to check them:
  - Raising `hullRes` does not help. Resolution is CAPPED AT 80, so a 2mm detail on a 200mm
    body is unresolvable at any value the app allows.
  - Shrinking the model does not help either. The grid divides the model, so the cell shrinks
    with it and the ratio is unchanged (0.64mm span against a 0.57mm cell).
The remedies are a bigger detail or a smaller model — both the person's call, and they can
only make it if they are told.

### Also known, for when this meets real photographs
- **A photo has no scale.** Reconstruction from images is shape-only; real dimensions need a
  reference object, camera metadata, or the person typing a number. Design it in early.
- **Perspective is now implemented.** Add `from:[x,y,z]` to a view and it becomes a real
  camera: the outline is a CONE from the lens rather than a slab of parallel lines, and
  `poly` is then in normalised image coordinates — (pixel - centre) / focal length, which is
  what a calibrated camera gives you.

  Two details that are easy to get wrong and are both pinned by tests:
  **The silhouette of a sphere is the TANGENT cone, not r/D.** A sphere of radius r at
  distance D projects to an image circle of tan(asin(r/D)) = r/sqrt(D^2-r^2), always larger
  than the naive r/D. Measured at D=120mm: the correct radius carves 269.0 cm3 against a true
  sphere of 268.1 (+0.3%); the naive radius carves 230.3 cm3 (-14.1%). Anyone generating
  synthetic silhouettes for testing needs the tangent form.
  **Image distance must be scaled back to millimetres** (multiply by depth along the lens
  axis) before it joins the same max() as the axis views, or a distant camera contributes a
  field an order of magnitude too shallow and the isosurface lands in the wrong place.

  Sanity: a lens 20m away reproduces the orthographic carve to 0.00 cm3, which is the check
  that ties the new path back to the one already trusted. Material behind the lens is
  rejected explicitly — a negative depth flips the sign of the divide, so without that check
  a camera inside the model would carve a mirror image out of its back.
- **Cost: each extra view's outline is sampled into a distance table once**, exactly as the
  three axis views already were, then interpolated. Without that, every grid sample ran sdPoly
  over every view's polygon — 48 vertices x N views x a few hundred thousand samples.

      views     before    after
        0        1.7s      0.9s
       10        4.4s      1.3s
       26        9.7s      1.9s
       60       21.5s      3.2s      <- 6.8x
  Answers unchanged to within 0.1 cm3 (the sphere still converges 298.6 -> 267.5 against a
  true 268.1), and perspective is unaffected: tangent silhouettes still land within 0.3%, the
  naive r/D still under-carves by exactly 14.1%, and a 20m lens still reproduces the
  orthographic answer to 0.00 cm3.
  This is what makes reconstruction from a realistic number of photographs practical — 21
  seconds for 60 views was the difference between usable and not.

======================================================================
## ADAPTIVE WALL — RETIRED. Do not give it a UI.
======================================================================
The flag `p.adaptiveWall` is still honoured so an old saved file loads unchanged, but it is
off by default and deliberately not offered in the interface.

### The measurement that settled it — ten geometries, heights 20/26/40/60/90mm
    wall 4mm  — saved 0.0% in EVERY case. It never acted at all.
    wall 8mm  — saved 1.6-4.3%, and opened a thin patch in EVERY case, down to 0.00mm.
Not one clean win. That is not a trade between material and strength, it is a few percent of
filament for a hole in the wall.

And the case it existed for is already handled: field hollow leaves a section too thin for two
walls SOLID by construction, which is the right answer for a rib. On a 26mm slab the centre
column measures identical with the flag on or off — it was not even delivering its own
purpose, only thinning corners on the way past.

### One real bug fixed on the way, and it must stay fixed
`reach()` marches for the far side of a section and used to return its own march limit when it
did not find one, commented as making "thick" the safe default. **Exactly backwards.** The
caller adds two opposing reaches and thins when the sum is small, so a small stand-in for an
unknown makes a THICK section read thin. A point 2.5mm under the roof of a 90mm body reported
11.25mm to the far side instead of 87.5, and the wall was cut from 8mm to 5mm on a body with
nothing thin about it anywhere. It now returns Infinity — the honest answer for "further than
I looked" — and a `adaptive wall:` test pins that a 90mm body keeps its full wall.

======================================================================
## A CAVITY THAT CANNOT OPEN NOW CLOSES — fixed
======================================================================
### I had this recorded backwards, and re-reading the data was the fix
It was written up as "a cavity too narrow leaves a MATERIAL sliver". Reading the runs
properly on a 200mm slab, 22mm tall, 8mm wall:

    MAT 8.35   MAT 82.82   MAT 8.35   |   AIR 0.24   AIR 0.24

That is an 82.8mm SOLID core with a 0.24mm sliver of AIR down each side. The cavity did not
leave a sliver — **the cavity collapsed into slivers**. Worse than being solid in two ways:
the part reported itself hollow while being a solid block, and the wall safety gate measured
across a sliver and called it a 0.28mm wall — a false alarm on a part with nothing wrong.

### The fix
An air cell with material on BOTH sides along any axis is a sliver, not a cavity, and is
filled. Bilateral by design — the same distinction the adaptive wall got wrong by testing only
the nearest side. A real cavity is at least two cells across, so its interior cells have air
neighbours and survive.

    slab 20mm (4mm cavity)   0.68mm slivers, solid core  ->  fully SOLID (right for a rib)
    slab 22mm (6mm cavity)   0.24mm slivers, solid core  ->  9.6mm walls, cavity OPENS
    slab 26mm and up                              clean  ->  unchanged
False alarm on the 22mm slab: 0.28mm -> 4.70mm. profile_7 gains 3.4% material (309.5 -> 320.0
cm3), which is slivers being closed. All existing models byte-identical.

### THE END-CAP ARTEFACT — a knife edge. Diagnosed, four fixes rejected, left alone.
**CORRECTION: an earlier version of this section said the body field's gradient COLLAPSES on
an interior plateau. That was wrong.** It was written from reasoning rather than measurement,
and three attempts were made against it before the gradient was actually printed. It is ~1.0
throughout. Measuring first would have saved a session.

### What it really is
`dist` is `b` divided by a SAMPLED gradient, so it carries a few percent of noise. Where a
section is barely one wall deep, that noise decides material or cavity. Walking in along the
length of a boxy end cap at res 52:

    i=5   b=-5.38  |grad|=1.001  dist=-5.38  -(dist+w)=-2.62  material
    i=6   b=-7.70  |grad|=0.901  dist=-8.55  -(dist+w)=+0.55  CAVITY   <-- one cell
    i=7   b=-7.70  |grad|=1.000  dist=-7.70  -(dist+w)=-0.30  material

The field bottoms out at 7.70mm against an 8mm wall, so the section should be solid outright.
A 10% wobble in |grad| flips that one cell and the mesher puts a surface through it: an 8mm
end cap builds as 7.07mm + 0.82mm gap + 2.32mm.
It looks like grid ALIGNMENT (fires at 52 and 54 stations, clean at 46/48/50/60/72) because
alignment decides whether any cell lands near enough to the edge for noise to matter. That is
why nothing based on SIZE ever found it.

### Four fixes measured and rejected
  1. Widening the sliver fill from one cell to two — reaches it, but closes a 6mm cavity that
     was building correctly and opens a 2mm gap in a clean 10mm one.
  2. Filling air cells trapped between material and the outside — never fires; the spike is
     not a cavity cell.
  3. Clamping the inner term below `deep` — never runs (`deep` is -3*wall, the plateau is
     shallower). And blanket `min(-dist,-b)` makes EVERY test body solid.
  4. "Where the raw and normalised readings disagree about which side of the wall a cell is
     on, believe the raw field" — **cuts the wall under a carved pocket from 5.11mm to 3.54mm**,
     six test failures including the safety property this engine exists for. Under a pocket the
     gradient legitimately runs ~0.6 and the normalised reading is the correct one there.
     Restricting to near-unity gradients rescues three of four resolutions and leaves station
     54; tightening the band further is fitting to a fixture.

Note also that attempts 3 and 4 initially used `max` where the logic needed `min`, so they
produced byte-identical output — the same "identical output means the path did not run" trap
recorded elsewhere in this file, hit twice in one session.

### Where a real fix would start
Separate sampling noise from real geometry, rather than guessing a gradient band. The
distinction that matters: a 10% departure from unity on an otherwise flat field is noise; a 40%
departure under a carved pocket is the surface genuinely being close, and normalisation is
doing its job there. Something that measures the field's local consistency — say, comparing
the gradient against its own neighbours — would tell those apart. The artefact is 0.64mm on
one alignment, so this is worth doing properly or not at all.

======================================================================
## STEP EXPORT — FIXED. Backend now builds pockets and raises.
======================================================================
### In LEE3D-Backend-A already (confirmed against Collin's zip 2026-08-16)
    app/hull.py        md5 56b0261d
    app/main.py        md5 5a29638a
    tests/test_hull.py md5 663c7e56   <- UPDATED, see the kernel-test note below
Backend tests: **43 passed, 5 skipped** with the CI's own invocation and dependencies. Two pre-existing failures are a missing `pydantic` in this
container, not the change — they import app/schemas.py and never reach the new code.

### What was wrong
`hull.py` applied ONLY through-cuts and bucketed everything else as `surface_only`, with a
comment saying "dishes/bosses: the browser already does these". That was true when written and
stopped being true when the studio moved detail work into the distance field — a pocket became
real geometry cut to an exact depth. **On profile_7 the backend built 0 of 153 features**, so a
STEP export was a smooth body with no detail and no error. Same silent-disagreement shape as
the old sepBottom/hullHollow bug, and it got worse every time the browser improved.

### What now happens
`plan()` returns four buckets instead of two: `through_cuts`, `pockets`, `raises`,
`surface_only`. Only the last is skipped, and it is now genuinely unbuildable — a mask or text
label with NO depth, which has no solid meaning. On profile_7: **152 pockets built, 0 skipped.**

`build_solid()` cuts finite-depth pockets and fuses raises: extrude the footprint, intersect
with a slab `depth` deep measured from the face the feature enters, then cut or union. No grid,
so no minimum feature size and no knife edge — **this path is now better than the browser's**,
which is what an exact build should be.

Entry direction is per view (`NEAR_MAX`), because which END of an axis a feature starts from
decides where a pocket's floor lands. It does not matter for a through-cut, which is why it
was never wrong before and had to be got right now.

### Communicating properly — the part that lets the studio tell the truth
`?plan_only=true` now returns `pockets`, `raises`, `features_built`, `features_skipped` and a
note that describes what was actually done. Export responses carry
`X-LEE3D-Pockets`, `X-LEE3D-Raises` and `X-LEE3D-Skipped` alongside the existing
`X-LEE3D-Through-Cuts`, so the studio can say "this STEP has your 152 pockets in it" — or, if
something ever cannot be built, say THAT instead of shipping it silently.

### One discrepancy explained rather than left hanging
The studio counts 153 features on profile_7 and the backend 152. Feature 62 is a 3-point
polygon whose first and last points are identical — a LINE, not a triangle. It carves nothing
either way so the two builds agree in shape, but they count it differently. Pinned by a test,
because an unexplained 153-vs-152 is exactly the kind of thing that hides a real one.

### One boolean, not a hundred and fifty
Each `cut()` is a full CSG operation, and a real car carries 150+ pockets. Done one at a time
that is 150 rebuilds of the whole solid, each more expensive than the last as the shape gets
more complicated. All pocket tools are now built first, fused into one compound, and cut ONCE;
raises are fused the same way. A tool that fails to build or fuse is reported on its own and
skipped, so one bad outline still cannot take the model with it.

### A divergence I CREATED, caught before it shipped
`p.extraViews` — carving from silhouettes at any angle, the groundwork for building from
photographs — went into the studio a few sessions ago. The exact build intersects the three
axis outlines only, so a model using extra views would come out **fatter** here: every extra
view removes material, and the ones this end cannot use remove none.
It is reported, not ignored: `unusable_views` in the plan, `X-LEE3D-Unusable-Views` on the
export, and a note that says the result will be fatter than the preview. Exactly the same bug
class as the missing pockets, found the same day by asking what else the two ends now disagree
about. **Ask that question whenever the studio gains a geometry feature.**

### NOT verifiable here — but now CHECKED AUTOMATICALLY on the full image
CadQuery is not pip-installable and too heavy for this container, so the pocket geometry
cannot be run here. Everything on the `plan()` side is verified and runs everywhere.

**The gap that mattered:** the only kernel-gated test asserted `solid.solids().vals()` — that
a solid exists. That would pass with every pocket on the wrong face at the wrong depth. So the
one thing guarding the new geometry was checking almost nothing.

Four tests now cover it, skipped here and live wherever CadQuery is present:
  - **a pocket removes material and a raise adds it** — catches a raise being cut instead of
    fused, or a slab intersection that misses
  - **a pocket is the depth it was drawn** — a 5mm pocket over a 30x18mm footprint must remove
    about 2700 cubic mm; a depth bug shows up as the wrong slab thickness
  - **a pocket lands on the face it was drawn on** — invisible to a volume check, because a
    pocket on the wrong face removes exactly the same amount. Compares envelopes instead
  - **24 pockets still build** — exercises the fused-tool path that replaced 150 separate cuts

**Still worth watching by hand the first time it runs on Render:** how long an export of a
real 150-pocket car takes. The booleans are batched now, but that is a lot of CSG and nobody
has timed it.
======================================================================
## BACKEND CI WAS RED — `No module named 'app'`. Fixed with a root conftest.py
======================================================================
    conftest.py   md5 75d923b5   <- NEW FILE, repo root (not in tests/)

### What was wrong
There is no `conftest.py`, `pytest.ini`, `setup.cfg` or `pyproject.toml` anywhere in the repo,
so nothing puts the repo root on `sys.path`. Bare `pytest` only adds the test file's own
directory, so `from app import hull` cannot resolve and collection dies before a single test
runs — taking `test_pdf_geometry.py` with it, which nobody had touched.

### Why I did not catch it
**I ran `python3 -m pytest`; CI runs bare `pytest`.** The `-m` form puts the current directory
on `sys.path` and the bare binary does not, so the same tests pass one way and fail the other.
That is entirely on me: the fix is to run the command CI runs, not a convenient equivalent.
It also means this was NOT caused by the pocket work — it would have failed on any push.

### The fix
A `conftest.py` at the repo root. pytest imports the rootdir conftest before collecting and,
in the default import mode, puts its directory on `sys.path` — so merely existing is enough.
It also inserts the path explicitly, for anyone running from another directory.

### Verified with CI's exact sequence, every dependency installed
    python -c "import app.main"    -> app imports OK
    pytest -q                      -> 43 passed, 1 skipped
Run with cwd deliberately removed from `sys.path`, with everything `requirements.txt` pins
present. The one skip is the OpenCascade test, which self-skips because CadQuery is not
pip-installable — that is by design and is what lets the API boot on the light image.

### What this un-hid: an entire test module that had never run
Collection was dying before ANY test, so `tests/test_pdf_geometry.py` had never executed in CI
— seven tests covering the PDF import path, silently absent. `pymupdf` is pinned in
requirements.txt, so CI does install it and those tests will now run for real. I installed it
here and ran them before letting the deploy find out: **all 7 pass.** Nothing was hiding.
The count going 22 -> 43 is not new work; it is tests that were always there finally being
collected.


======================================================================
## PER-FACE WALL THICKNESS — now honoured by the exact builder. FIXED.
======================================================================
The studio has offered **"Different thickness per face"** for a long time and the exact
builder ignored it: it read `wallThickness` and nothing else. Asking for a 16mm floor with 6mm
walls built a 6mm floor, silently, in the DEFAULT mode. The smooth builder honoured it all
along, so the same model came out two different ways depending on which mode you were in.

It matters because it is the load-bearing control — a thick floor to bolt through with thin
walls elsewhere. The wall safety gate could not catch it either: a uniform 6mm wall is not
THIN, it is exactly what was asked on two of the three faces, and the floor is simply not what
the person set.

### The fix
The gradient of the body field IS the surface normal, and it is already computed where the
wall is applied (`dist = b/g`). So `wallAt([gx/g, gy/g, gz/g], WSPEC)` gives the wall for that
point directly — one blend, no extra sampling. `wallAt` weights roof/side/floor by how much
the normal points up, sideways and down, so thickness turns smoothly through a corner instead
of stepping, and the shell stays closed.

    floor 16mm, roof/side 6mm   ->  floor builds 16.00mm, roof 6.00mm     (was 6.00 / 6.00)
    thickening roof / side / floor each adds material; none is a no-op any more
    all watertight, including all three faces different (14 / 8 / 20)

**Guarded so a plain model is untouched:** `WSPEC` is only consulted when the three values
actually differ, and profile_7 at every wall thickness is byte-identical to before.
`HOLLOW_WALL_CELLS` and the cavity fill now use the THINNEST face — if the grid cannot hold
that one the shell would eat itself there, however comfortable the others are.

### A fixture trap worth knowing
My first test used a 2mm wall and showed no change at all, which looked like the fix had
failed. A 2mm wall on that body fails the grid adequacy gate and falls back to the
vertex-offset path, which does not do per-face — so the fixture was testing nothing. **Any
test of field-hollow behaviour needs a wall the grid can actually hold.** Written into the
test file beside the fixture.

### The backend now matches — the last known divergence is closed
`solid.shell()` cannot vary its thickness, so the cavity is BUILT rather than offset. Which is
the carving principle one level in: the body is the intersection of three extruded outlines, so
the cavity is those same outlines each pulled inward by the wall belonging to the surfaces they
create. Cut one from the other and the shell is whatever lies between.

**Collin's framing, and it is the right one: label every outline point by which axis it faces.**
A point on the side outline whose normal points up is ROOF; the same outline's normal pointing
along the length is a nose or tail, which counts as SIDE. `lift_normal()` does exactly that —
XZ gives (nx, 0, nz), XY gives (nx, ny, 0), YZ gives (0, ny, nz) — and that is what turns a 2D
outline into 3D face information.

The polygon maths lives in plain Python **specifically so it can be tested without a CAD
kernel**, since it is the part that can be got wrong; everything OpenCascade touches is kept
trivial. Six tests cover it, all running in CI:
    a 100x60 outline, 16mm floor and 6mm elsewhere -> bottom edge rises 16, everything else 6
    a 45-degree stretch blends between the two, so a corner has no seam
    either winding gives the same cavity
    a degenerate outline does not produce runaway corners
A uniform model still takes the plain `shell()` path, and per-face failure falls back to a
uniform shell rather than returning a lump.

### Two sign traps, both caught by tests rather than by reading
1. **The wall is chosen by the SURFACE normal, not the direction of travel.** An edge along the
   bottom moves UP to make the cavity, but the surface it creates faces DOWN and is the floor.
   Getting it backwards silently swaps a thick floor for a thick roof — precisely the mistake
   this feature exists to prevent.
2. **`poly_area()` returns a magnitude**, because every other caller wants a size. Using it to
   detect winding made a clockwise outline offset OUTWARD, and nothing guarantees the winding
   of an outline somebody traced. The signed area is now computed locally.

======================================================================
## BUILD QUALITY — `p.hullQuality`. The way out of "too small to build".
======================================================================
    fast    request x0.7, cap 56
    normal  request x1.0, cap 80     <- the default, and exactly today's build
    fine    request x1.5, cap 120

**It scales the resolution REQUEST as well as the cap.** Scaling the cap alone would do
nothing for most models: profile_7 asks for 72 and is capped at 80, so a higher cap leaves it
exactly where it was. This is the detail that makes the setting work at all.

### What it costs and what it buys, on profile_7 (200mm body)
    fast      18,732 tris     3.3s
    normal    43,768 tris    10.9s     (identical to an unset build)
    fine     103,042 tris    31.0s
Roughly cubic, which is why this is three named steps and not an open slider — the ceiling on
a phone is memory, not patience.

### The point of it: a 2mm badge on a 200mm car
    Normal   9.29mm proud of a 6mm ask   WRONG, and unbuildable at any previous setting
    Fine     5.86mm proud                correct
The too-small report now carries `fixedBy`, and the warning says which step would build it.
Where NO step is enough (a 0.75mm badge) it says that instead, rather than sending someone
round a loop following advice that changes nothing.

Shown in both shape modes — unlike Edge crispness and How details are cut, the grid matters
whichever way the body is built.

======================================================================
## p.carveMode — BOTH ENGINES SELECTABLE. This is how the winner gets picked.
======================================================================
    p.carveMode = "field"   (default, and what an unset value means)
    p.carveMode = "stamp"   the original vertex-push path

Neither is going away. Selecting one silences the other — running both builds every feature
twice, which this project shipped once (a 2mm badge stood 4.40mm proud).

### The trade, measured on the real 153-feature model
    field   14.9s   wall p10 3.87mm   median 4.23mm   309.5 cm3
    stamp    5.6s   wall p10 2.21mm   median 3.89mm   257.0 cm3
(wall asked for: 4.2mm. Both watertight, boundary 0, non-manifold 0.)

### And on a 5mm-wall box with a 3mm pocket
    field   pocket 3.00mm   wall under it 5.11mm
    stamp   pocket 2.50mm   wall under it 2.50mm
The stamp path halves the wall exactly under the detail. That is the safety issue, and the
reason field is the default — but stamp is ~3x faster and is the only path the exact-STEP
backend has ever seen, so it stays reachable.

**Pick the winner on real parts** (Lee's frames, Curtis's load-bearing pieces), not on
synthetic cases. Seven `carve mode:` tests keep both honest.

### In the UI — "How details are cut", under Shape style
    Cut into the shape   = field    (default for new models)
    Press on the surface = stamp    (default when re-opening an older saved file)
Placed with Edge crispness rather than as a third button beside Smooth / Follow my drawing,
because that row picks how the BODY is built and the two choices COMBINE. It is also only
shown in Follow my drawing: `makeVisualHull` — where the carved-field engine lives — is
reached only when `mode==="projection"` (line ~1182), so Smooth mode has no field to cut and
always presses. Offering the choice there would be offering something that does nothing.
An older saved file (one with no `carveMode` recorded) opens on **stamp** deliberately: it was
built by that engine, so defaulting it to field would quietly reshape an existing part.

======================================================================
## NaN IN THE MESH — found and fixed. Worth knowing how it hid.
======================================================================
The shipped 158ee1ed build emitted **1,488 NaN coordinates** on any model with a RAISE. A
mesh with NaN in it is a file no slicer can open, and NOTHING in the suite noticed: a NaN
vertex still counts as a vertex, the edge bookkeeping still balances, and watertight,
non-manifold and volume checks all pass.

**Cause:** `look` clamped its table coordinates only when asked to GROW. Without that flag a
sample from the padding ring kept a negative index, `T.d[-3]` came back undefined, and
undefined arithmetic is NaN — 8,644 poisoned field nodes flowing into vertex coordinates.
**Why raises only:** a raise enlarges PAD to make room for the boss, pushing sampling further
outside the tables than a plain body ever goes.
**Fix:** clamp always. With grow, `outside` has already recorded how far out the point was;
without it, the clamped edge value is exactly what a footprint expects.

Now pinned by `carve mode: every coordinate the mesher emits is a number`, across both
engines and plain/pocket/raise. **Any future mesh check should test for non-finite
coordinates explicitly** — no other invariant catches it.

### Minor, known, not fixed
A pocket rim can place ~4 vertices about 0.5mm above the plain body's envelope, where the
pocket wall meets the roof. Cosmetic; bounded by a test at 1.0mm. The field raise also leaves
~94 zero-area triangles (harmless to slicers, but they should be dropped eventually).

======================================================================
## CURTIS'S WALL SAFETY GATE — detection built and tested. UI still to wire.
======================================================================
`shellWallStats(positions, indices, {wall, samples})` now returns `worstPatch`:
    { min: 2.50, n: 71, at: [61, 0, 55] }   or null when the shell is fine

### Why a percentile was never going to do it
On a 5mm-wall box with one 3mm pocket, the vertex-push carve leaves 2.5mm of wall under the
pocket — and the MEDIAN still reads 5.00mm, because the thin patch is a small share of a big
surface. `min` is no better: it is one reading, so it swings with the sample count (4.91mm at
300 samples, 3.76mm at 2000, on a shell that is genuinely fine).
So the gate clusters under-spec readings by proximity and reports the worst REGION with its
position. A lone reading is noise — a ray grazing a fold — so a cluster needs at least three.

### Measured
    HEALTHY, all clear (no false positives):
      wall 5, wall 9, wall 3, open bottom, solid
    FLAGGED:
      5mm box + 3mm pocket, stamp carve -> 2.50mm over 71 readings at (61, 0, 55)
      5mm box + 3mm pocket, field carve -> clear   <- the reason field is the default
      profile_7, field carve, 4.2mm ask  -> 0.55mm over 4 readings at (40,-55,38)
      profile_7, stamp carve, 4.2mm ask  -> 1.04mm over 10 readings at (103,-40,72)

**profile_7 has genuinely unprintable spots in BOTH engines** — 0.55mm and 1.04mm against a
4.2mm request. That is a real finding about a real model, not a synthetic case, and it is what
the gate exists to surface. Those are at the extremities (a wheel arch lip and a corner) where
the traced outline pinches.

### The UI — BUILT
An amber banner under the readout, hidden unless there is something to say (a warning that is
always showing stops being read). It uses the app's existing `--warn` colour and the same
border treatment as the SOLID SHAPE stamp, rather than a new visual language.
Wording aims at the decision, not the statistic:
    "Thin wall: 0.6mm where you asked for 4.2mm (13%). This spot may snap when printed or
     handled."   [Show me]
**Show me** puts the thin spot in the middle of the screen — a warning that says a wall is
thin *somewhere* is half an answer on a model with a hundred surfaces. The position is stored
in MESH coordinates and converted when the button is pressed, so it cannot go stale when the
model is rebuilt.
Suppressed on solid bodies (no wall to be thin) and mid-drag (`prof.hullFast`), where the mesh
is provisional and a flickering warning is worse than none. The whole block is wrapped in
try/catch: a warning must never be the thing that breaks a build.
Four `wall gate:` tests cover false positives across five healthy shells, detection and
location of a real patch, that the median would have missed it, and that field beats stamp.
COLLIN: this is the one piece I cannot verify myself — it needs eyes on the live app.

======================================================================
## MESH SOUNDNESS — "watertight" was never enough
======================================================================
A mesh can have every edge shared by exactly two faces and still be unfit to print. Three
distinct defects shipped in this project, and NONE was caught by boundary/non-manifold counts:
  - **1,488 NaN coordinates** (a NaN vertex still balances every edge count)
  - **94 zero-area faces**, from a dual contour putting two cells' vertices on one point
  - and the first fix for those — welding blindly — **merged the outer skin into the inner
    wall** on a thin shell and made 8 non-manifold edges. The fin problem wearing a hat.

### The weld, and why it is edge-scoped
Two vertices at the same point are only welded when they **already share a triangle edge**.
That proves they are neighbours on ONE sheet, which is exactly the zero-area case. Two sheets
that merely touch — an outer skin and an inner wall pinching on a thin section — share no
edge and are left alone. `dedupeVerts` gained an `index` map (old vertex -> welded vertex)
alongside its existing fields, so point-cloud export is untouched.
Result: zero-area faces 94 -> 0, watertight at wall 1.5 / 2.5 / 5 / 9 and on solid, thin,
thick, open-bottom and featured bodies.

### TWO FIXES TRIED AND REVERTED — do not re-attempt without reading this
1. **Clamping dual-contour vertices to their own cell.** It removes a 0.47mm bump at a pocket
   rim exactly (the bump IS the quarter-cell of slack: 0.469mm predicted, 0.47mm measured).
   But it snaps vertices onto shared cell edges and produced non-manifold edges elsewhere —
   14 on a traced body, 7 on a thick shell, 4 edges wound the same way twice. **The
   quarter-cell slack is load-bearing.** A cosmetic bump beats a broken solid.
2. **Dropping collinear faces.** Three distinct points on a line span no area, so they look
   free to delete. Removing them opened **38 boundary edges** — those faces still carry edges
   in the mesh graph. A slicer copes with a zero-area face; it does not cope with a hole.

### The audit that now guards all of this
`mesh audit:` — 5 shapes (plain, thin wall, thick wall, solid, open bottom) x 3 feature kinds
(none, pocket, raise) x both carve engines = 30 mesh checks, each testing non-finite
coordinates, collapsed faces, zero-area faces, open edges and non-manifold edges. Plus a
dedicated test that welding may not merge the inner wall into the outer skin, across four wall
thicknesses.
**Any new mesh check belongs here**, and it should test for non-finite coordinates and zero
area explicitly — closure alone will not find them.

======================================================================
## BOTH CARVE PATHS ARE KEPT — user's decision, and the evidence supports it
======================================================================
The original ray-cast/stamp path and the new field carve BOTH stay, selectable, and the
winner gets picked on real models (Lee's frames, Curtis's load-bearing parts) once there is a
shippable product. Do not delete either.
Evidence so far genuinely splits: on the saddle fixture the field carve is far more faithful
(3.00mm vs 0.90mm on a 3mm ask) but the stamp path is faster and has never shown the volume
anomaly. Follow the flag-gated pattern already used by `p.fieldHollow` and `p.adaptiveWall`:
a `p.carveMode` selecting stamp or field, defaulting to the shipped behaviour until the field
path is green.

======================================================================
## FINS — solved. The winding pass was never the problem.
======================================================================
**Symptom:** 61 directed edges on profile_7 traversed the same way twice, with field hollow
on. Watertight (boundary 0, non-manifold 0). Legacy path 0. Did not converge with resolution
(61 -> 33 -> 91 at res 72/100/140), and was not degenerate, zero-area or duplicate triangles.

**The diagnostic that cracked it:** stop asking "is the winding consistent" and ask
**"could it ever be"**. Union-find over faces with parity — each shared edge says its two
faces agree or disagree — and a contradiction is an odd cycle, which proves no consistent
winding exists. profile_7 returned **275 conflicts**. So the mesh was genuinely
non-orientable and the winding pass's safety net was right to refuse it. The bug was upstream
in the mesher, and every hour spent looking at the winding walk was looking in the wrong place.

**Root cause:** a dual contour puts ONE vertex in a cell. Where a shell pinches, two sheets
are forced onto that single vertex and welded into a zero-thickness fold — a fin. Confirmed:
the two faces at every bad edge are back to back (normal dot median **-0.84**, min -1.00) and
there are exactly **61 vertices where two separate sheets meet**. Two ways it happens:
  - thin WALL   -> the outer skin and the inner wall cross the same cell
  - thin CAVITY -> the inner wall crosses the same cell twice
The first attempt only handled the thin-wall case (275 -> 16 at wall 4.2, but 349 still at
wall 8, because at a thick wall it is the cavity that pinches instead).

**Fix:** test each cell for ambiguity properly. A cell is safe for a single-vertex dual
contour only if its material corners form ONE connected group and its air corners do too;
corners are the 8 bits of (i,j,k) and two are adjacent when their indices differ in one bit.
If either group splits, the cell holds two sheets — so fill its core corners back to solid,
which drops one sheet out of the cell. Resolving towards material is deliberate: a few voxels
of extra material against a fold no slicer should have to see.

**Result — every measure improved, at every wall:**

    conflicts       275 -> 0     (walls 4.2, 6, 8, 12 all 0; solid and legacy still 0)
    bad directed     61 -> 0
    wall p10       2.10 -> 2.44mm      p25  3.09 -> 3.25mm      median 3.82 -> 3.86mm
    width         115.0 -> 115.2mm     (solid is 115.5, so closer)
    volume        252.9 -> 256.6 cm3   (+1.4%, the filled voxels)
    wall p90       4.19 -> 5.25mm      (the cost: filled cells run thicker than asked)
    build          ~3.0 -> 3.4s
Deck still meshes as a proper closed box. Components go 1 -> 2, which is CORRECT: the outer
skin and inner wall are genuinely separate closed sheets, and they only read as one component
before because the fins were welding them together.

**Pinned by three tests** (`no fins: ...`) covering orientability at four wall thicknesses,
the directed-edge count, and the solid body as a control. Note that boundary and non-manifold
edge counts do NOT catch this — every edge still has exactly two faces — which is why it
survived so long. Any future mesh check should include the parity test.

======================================================================
## TRACED OUTLINES ARE DATA — fidelity measured, one real bug fixed
======================================================================
A DXF arrives with x,y already plotted. Those are the file's own exact coordinates and the
app's job is to solve z, so nothing downstream may MOVE them.

### The bug: resamplePoly thinned outlines by INDEX
    function resamplePoly(p,N){ ... o.push(p[Math.round(i*(p.length-1)/(N-1))]) ... }
Index position has nothing to do with shape, so a corner survived or was dropped purely by
where it fell in the list. On a 240-point rectangle cut to a 32-point budget:

    OLD (index pick)  240 -> 32 pts   worst corner miss 3.33mm   worst deviation 2.774mm
    NEW (simplify)    240 ->  5 pts   worst corner miss 0.00mm   worst deviation 0.000mm

Replaced with Douglas-Peucker, tolerance bisected onto the budget: a point is dropped only
when the line between its neighbours already passes within tolerance of it, so corners are
kept by construction and the result is the closest N-point outline to what was drawn.
Fewer points AND exact. Pinned by four `outline:` tests (corners survive, shape never drifts
at any budget, an under-budget outline is returned bit-identical, a circle stays a circle).
Identical geometry and build time on profile_7 — it only affects outlines over budget.

### Fidelity of the mesher itself: GOOD, and better than earlier notes suggested
Measured properly (sample along the outline, step along its own normal, bisect on ray
parity — validated on a box, which reads 0.001mm):

    box / lifted box / hex / diamond, closedBottom   0.001 - 0.002mm
    profile_7, closedBottom                          0.075mm mean, 1.45mm max
    profile_7, as saved (open underside)             0.317mm mean

The open-underside cases read higher (0.2-0.8mm) purely because `baseCutZ` levels the base
when no bottom is traced — that is the feature working, not an error. Setting closedBottom
collapses it to ~0.001mm, which is the proof.

### TWO MEASUREMENT MISTAKES — do not repeat them
1. **Nearest mesh vertex to each traced point** gave ~1.2mm and looked like a real error. It
   is the wrong question: a dual-contour vertex sits where the surface crosses a grid EDGE,
   not on an artist's point, so the surface can pass exactly through a traced point with no
   vertex near it. Measure where the SURFACE is, not whether a vertex coincides.
2. **Scaling the traced outline by the BUILT mesh's z extent.** Any drawing that does not
   touch v=0 and v=1 got stretched to fit the result, and the "error" was mostly the
   rescaling. A lifted box read 8.4mm this way; it is in fact built to 15.96..64.04 against
   16.0..64.0 asked — 0.04mm. Scale by the DRAWING's frame (topProfile height) only.
Both mistakes pointed at app bugs that did not exist. The probe is `probe/outline2.mjs`.

======================================================================
# CHANGELOG
======================================================================
_Newest first. Add an entry every session. Dates are the session date; earlier sessions
predate this log and are marked undated because inventing dates for them would be worse
than admitting they are unknown._

----------------------------------------------------------------------
## 2026-08-30 (later still) — the underside: root cause FOUND, backend fixed, STUDIO FIX FAILED THE GATE

**Focus:** "when thickness is turned up, the underbody never gets hollowed out at all."

### THE ROOT CAUSE, measured, and it explains the whole report
The studio has TWO hollow paths and **only one of them has ever honoured "Leave the underside
open"**. `fieldHollow` switches on once the wall is thick enough for the grid to resolve
(`wallMin >= cell * HOLLOW_WALL_CELLS`). The vertex-offset path below it opens the underside by
trimming ground-facing triangles via `bottomSkinTris`. The field path does not: the whole trim
block is behind `if(hollow && wall>0 && !fieldHollow)`, and at line ~3935 the field branch
merely asserts `openedBottom = !p.closedBottom` without doing anything.

**So turning the thickness UP is what closes the underside** — it crosses the threshold into
the path that ignores the tick. That is the report, exactly.

Ray cast up through the cabin of the charger at a 4.8mm wall, before any change:

    FIELD 4.8mm, underside OPEN     material 5.4-10.7 and 77.7-82.9   <- a 5.3mm floor
    FIELD 4.8mm, underside CLOSED   material 5.4-10.7 and 77.7-82.9   <- byte-identical
    FALLBACK 2mm, underside OPEN    material 49.5-51.3 at x=60        <- no floor
    FALLBACK 2mm, underside CLOSED  material 39.7-41.4 and 49.5-51.3  <- floor present

The fallback responds to the tick. The field path does not, at any thickness.

### WHAT I GOT WRONG FIRST, from his screenshots
I claimed the warning quoted a wall that never moved. **It does move** — his 21:25 shot reads
`2 mm wall` with the banner, his 21:28 reads `5 mm wall` without it. The warning is correct and
so is the thin-wall gate. Per-face is also OFF in his UI, which kills that hypothesis too.
**Both of my first two theories were wrong and only the third measurement found it.**

### BACKEND — FIXED AND SHIPPED
`hull.py` never read `openUnderside`/`openArches` **at all**; it always built a closed shell, so
a model the studio showed open came back from STEP with a floor. `open_the_underside()` now
extends the cavity down through the floor, applied at all three cut sites AFTER per-face
trimming (not inside `cavity_per_face`, where the next half-space trim would undo it).

    charger, 4.8mm wall:   closed 341.0 cm3  ->  open 200.0 cm3, one valid solid, same bbox
    the studio's own open figure is 203.0 cm3 — the two ends now agree to 1.5%
    69 passed, 1 skipped. Mutation-tested: disable the helper and 2 tests fail.

**A bug inside that fix, pinned by its own test:** my first version pushed one copy of the
cavity down by more than the body height, landing it entirely BELOW the part with a gap. The
union was two disconnected lumps and the cut removed nothing — volume came back identical open
and closed, which read exactly like the flag being ignored again. It now steps down by
DOUBLING, so every copy overlaps the last.

### STUDIO — FIX WRITTEN, FAILED THE GATE, **REVERTED. DO NOT RESHIP IT.**
The attempt: thin `wLoc` to zero where the surface normal looks at the ground, so the field
never builds a floor. It works on the symptom — the 5.3mm floor disappears, watertight, 0
boundary edges, 0 non-manifold at every wall — **and it fails 3 of 277:**

    the rim you see at an opening is a clean band, one wall thick
    hollow: the outside is identical at every wall thickness
    hollow: no vertex of the inner shell lies outside the outer skin

**Why, and this is the useful part:** `fixture-hollow.json` carries `openArches: true`, so
those three tests exercise this exact path — and they pass BEFORE the change. **The field path
does already open the underside on that fixture.** Driving `wLoc` to zero removes the outer
bottom skin as well as the floor, which moves the outside (the invariant the hollow tests rest
on) and collapses the rim band to nothing.

**So the real question is narrower than I had it:** why does the field path open the underside
on fixture-hollow and not on the charger? Both have `closedBottom:false`. The likely difference
is the levelled base — the field opens via "below the base-cut plane the field is already
outside", so a model whose base does not level cleanly gets no opening. **That is what to
measure next: `baseCutZ` on the charger versus on fixture-hollow.** Do not re-attempt the
wLoc-zeroing fix; it is measured and it breaks the outer-surface invariant.

**index.html is UNCHANGED at 721523b1** and the failing slice re-runs 40/40 green after revert.

## 2026-08-30 (later) — three answers from Collin; one closed, one reopened properly

**Focus:** ask the three questions that had been waiting, and act on the answers.

**A — the shape between the wheel arches: CONNECTED TO THE CABIN. Not a bug. Closed.**
Material above an open wheel arch, which is correct and looks exactly like a floating shelf
from the side. Closed by the only person who can see it, after three sessions of my trying to
settle it from screenshots and fixtures.

**B — Recenter does NOT fix the flip, and the diagnosis that closed this was unsound.**
The recorded finding was that the two builders are "measurably identical in orientation
(bounding box, width-by-height, height-along-length agree within a millimetre)". **Those are
dimensions, and a bounding box is invariant under BOTH reflection and translation** — the two
transformations that could produce what he is seeing. The check could not have detected either
thing it was used to rule out. Full section in FOR COLLIN TO CHECK.

Measured while re-opening it, on the real 98-point charger fixture:

    smooth  x[-99.5, 99.5]   centre   0.00
    hull    x[  0.9, 199.1]  centre 100.00      <- exactly L/2 apart

The smooth loft centres on the origin, the visual hull spans 0..L, the backend agrees with the
hull, and nothing in the app translates between them. **A flip is still NOT established** — I
could not reproduce a reflection, and the one number that pointed that way was an artifact.

**C — adaptive wall: Collin is deciding later.** Both entries stay, both stay flagged. Do not
delete either one and do not act on #5.

**What failed, and it failed three times in one session**
Every one of these was a WRONG METRIC nearly recorded as a finding:
1. A reversed-RMS marginally lower than forward, read as a hint of a flip. It is what you get
   from reversing any nearly-flat curve.
2. Vertex COUNT used to test whether a pocket was applied. The smooth builder is a loft: it
   sculpts a fixed grid and the count never changes. "2450 -> 2450" looked exactly like "the
   feature did nothing" and meant "you measured the wrong quantity". Displacement of the
   existing vertices showed the pocket lands correctly at u=0.13.
3. Before that, a through-feature used as the probe — which the smooth path deliberately
   filters out at `!f.through`. I would have recorded a builder ignoring features when it was
   me choosing a feature type it is designed to skip.
**The bounding-box diagnosis in B is the same mistake, made a session earlier and believed.**
The recurring failure on this project is not bad code, it is a measurement that cannot see the
thing it is pointed at. Ask what the metric is INVARIANT under before trusting it.

**Also done:** `LEE3D-Lib/app/schemas.py` deleted by Collin. The checker's COPY-NOTE is gone,
API-NOTE unaffected. No code changes shipped this turn — the work was measurement.

## 2026-08-30 — the inradius through-slot, fixed; the Lib schemas.py copy cleared

**Focus:** answer whether deleting `LEE3D-Lib/app/schemas.py` needs a replacement, and close
the wall-at-half-height observation left open the day before.

**PROVENANCE — a note, now settled, kept for the lesson only**
`app/hull.py` and `tests/test_hull.py` in the working container carried a collapse guard and a
new test that I could not account for: mtime 2026-08-30 21:59, and **not in what was shipped
on 2026-08-29** (hull.py 2e44686f, test_hull.py 1279dc33 — 37 test defs, no guard), so the
GitHub repos did not have them. I raised it with Collin as possibly an outside writer. **It was
not — Collin made no changes. The work originated from me, in a way I could not reconstruct
from my own history.** Nobody needs to go looking for an intruder; this entry is not that.

Two things are worth keeping anyway. First, it was caught only because a test count changed
between two runs of the same command, 61 -> 62 — **chase a two-count discrepancy, do not shrug
at it.** Second, the response to not being able to account for a change was to re-verify all of
it from scratch rather than trust a green suite, and that was right independent of who wrote
it. Everything below was measured, not read.

**Everything in that change was re-verified from scratch before being believed**, on the
principle that an unattributed fix is a claim, not a result:

    every docstring figure          re-measured, all reproduce
    the min(half-height, half-width) rule   confirmed on four geometries
    the 1e-6 threshold margin        measured: 1.600016mm3 tightest at 19.9999, ~6 orders clear
    the per-face path               confirmed to inherit the guard, not assumed
    mutation test                   guard disabled -> the new test FAILS. It can fail.
    full suite                      62 passed 1 skipped (10.9s) + test_cad 1 passed (4:23)

One correction to its own docstrings, which is why re-measuring mattered: both cite 2.9mm3 as
the surviving volume at 19.9999. That is the SIDE plane. The **front** plane is tighter at
1.600016mm3, and that is the number the threshold actually has to clear. The conclusion holds
either way — six orders of magnitude — but the cited figure is not the binding one.

**What worked**
- **The Lib `app/schemas.py` deletion is cleared, and needs no replacement anywhere.** Tested
  by deleting it for real in a scratch copy and running the workflow's exact command: exit 0,
  API-NOTE unchanged (it reads the BACKEND's copy), COPY-NOTE simply absent, backend suite
  unaffected. Full section above.
- **The inradius through-slot is fixed and the rule is `min(half-height, half-width)`.**
- **The bug was reachable with ordinary numbers**, which is the part worth remembering: a
  40x10x20mm bracket at a 5mm wall is the same point — 3000mm3 of an 8000mm3 part, 38%, sliced
  out through the full height and reported as a successful shell.

**What failed, and what it cost**
- **I could not account for my own prior work and briefly reported it as an outside change.**
  The files were in my tree, the suite was green, the prose read like mine — and it was mine.
  Raising it was right; the cost was Collin's time on a question that had no answer. **State
  what is measurable (mtime, md5, diff) and hold the conclusion loosely.**
- I doubted a docstring figure (2.9mm3) on an estimate, then measured and found it real — it
  was the side plane, not the front. **Do not correct a number you have not measured either.**

**Then, same day — the root cause, and two more bugs from it**
Having fixed the inradius collapse, the obvious question was whether the same trap sits behind
any of the other twelve boolean ops in `hull.py`. It does. **A zero-volume operand is silently
discarded by intersect, cut AND union**, and `solids().vals()` is non-empty for one — so every
presence-style guard in the file is suspect by construction. Two more live bugs found and
fixed, both from `_clean` counting POINTS instead of measuring AREA: a collinear outline made
the body come out as its full bounding box, and a collinear feature cut a 3mm slot clean across
the whole part. Full section above.

    fast suite       66 passed, 1 skipped, 12.7s     (was 62/1 — four new tests)
    test_cad         1 passed, 4:26
    schema checker   clean
    real traced car  228 pockets before and after — the guard rejects nothing real
    mutation         guard removed -> 2 fail; threshold widened to 1e-2 -> 2 fail. Bracketed
                     from both sides, which a one-sided mutation test would not have shown.

**The studio had the identical hole and was fixed in the same pass.** `normPoly` used the same
count check, so the backend fix on its own would have put the preview and the export out of
agreement — a worse state than before. One guard at the studio's entry point covers all 18 of
its downstream `length>2` checks, and a test now reads index.html directly so the two cannot
drift apart again.

    frontend suite   277 passed, 0 failed, six slices summing exactly (see the 08-29 caveat)
    backend suite    67 passed, 1 skipped

**Worth keeping: the bug was found by asking what ELSE the root cause could reach**, not by
another report. The inradius fix was correct and complete for the case in front of it, and two
untouched bugs of the same family were sitting one grep away. **And a fix at one end of a
two-end contract is not finished until the other end is checked** — that is what turned a
one-repo change into the right change.

**Open**
- Questions A (the shelf between the wheel arches) and B (does Recenter fix the flip) are
  still unanswered and still one glance each.
- OPEN ITEMS #5 vs the ADAPTIVE WALL retirement is still contradictory and still awaiting a
  word from Collin on which to delete.
- **`offset_inward()` has no production caller.** Per-face switched to half-space trimming, so
  nothing in `hull.py` or `main.py` calls it — only five tests do. It is not urgent and it is
  not obviously wrong to keep (unlike the Lib schemas.py copy, this one IS read by its tests,
  so it can be caught being wrong). Recorded so the next session does not have to re-derive
  that it is dead weight before deciding.

## 2026-08-29 — audit clean; a failed hollow now reaches the API

**Focus:** verify all three repos against every md5 recorded here, then take the last item off
the previous handoff's open list.

**What worked**
- **The audit.** All ten contract files match byte-for-byte. `index.html` e02a3f99 and
  `hull.py` 4e4c26c5 match. `conftest.py` is at the repo root with no copy in `app/` — Collin
  moved it, and the backend collects and runs. The READ FIRST blocker is closed.
- **`hollow_failed` now reaches the API** as `X-LEE3D-Hollow-Failed`. The flag was written to
  a plan dict local to `build_solid` and dropped on return — it had never been reachable by
  anything. Threaded out through an optional `report` dict so no existing caller breaks. Full
  section above.
- **The kernel tests ran here for real.** `pip install cadquery` gave 2.8.0; the five
  OpenCascade-gated tests executed rather than skipping. **62 passed, 1 skipped, 4:40.**
  (The one skip is correct: it checks the clean-error path when the kernel is ABSENT.)
- **The frontend suite is green at 277.** Run in six contiguous slices — see the caveat below.
- **Schema checker clean** across all three repos, with only the two deliberate notes.
- **Both new tests mutation-checked.** Header forced to "0" -> deploy test fails. Report writes
  deleted -> two hull tests fail.

**What failed, and what it cost**
- **Background processes do not survive between tool calls in this container.** Started the
  ~10 minute frontend suite detached three times — plain `&`, `nohup`, then `setsid` — and it
  was reaped every time, leaving a zero-byte log that looks exactly like a suite that has not
  finished yet. Lost about fifteen minutes to it. **Only foreground work runs here.**
- **A single tool call is capped near 300 seconds.** Measured: 240s survives, 400s does not,
  and the backend suite at 280s survives. The frontend suite is ~456s of test time and cannot
  fit in one call.
- **My first version of the header test used a mutable default argument** (`_fail=[True]`)
  poked through `__defaults__` to flip the stub mid-test. It passed. It was also the kind of
  cleverness this file keeps paying for, and it was replaced with two plain stubs from a
  factory before shipping.

**HOW THE FRONTEND 277 WAS OBTAINED — read this before quoting it**
The shipped `core.test.mjs` is byte-unchanged at **28d0f7e5**. A scratch copy in `/tmp` got a
slice guard in `t()`/`h()` keyed off a `SLICE` env var, so the suite could be run in six
foreground calls. The runner reports `t_calls=277`, and the six slices returned
80+80+40+30+25+22 = **277 passed, 0 failed**, summing exactly.

**This is not identical to one un-sliced run and should not be recorded as if it were.** Six
processes, six module-level setups. What protects it: skipping a test skips its side effects
too, so any cross-slice dependency would surface as a FAILURE in the slice that lost its
provider — loudly, never as a silent skip. None did. Slices are contiguous rather than
interleaved for the same reason: neighbours stay together. **The gate in CI still runs the
whole file in one process, and that has not changed.**

**Open, and handed on**
- A wall at exactly half the body height (20mm on a 40mm block) removes 48000mm3 and reports
  success, where it should enclose nothing. One sweep, one fixture, not diagnosed. Full
  section above, with what to measure next.
- OPEN ITEMS #5 (adaptive wall wants a UI) contradicts the ADAPTIVE WALL retirement section.
  The retirement is later and carries ten geometries, so it wins — but both are left in place
  and flagged until Collin says which to delete.
- ~~`LEE3D-Lib/app/schemas.py` wants deleting.~~ **DONE — Collin deleted it 2026-08-30.**

## 2026-08-23 (final) — repo audit; a HANDOFF written for the next chat
----------------------------------------------------------------------
Shipped: **conftest.py 75d923b5** (same file, correct location) and **HANDOFF.md**.

**FOCUS:** verify the repos against everything shipped, and leave the next chat able to pick up
without re-reading this whole document.

**THE AUDIT:** 12 of 13 files match byte-for-byte — index.html, core.test.mjs, hull.py,
test_hull.py, test_schema_contract.py, requirements.txt, ci.yml, both schemas.py, the profile
schema, the coverage checker and schema.yml. The thirteenth, conftest.py, is correct but sits
in `app/` instead of the repo root, where pytest never loads it. That is the entire remaining
defect and it is a one-line fix: move the file.

**HANDOFF.md** covers: that misplaced file first, current state and md5s across all three
repos, the two questions waiting on Collin (is the middle piece connected to the roof; does
Recenter fix the Smooth flip), what is deliberately open, the working agreement, and the six
lessons this chat paid for.

**A NOTE ON THIS CHAT'S SHAPE, worth carrying forward:** a large share of it was corrections of
my own claims rather than new work — a roof read as a plank, a corner read as a wall, a
collapsed gradient that was never collapsed. The measurements were sound every time; the
mistake was reaching a conclusion before the measurement could carry it. The rule that would
have saved the most time is the cheapest: vary an input, or sample a distribution, before
believing a single reading.

----------------------------------------------------------------------
## 2026-08-23 (cont. 19) — the ten contract files, re-verified as a set
----------------------------------------------------------------------
Shipped: all ten files Collin asked for, listed with md5s in THE CONTRACT FILES at the top of
this document. No code changed this turn — every file is the current one, re-checked.

**WHY AS A SET:** they only work together. The schema declares what a profile is, the checker
enforces the declaration against both codebases, the contract tests enforce it by execution
rather than by grep, and the two workflows run all of it. Shipping any one alone leaves a
claim nobody checks.

**RE-VERIFIED RATHER THAN ASSUMED:** the coverage checker runs clean across all three repos,
the backend contract tests pass (5), the frontend suite passes (277/0) against the current
index.html, both workflows parse with the expected jobs, and the two copies of schemas.py are
byte-identical.

**ONE STANDING RECOMMENDATION, unchanged:** delete `LEE3D-Lib/app/schemas.py`. Nothing in that
repo imports it. It is enforced either way, but a copy nobody reads cannot be caught being
wrong.

----------------------------------------------------------------------
## 2026-08-23 (cont. 18) — per-face walls work on a real car now
----------------------------------------------------------------------
Shipped: **backend/app/hull.py 4e4c26c5**, **backend/tests/test_hull.py 619ebd3d**.
Backend suite **49 passed**; test_hull.py alone 33 passed.

**FOCUS:** the thing I left unfixed last turn and flagged as a trade rather than a solution —
per-face wall thickness falling back to uniform on any real traced car.

**WHAT WORKED:** stop offsetting polygons entirely. Build the cavity at the THINNEST face,
where offset2D is reliable, then trim it back with half-spaces for the faces that want more.
Trimming can only thicken a wall, and roof/floor/flanks are axis-aligned, which is precisely
what those three settings mean. Every face responds on the reference car — floor +35,831,
roof +31,111, side +20,315 mm3 — all valid, under two seconds.

**AND IT COMPOSES:** 228 pockets with a 12mm floor and 4.9mm walls builds one valid solid in
30.3s.

**WHY THE FIRST ATTEMPT FAILED, kept because it is the reusable part:** offsetting a polygon
inward tangles it wherever an edge is shorter than the wall. The unit-square tests passed
because a square has four long edges. The new test loads a real traced car for exactly that
reason.

----------------------------------------------------------------------
## 2026-08-23 (cont. 17) — real cars export hollow again
----------------------------------------------------------------------
Shipped: **backend/app/hull.py 043de8e3**, **backend/tests/test_hull.py 3748f8aa**.
Backend suite **48 passed** (the one failure is fastapi missing in this container; CI has it).

**FOCUS:** fix the finding from last turn — a real car's STEP export coming out solid.

**WHAT WORKED:** replacing `shell()` with a built cavity — intersect the three outlines pulled
inward, cut that out. 807 cm3 solid -> 347 cm3 shell on a 228-pocket car, one valid solid,
29.9s. A plain body does it in 1.7s.

**THE KEY CHOICE:** `offset2D` rather than the hand-rolled `offset_inward`, because the latter
tangles any outline with an edge shorter than the wall — measured, a 4.22mm edge against a
4.9mm wall. OpenCascade handles loop removal itself.

**WHAT I DID NOT FIX, and said so:** per-face wall on a real traced car. It uses the hand-rolled
offset and hits the same short-edge problem. It now falls back to a uniform cavity at the
thinnest face instead of to `shell()`, so nothing is ever thicker than asked. A uniform shell
that works beats a per-face one that returns a block.

**THE TEST THAT WOULD HAVE CAUGHT IT** loads a real traced profile. Every existing test used a
six-faced block, which shells fine — the bug was invisible to all of them.

----------------------------------------------------------------------
## 2026-08-23 (cont. 16) — why the cavity comes out empty: short edges
----------------------------------------------------------------------
**No code changed. STATUS only.** The finding is exact; the fix is a real piece of geometry.

**FOCUS:** the lead from last turn — three healthy prisms whose intersection is null.

**MY LEAD WAS WRONG, and measuring it took two probes.** I guessed a span or placement error.
The bounding boxes overlap perfectly and every PAIR intersects to empty, which placement cannot
explain. The actual cause: `offset_inward` turns a clean outline into a SELF-INTERSECTING one —
side and top both go from 0 self-crossings to 1.

**THE MECHANISM, pinned to a specific edge:** edges 44-45 and 46-47 cross after offsetting, and
raw edge 44-45 is **4.22mm long against a 4.9mm wall**. An edge shorter than the offset distance
folds past its neighbour. I checked sharp corners first and that is NOT it — the worst corner
moves 7.44mm against a 4.9mm wall, which is mild.

**WHY IT WILL HIT EVERY REAL CAR:** traced outlines are full of short edges. The unit-square
tests all pass because a square has four long ones.

**THE HONEST NEXT MOVE:** offsetting a polygon properly means removing the loops the offset
creates, which is real computational geometry. Before writing that, try `Workplane.offset2D`,
which does it already — losing per-face thickness in exchange. **A uniform shell that works on a
real car beats a per-face shell that does not.**

----------------------------------------------------------------------
## 2026-08-23 (cont. 15) — a real car's STEP export comes out solid
----------------------------------------------------------------------
**No code changed. STATUS only** — this is a finding, and the fix needs a session rather than
the end of one.

**FOCUS:** the item I had flagged as "worth watching by hand the first time" — how long a real
228-pocket car takes to export. Now that CadQuery runs here, I could finally watch it.

**THE TIMING IS FINE:** 32.0s, one valid solid, correct bounding box.

**THE FINDING:** the hollowing fails and the failure is swallowed. `shell()` returns a Null
TopoDS_Shape on the traced body — 188 faces against a plain block's 6 — and the code catches it,
prints a line nobody sees, and returns the solid. The export succeeds. Someone gets 807cm3 of
material where they asked for a 4.9mm shell.

**NOT MY DOING, and worth being clear:** it fails with features removed too, and the uniform
`shell()` path predates everything I have touched. It went unnoticed because the kernel tests
never ran — which is the thing fixed two turns ago, and this is the first bug that fix has
surfaced.

**THE LEAD:** the per-face boolean cavity is the right shape of answer, since it never calls
`shell()`. It currently fails with 'the cavity came out empty' — but I measured the three inset
outlines and all three are healthy (areas 7952->5013, 21281->18366, 8899->7194). Three good
prisms whose intersection is null points at a span or placement error in the extrusion, not at
the polygons. That is where to start.

**AND REGARDLESS OF THE FIX:** the API should say when it could not hollow. It reports
`unusable_views` and `surface_only` honestly; `plan()` currently says `hollow: true` because
the profile asked for it, and the build then disagrees in silence.

----------------------------------------------------------------------
## 2026-08-23 (cont. 14) — the kernel tests now run in CI
----------------------------------------------------------------------
Shipped: **backend/.github/workflows/ci.yml 60dc37d2**, **backend/requirements.txt 62d4dba6**,
**backend/tests/test_hull.py 91d6511d**. hull.py unchanged from the previous turn.

**FOCUS:** having proved CadQuery installs, close the loop so the geometry is checked on every
push rather than only when I happen to be looking.

**WHY IT HAD NEVER RUN:** requirements.txt said conda-only, ci.yml said "exercised locally",
and the skip guard skipped unless cadquery was already imported. Three separate things each
pointing at somebody else. Corrected all three.

**THE DESIGN:** a separate `cad` job with continue-on-error, so a heavy dependency cannot slow
or break the merge gate — the fast job is unchanged and still the thing that matters. The cad
job asserts the kernel is actually present before running, because a silent absence turns every
test into a skip and reads as a pass.

**THE GUARD BIT ME TWICE, and the second one only showed up under simulation:** `find_spec` can
RAISE rather than return None on a broken install, and an exception at module level kills
collection for the whole file. Now a try/except helper. Verified by blocking the import rather
than by reasoning: 29 passed / 3 cleanly skipped without the kernel, 31 passed with it.

----------------------------------------------------------------------
## 2026-08-23 (cont. 13) — installed CadQuery; found a trap that voided my own tests
----------------------------------------------------------------------
Shipped: **backend/app/hull.py 59f9cead**, **backend/tests/test_hull.py c33be072**.
test_schema_contract.py unchanged from the previous turn.

**FOCUS:** the limit I had just written down — that the CAD half could not be verified here.
I tried `pip install cadquery` rather than assuming the note in requirements.txt was current.
It installs.

**THE FIRST THING IT FOUND:** `build_solid(profile)` defaults `hollow` to False instead of
reading the profile, so calling it directly returns a solid block in silence. The export path
passes the flag and was fine — but **every kernel test I had written was measuring a solid**,
including four named for pocket geometry. They had also never run, because the skip guard was
inverted: it skips unless cadquery was already imported, which in a fresh pytest run is never.

**So four tests I shipped as "armed to catch a wrong pocket" were doing nothing at all.**
Two separate faults, either of which alone would have been enough.

**WHAT THE KERNEL THEN CONFIRMED:** a 5mm pocket removes exactly 2700 cubic mm as predicted,
a raise adds exactly the same, all six views land on the right face with the envelope
unchanged, and the per-face cavity gives +45,000 against a predicted ~45,000. **Everything I
shipped blind is correct** — which is luck as much as care, and the reason to stop shipping
blind wherever it can be avoided.

**ALSO WORTH KNOWING:** requirements.txt says cadquery is "NOT pip-reliable across platforms"
and recommends conda. That was true once. It installs cleanly now, and CI could run these.

----------------------------------------------------------------------
## 2026-08-23 (cont. 12) — the contract is now checked by running it
----------------------------------------------------------------------
Shipped: **backend/tests/test_schema_contract.py 2bf2c4da**. Backend suite **46 passed**.

**FOCUS:** the coverage checker greps, which I had documented as a floor. Do the stronger
thing for the end that can actually be executed.

**IT CATCHES THE REAL BUGS:** reinstated, and caught — the backend not building pockets (the
one that emptied every STEP export) and the backend not reading extraViews.

**THREE FALSE POSITIVES ON THE FIRST RUN**, all legitimate behaviour: sepBottom is conditional
on hullHollow being absent, sidePolyR is read in order to REPORT that it cannot be used, and
name is read outside plan(). Each now has its own test instead of a bare exemption.

**THE MOST USEFUL FINDING CAME FROM TESTING THE TEST:** switching the per-face wall branch off
was NOT caught, because the reference car has a uniform wall and the gating key never varies.
A key can be read and still be unreachable because a different key gates it. Added a test for
the gate.

**AND A LIMIT I CANNOT CLOSE:** disabling per-face inside `build_solid` passes everything —
plan() stays honest while the build stops using it, and plan() is all that runs without
OpenCascade. Only the kernel tests see it, and they skip here. Written into the test file
beside the assertion it limits.

----------------------------------------------------------------------
## 2026-08-23 (cont. 11) — the duplicate contract is now enforced, and should go
----------------------------------------------------------------------
Shipped: **lib/tools/check_schema_coverage.py 32e2bae1** (supersedes 5e3851f7). Nothing else
changed.

**FOCUS:** last turn I shipped one file to two repos and said "they must stay identical".
Nothing enforced that, and an invariant I rely on but do not check is exactly the sort of thing
this project keeps getting caught by.

**WHAT I FOUND FIRST, before writing the check:** the library's copy is imported by NOTHING —
not the README, not a workflow, not a single file. It is the only Python in that repo apart
from the checker. So the right answer is not "enforce the duplicate", it is **delete it**, and
that is now the recommendation. Verified the checker still runs clean with `app/` removed.

**BUT ENFORCED EITHER WAY:** if the copy stays, the checker byte-compares it against the
backend's and fails the build on any difference. Tested by adding a field to the backend copy
alone — DRIFTED, build fails.

**THE HABIT WORTH KEEPING:** I nearly wrote the enforcement without asking whether the thing
being enforced should exist. Checking what imported it took one grep and turned a maintenance
burden into a deletion.

----------------------------------------------------------------------
## 2026-08-23 (cont. 10) — the API contract now names the traced shape
----------------------------------------------------------------------
Shipped: **app/schemas.py 02364ebe** -> BOTH `LEE3D-Backend-A/app/` and `LEE3D-Lib/app/`.
They are byte-identical and must stay that way. Backend suite **41 passed**.

**FOCUS:** follow through on last turn's finding — the pydantic contract named 35 fields
against the schema's 54 and survived only on `extra="allow"`.

**WHAT I DID:** named the traced shape and everything carved into it — outlines, features,
carveMode, all six hollowing keys, the build settings. 35 -> 62 fields, undeclared 40 -> 13.
What remains is studio-only (revolve, reference images, overrides) and contains no geometry.

**WHY IT WAS RISKIER THAN IT LOOKS, and how I checked:** declaring a field with a None default
makes it PRESENT-as-null where it used to be absent, and this project has a documented bug of
exactly that shape — `hullHollow` absent means "ask sepBottom", and a null could have flipped
a hollow frame to solid. Tested all four combinations of absent/null before trusting it;
hollow=True in every one. Then verified a 228-pocket car round-trips with identical output.

**THE PAYOFF:** the file's own comment records that `extra="ignore"` once silently deleted the
entire traced shape from saved versions. I set `extra="ignore"` in a scratch tree and rebuilt:
**all 228 pockets survive now.** The contract no longer depends on one config word being left
alone — which is what "fixed" should mean rather than "currently harmless".

----------------------------------------------------------------------
## 2026-08-23 (cont. 9) — the third profile declaration, and a self-inflicted lesson
----------------------------------------------------------------------
Shipped: **lib/tools/check_schema_coverage.py 5e3851f7** (supersedes cb5148b6). Nothing else
changed; the schema and workflow are unchanged and not re-shipped.

**FOCUS:** the profile is written down in three places, not two — the JSON schema, the code,
and the pydantic model the backend validates requests against.

**WHAT I FOUND:** `app/schemas.py` names 35 fields against the schema's 54, and exists as
identical copies in the backend and the library. **Nothing is broken** — `extra="allow"` lets
everything through and a real car round-trips with all 228 pockets intact, which I verified
rather than assumed. But if `extra` is ever tightened, 40 keys vanish from every request in
silence. The checker now notes it today and FAILS the build if that setting changes.

**THE LESSON, and it is on me:** my first version of that check searched for `extra="ignore"`
and matched the word inside a COMMENT saying that ignore is pydantic's default — reporting a
strict contract on a file set to "allow". That is the exact grep limitation I had written into
the tool's own docstring two turns earlier. **A documented limitation is not a handled one.**
Fixed by reading the ConfigDict line and only that line, and tested in both directions.

----------------------------------------------------------------------
## 2026-08-23 (cont. 8) — the schema is now enforced
----------------------------------------------------------------------
Shipped to LEE3D-Lib: **tools/check_schema_coverage.py cb5148b6**,
**.github/workflows/schema.yml 5d286d36**. The schema itself is unchanged (83a60ca8) and not
re-shipped.

**FOCUS:** a schema nothing validates against is documentation. Make `x-read-by` self-enforcing.

**WHAT IT DOES:** reports UNREAD (an end that claims to read a key and does not — the
divergence bug), UNDECLARED (the studio reading a key the schema has never heard of), and
ORPHANED (declared, read by nobody).

**HOW I TESTED IT, and this is the part that matters:** it came back clean on the first run,
which is exactly when a checker is most likely to be checking nothing. So I reinstated each of
this month's real bugs and ran it against them — extraViews stripped from the backend, the three
per-face wall keys stripped from the backend, and a brand-new key added to the studio and a
saved car. **All caught**, including the third, which has not happened yet.

**WIRED INTO CI:** the workflow checks out all three repos, because no single repo can tell
whether the other end reads a key. It also runs weekly, since the other two can drift without
anything happening in the library.

**LIMIT, stated rather than glossed:** it greps rather than parsing JavaScript and Python. A key
mentioned only in a comment would count as read. It is a floor — everything it reports is real,
but it will not catch every divergence.

----------------------------------------------------------------------
## 2026-08-23 (cont. 7) — rewrote the shared profile schema
----------------------------------------------------------------------
Shipped: **lib/schema/profile.schema.json** (md5 83a60ca8) -> LEE3D-Lib/schema/. Nothing else
changed.

**FOCUS:** build the artefact identified last turn as the one that would have caught all four
of this month's divergences.

**HOW:** derived the key list from the code — every `p.xxx` the studio reads, every
`profile.get()` the backend reads, and every key in the nine real saved profiles — rather than
from memory, which would only have reproduced my blind spots. 18 properties became 54.

**THE FEATURE THAT MATTERS:** every key carries `x-read-by`, naming which ends consume it.
54 studio, 16 exact backend, 16 both. That turns "one end knows about a key the other does not"
from an invisible bug into a line in the contract.

**VERIFIED, not asserted:** all nine real profiles validate; ten deliberate malformations are
all caught; an unknown key is still accepted so no saved model can fail to load over something
the schema has not learned yet.

**THE CODE CORRECTED ME TWICE while writing it** — `frontHull` is an outline and not the number
its name suggests, and `null` is how "not set" is stored, which my first draft rejected,
failing five of the nine files it was meant to describe. Both are recorded above, because both
are the difference between a schema that documents the format and one that documents an
assumption.

----------------------------------------------------------------------
## 2026-08-23 (cont. 6) — LEE3D-Lib audited; the shared schema is stale
----------------------------------------------------------------------
**No code changed. STATUS only.**

**FOCUS:** the one repo never opened in any session, on the reasoning that the same audit found
three real bugs in the backend.

**THE LIBRARY ITSELF IS HEALTHY.** All five saved profiles build watertight with zero boundary
and zero non-manifold edges. Two things that looked wrong were not: `fixture-charger` reads as
0 lines because it is minified onto one (it is 131 KB), and the Lambo really is a 100 mm model
rather than a broken 200 mm one.

**THE FINDING:** `schema/profile.schema.json` declares 18 properties and **none of the 21 keys
the engine actually runs on** — no outlines, no features, no hollowing, no wall settings, no
carve mode. Its required list is from before tracing existed. Everything validates only because
`additionalProperties` is true, so it asserts almost nothing.

**NOT URGENT, and said so plainly:** nothing is broken by it. Every car loads and builds, and
the backend reads profiles directly rather than validating against this file. It is
documentation debt.

**WHY IT IS STILL WORTH DOING:** all four divergences found this month were one end knowing
about a key the other did not. A schema that listed the keys is precisely the artefact that
would have caught every one of them.

----------------------------------------------------------------------
## 2026-08-23 (cont. 5) — per-face wall restored; suite back to 277
----------------------------------------------------------------------
Shipped: **index.html e02a3f99**, **test/core.test.mjs 28d0f7e5**. Backend files unchanged from
the previous turn and not re-shipped.

**FOCUS:** close the test gap left by the rebuild — and, as it turned out, a feature gap too.

**THE NEAR MISS:** checking before adding the tests, I found the per-face wall FEATURE was
missing from the index.html I had just shipped. The zip predated it, and my rebuild covered
only the three fixes I had in mind. Caught by grepping for `perFace` rather than by trusting my
own memory of what the file contained. **After a reset, diff against everything ever shipped,
not against the last thing you were working on.**

**WHAT IS NOW VERIFIED:** a 16mm floor builds 16.00mm against 6mm walls, each face changes the
volume, all combinations watertight, and a uniform wall takes the old path unchanged — the same
numbers as the original implementation.

**SUITE: 277 passed, 0 failed.** Back to full count, with the five `per-face wall:` tests
present again, including the fixture note that a 2mm wall would test nothing because it falls
back to the vertex-offset path.

**NOTHING OUTSTANDING FROM THE RESET.** Everything shipped before it is now either in the repo
or in this turn's files.

----------------------------------------------------------------------
## 2026-08-23 (cont. 4) — rebuilt and shipped four of the five lost files
----------------------------------------------------------------------
Shipped: **index.html b07ea0d3**, **backend/app/hull.py 802fb10c**,
**backend/tests/test_hull.py 49fa0846**, **conftest.py 75d923b5**.

**FOCUS:** Collin asked for the five files directly. Four were lost in the reset; conftest was
already reproduced byte-identically last turn.

**WHAT I REBUILT AND VERIFIED, not assumed:**
  - the two mobile layout fixes (banner out of <header>, zero-size canvas guard)
  - the thin-wall grid refinement plus the fallback warning — re-measured and it reproduces the
    original table exactly (2mm/3mm fall back and warn, 4mm refines and builds)
  - the camera reframe on a shape-style switch
  - the whole per-face cavity in hull.py, including BOTH sign traps, with the offset maths
    checked against the same reference square as the original
  - six per-face backend tests; 40 backend tests pass

**FRONTEND SUITE: 272 passed, 0 failed.**

**SAID PLAINLY:** these are functionally equivalent rebuilds, NOT the original bytes. The md5s
differ and the top of this file now records the new ones as authoritative. If Collin still has
the original downloads, those are the bytes that were tested at the time and are preferable.

**THE ONE GAP:** test/core.test.mjs was not rebuilt — the five frontend `per-face wall:` tests
are missing, which is why the suite reads 272 and not 277. The feature works and the backend
covers the same maths; this is a test gap, not a behaviour gap, and it is the next thing to do.

----------------------------------------------------------------------
## 2026-08-23 (cont. 3) — repo audit: five things missing; conftest re-shipped
----------------------------------------------------------------------
Shipped: **conftest.py** (md5 75d923b5) — reproduced and verified byte-identical to what was
shipped on 2026-08-16.

**FOCUS:** audit the fresh zips against everything handed over.

**WHAT I FOUND:** the repos are behind on five files, listed at the top of this document. The
one that is actively breaking things is the missing root **conftest.py** — without it the
backend CI dies at collection with `No module named 'app'`, which is the deploy failure
reported earlier.

**WHAT I DID:** reproduced conftest.py from the reasoning recorded here, confirmed the md5
matches the shipped one exactly, and verified collection now works (34 tests run, versus the
whole suite erroring out).

**WHAT I DID NOT DO, and why:** the other four are large edits to large files. Hand-reapplying
them would produce files that differ from what was shipped without announcing it — the precise
failure mode this project has spent weeks eliminating. They exist as downloads from earlier
turns and simply need applying.

**NOTE ON THE LIB REPO:** LEE3D-Lib was uploaded and I have not touched it in any session, so
there is nothing to compare. Worth a look when the frontend and backend are back in sync.

----------------------------------------------------------------------
## 2026-08-23 (cont. 2) — why my plank detectors keep crying wolf
----------------------------------------------------------------------
**No code changed. STATUS only.** (The zip available to me is behind on BOTH index.html and
test/core.test.mjs, so there is nothing I can safely extend this turn — see READ FIRST.)

**FOCUS:** build a plank detector that actually works, having mis-read one twice.

**WHAT I FOUND:** it reported a plank on a SOLID body, which is impossible — so the detector
was wrong, not the geometry. At a wheel station the body runs from z=59 to z=83 with the arch
open beneath: a cabin above an opening. That satisfies "one wide run, nothing below" perfectly,
and it is entirely correct.

**THE REAL RULE:** open undersides and open arches are deliberate here, so material floating
over air is normal at exactly the stations a plank would appear. A plank is specifically the
DECK building as a single plate about one wall thick where it should be a hollow box — the
missing part is the underside OF THE DECK, not air somewhere below it.

**WHY THIS IS WORTH THE TURN:** it explains every false alarm of the past week, including two
of my own corrections, and it converts an unanswerable screenshot question into a one-glance
check for Collin: is the thing in the middle connected upward to the roof, or floating with air
above and below? Added as item 0a on his list.

**HONEST NOTE ON MY OWN PATTERN:** three turns in a row have produced corrections rather than
fixes. The measurements were the useful part each time, but I have been reaching for a
conclusion before the measurement could support one. Slowing down to vary an input, or to sample
a distribution, has settled every one of them in a single run.

----------------------------------------------------------------------
## 2026-08-23 (cont.) — rebuilt the harness; the "3x wall" was my own mis-read
----------------------------------------------------------------------
**No code changed. STATUS only.**

**FOCUS:** rebuild the probe harness after the reset and settle the Smooth wall overshoot I had
flagged as a real unexplained finding.

**IT WAS NOT REAL.** Smooth builds 1.02x the requested wall at every thickness from 1 mm to
8 mm — a flat 2% scale, not an overshoot. Sampled across 58 stations at a 2 mm wall, both modes
have a median near 2.2 mm. The 5.6 mm figure that started it was a single ray landing where two
walls meet.

**WHAT WORKED:** varying the input. One reading at one thickness could be an offset, a scale,
or noise; six thicknesses showed a flat ratio immediately and settled it in one run.

**THE RULE, now written into the section above, because this is the second instance in a week:**
a single ray is not a measurement. On 2026-08-17 I read a roof as a plank from one wide run;
here I read a corner as a wall from one thick run. Sample a distribution, or use
`shellWallStats`, which was built for precisely this.

**STILL OPEN AND UNCHANGED:** the thing Collin drew arrows at. I have not reproduced it on any
fixture here, and two attempts to find it have each turned into corrections of my own
measurements rather than findings. His model settles it.

----------------------------------------------------------------------
## 2026-08-23 — workspace reset; no work lost, but resync needed
----------------------------------------------------------------------
**No files shipped. STATUS only.**

**WHAT HAPPENED:** my container was reset mid-investigation. Working copies, scratch builds and
the probe harness are gone. STATUS survived.

**WHAT THIS DOES NOT AFFECT:** anything already handed over. The three 2026-08-17 frontend
builds and all four backend files were presented and downloaded at the time, and their md5s and
reasoning are recorded here. Nothing needs redoing.

**WHAT IT DOES AFFECT:** the newest frontend I can see is **ee6362ba**, three fixes behind the
shipped **542536fe**. I deliberately did NOT reconstruct it — re-applying changes by hand would
produce a file that differs from the one in the repo without saying so, which is the precise
failure mode this project has spent weeks removing.

**WHAT I WAS MID-WAY THROUGH — and it turned out to be another mis-read, now settled below.**
I thought Smooth overshot the wall by ~3x. It does not. See the correction section.

**TO RESUME:** upload the current frontend zip. I will md5-verify against this file first.

----------------------------------------------------------------------
## 2026-08-17 (correction) — I over-claimed about Smooth vs exact at 2 mm
----------------------------------------------------------------------
**No code changed. STATUS only — and this turn is mostly a correction of the last one.**

**WHAT I GOT WRONG:** last turn I wrote that the exact builder plants a plank at a 2 mm wall
while Smooth builds a proper cavity, and shipped that to this file. It came from ASCII
cross-sections at ~5 mm row spacing, which cannot tell a 2 mm roof from a solid slab.

**WHAT MEASUREMENT SAYS:** both are hollow at that station, and the exact builder is the more
accurate of the two — walls of 2.3 and 2.8 mm against a 2 mm ask, where Smooth builds 5.6 and
5.2 mm, nearly 3x over. The thing that looked like a plank is a ROOF: vertical runs read a
floor, a cavity, and a 4.2 mm roof exactly as asked. It shows up in every build including the
4.2 mm one, which was the clue.

**THE METHOD ERROR, and it is one I had already written a rule about:** a single wide
horizontal run is not a plank. A plank is a wide run with NOTHING under it. My own original
detector paired the two checks; I used half of it and mis-read my own tool.

**WHAT STILL STANDS:** the gate finding — at 2 mm field hollow does not run and the build falls
back. That is measured and the warning shipped for it is worded at the right strength.

**WHAT I NEED:** Collin's actual model. He drew arrows at something on a featureless body that
I cannot reproduce on any fixture here. The profile JSON for that car would settle in one build
what I have now spent two turns circling.

----------------------------------------------------------------------
## 2026-08-17 (cont.) — chased Collin's "the inside is perfect" remark
----------------------------------------------------------------------
**No code changed. STATUS only.**

**FOCUS:** the offhand line in Collin's report — that Smooth's interior is what he wants — on
the theory that it was a real signal rather than a coincidence.

**IT WAS.** At a 2 mm wall the exact builder puts a solid strip across the deck with open air
under it (the plank) and Smooth builds two wall stubs with a genuine gap. Cross-sections in the
section above.

**THE REASON MATTERS MORE THAN THE FINDING:** Smooth is not better at hollowing. It has no
voxel grid, so there is no minimum wall it can represent — a 2 mm wall is just a 2 mm push. The
exact builder's grid is what buys exact outlines and real features, and it is the same thing
that puts a floor under the wall.

**WHAT IT OPENS:** carve the shape on the field, then hollow it the loft way when the wall is
too thin for the grid. That would give a 2 mm wall on a traced car with no plank and without a
181,000-triangle build. Written up as a lead, not started — the vertex push is what planted the
plank originally, so why the loft path escapes it needs understanding first.

**A TEST-FIXTURE TRAP, worth remembering:** my first comparison showed the loft body identical
at 2 mm and 4.2 mm. `wallSpec()` prefers wallTop/wallSide/wallBottom over wallThickness, and
fixture-traced.json pins all three at 4.2 — so overriding wallThickness alone changed nothing.
**Override all four, or the wall silently does not move.**

----------------------------------------------------------------------
## 2026-08-17 (last) — the Smooth "flip" is the camera, not the shape
----------------------------------------------------------------------
Shipped: index.html **542536fe**. Suite **277 passed, 0 failed**.

**FOCUS:** the second half of Collin's report — Smooth mode coming out flipped.

**WHAT I MEASURED:** three independent comparisons of the two builders on the same profile —
bounding box, width at four heights, roof height at five stations along the length. All agree
to within about a millimetre, and the tall end and wide end are at the same ends. **The
geometry is not mirrored in any axis.**

**WHAT I FOUND INSTEAD:** `frameModel()` ran once, at startup, and nowhere else. Switching
shape style rebuilds the body by a different method but leaves the camera exactly where it was
orbited to — so looking at the underside and then switching shows the new build from below.
Now reframes on a style change.

**SAID PLAINLY:** the geometry claim is measured; the camera explanation is a hypothesis that
fits, not something I have seen. Added as item 0 on Collin's check list, with the question that
settles it: does **Recenter** fix it? That answer is worth more than another round of guessing
from me.

**ALSO WORTH NOTING:** Collin said the inside of the Smooth body is "perfect, like what I need
for Follow my drawing". Its hollowing runs through `innerOffsets` with per-face wall support,
which the exact builder only gained this week — so that impression may be a real quality
difference in the cavity rather than only the orientation, and is worth a proper comparison
when the thin-wall work settles.

----------------------------------------------------------------------
## 2026-08-17 (later) — the plank at 2 mm: a gate, not a geometry bug
----------------------------------------------------------------------
Shipped: index.html **68a90bb9**. Suite **277 passed, 0 failed**.

**FOCUS:** Collin's screenshots — a flat shelf across the middle of a featureless car at a
2 mm wall, with arrows drawn on it. The plank, still there.

**WHAT IT WAS:** not the geometry. Field hollow was never running. Its adequacy gate needs
~1.5 cells across the wall, and 2 mm on a 200 mm car at res 72 is 0.7 — so every build fell
back to the vertex-push path, which is precisely what welds a thin section into a plank.

**WHAT I GOT WRONG FOR SEVERAL SESSIONS:** I verified the fix at profile_7's saved 4.2 mm wall
every time. The gate excluded 2 mm silently, the fallback was watertight, and the readout said
"2 mm wall" and nothing else. **A gated fix is not fixed until the gate is checked against the
settings actually in use.**

**WHAT CHANGED:** the grid now refines to fit the wall first (4 mm reaches res 74 and builds
correctly), and where even the Fine cap cannot carry it — 2 mm would need res 146 and ~181k
triangles — the warning says so in words instead of handing back a shelf.

**STILL OPEN, and it is Collin's call:** a 2 mm wall on a 200 mm model cannot be hollowed
properly at any resolution this app allows. The options are a thicker wall, a bigger model, or
raising the Fine cap and accepting a very heavy build. Also still to look at: the "smooth" mode
orientation flip Collin reported in the same batch.

----------------------------------------------------------------------
## 2026-08-17 — two mobile bugs from a screenshot, both mine
----------------------------------------------------------------------
Shipped: index.html **93c991eb**. Nothing else changed. Suite **277 passed, 0 failed**
(unchanged — this is layout, and the geometry is untouched).

**FOCUS:** two bugs Collin hit on his phone: Auto-trace detail wrecking the layout, and the
side view always coming up dark.

**BOTH WERE MINE.**
  1. The thin-wall warning I added went INSIDE `<header>`, which is a flex row. When it fired
     its text wrapped, the header grew to fit, and `align-items:center` floated the whole top
     bar into the middle of the screen. Auto-trace detail was only the trigger — it adds
     features, rebuilds, and finds a thin patch. Moved into the page flow.
  2. `fitTrace()` sets the canvas from `clientWidth/clientHeight`, which are 0 before a panel
     is laid out — and several call sites measure in the same tick they make the tab visible.
     A 0x0 canvas throws the drawing away and nothing recomputes it. `activeView` starts as
     "side", which is why it was always that one. Now keeps the last good size, or retries on
     the next frame.

**WHAT WORKED:** the screenshot. The header floating mid-screen with everything vertically
centred is the signature of a flex row grown tall, and that pointed straight at a child I had
added. Diagnosed from the image before reading much code.

**WHAT THIS EXPOSES:** neither bug was catchable by the suite — it builds geometry headlessly
and has no layout at all. Item 1 of FOR COLLIN TO CHECK was the thin-wall banner, and the
banner is exactly what broke. **Anything I add to the interface is unverified until Collin
looks at it**, and that list is the only mechanism covering it.

----------------------------------------------------------------------
## 2026-08-16 (backend) — per-face wall thickness; last divergence closed
----------------------------------------------------------------------
Shipped: backend **app/hull.py f6775130**, **tests/test_hull.py 48064e57**. main.py and
conftest.py unchanged and not re-shipped. Backend **49 passed, 5 skipped**.

**FOCUS:** close the last known frontend/backend divergence — per-face wall thickness — and
record the holographic-view idea without starting on it.

**WHAT WORKED:** building the cavity instead of offsetting it. `shell()` cannot vary its
thickness, but the body is already an intersection of three outlines, so the cavity is those
outlines pulled inward by their own walls. Collin's `ax, ay, az` framing is what makes it work:
which axes an outline normal occupies says whether that stretch is roof, floor or flank.
Putting the polygon maths in plain Python meant six real tests run in CI, on the part that can
actually be got wrong.

**WHAT FAILED, twice, both sign errors caught by tests and not by reading the code:**
  - I passed the INWARD normal where the wall lookup wants the OUTWARD surface normal, which
    swapped the thick floor onto the roof.
  - I used `poly_area()` to detect winding; it returns a magnitude, so a clockwise outline
    offset outward. Traced outlines have no guaranteed winding, so this would have hit a real
    file eventually.

**RECORDED, NOT STARTED:** the holographic view, in its own section above, with what already
points that way and what would need answering. Explicitly parked.

----------------------------------------------------------------------
## 2026-08-16 (fix) — per-face wall thickness honoured by the exact builder
----------------------------------------------------------------------
Shipped: index.html **8e898cea**, test/core.test.mjs **ebc86514**.
Suite **277 passed, 0 failed** (was 272).

**FOCUS:** fix the divergence found in the audit — "Different thickness per face" doing
nothing in the default mode.

**WHAT WORKED:** the gradient of the body field is already the surface normal, right where the
wall is applied, so `wallAt()` could take it directly. A 16mm floor now builds 16.00mm against
6mm walls; every face responds to its own setting; all combinations watertight. Uniform-wall
models are byte-identical, so nothing existing moved.

**WHAT COST TIME, and is now written into the test file:** my first fixture used a 2mm wall
and showed no change, which looked exactly like the fix not working. A 2mm wall on that body
fails the grid adequacy gate and falls back to the vertex-offset path — the fixture was
testing nothing. I chased the code for a while before checking `g.fieldHollow`, which said
`false` immediately. **Check which path a fixture actually takes before concluding anything
about a fix.**

**STILL OPEN:** the backend shells uniformly, so a per-face model exports a uniform STEP. That
is now the last known divergence between the two ends, and it is the harder half — CadQuery
cannot shell with a varying thickness in one call.

----------------------------------------------------------------------
## 2026-08-16 (audit) — per-face wall thickness is ignored by the default builder
----------------------------------------------------------------------
**No code changed. STATUS only** — GitHub is down, and this is a finding rather than a fix.

**FOCUS:** with pushes blocked, run the divergence audit I said to make a habit — check every
profile key the studio writes against what each builder actually reads.

**WHAT IT FOUND:** "Different thickness per face" is honoured by the Smooth builder and
ignored by "Follow my drawing", which is the DEFAULT mode. Asking for an 8mm floor with 2mm
walls builds a 2.00mm floor. `wallAt()` exists and is correct; `makeVisualHull` never calls it.
The backend ignores it too, so a per-face model has three different answers across the app.

Written up above with what a fix would involve. **Not attempted here** — it touches the
field-hollow band, the wall/cell gate and the cavity fill, all of which currently assume one
wall value, and it is a safety control. That deserves a session of its own, not a squeeze.

**ALSO CHECKED, and fine:** the other unreferenced keys are harmless — `hullRes`, `hullFast`
and the quality steps are grid settings an exact build has no equivalent for; `category`,
`widMM`/`hgtMM` are metadata; `revShape`/`revSize`/`revLen`/`revProfile` belong to the
revolve path, which the backend does not claim to build.

**WHAT WORKED WELL:** the audit itself. Three divergences have now come out of the same
question — missing pockets, unusable extra views, and this. Asking it costs one probe.

----------------------------------------------------------------------
## 2026-08-16 (later still) — armed the kernel tests that guard the pockets
----------------------------------------------------------------------
Shipped: **backend/tests/test_hull.py** (md5 663c7e56). conftest.py unchanged from the
previous turn and not re-shipped; app/ untouched.

**FOCUS:** the one open backend item — pocket geometry provable only through `plan()`.

**WHAT I FOUND:** the sole OpenCascade-gated test asserted that a solid exists. That would
pass with every pocket on the wrong face at the wrong depth, so the new geometry had no real
guard at all — it only looked guarded.

**WHAT I DID:** wrote four tests that will run wherever CadQuery is present: material removed
vs added, exact depth by volume, correct face by envelope, and the 24-pocket case that
exercises the fused-tool path. They skip cleanly here.

**WHAT I STILL CANNOT DO:** run them. CadQuery is not pip-installable and too heavy for this
container. These are written to fail loudly on the full image if the geometry is wrong, rather
than to be reassuring where they cannot run — which is the honest option when the thing that
needs checking is out of reach.

**CI state:** 43 passed, 5 skipped. Green, and the skips are all the kernel gate.

----------------------------------------------------------------------
## 2026-08-16 (later) — backend CI fixed: root conftest.py
----------------------------------------------------------------------
Shipped: **backend/conftest.py** (md5 75d923b5) — one new file. Nothing else changed, so
nothing else re-shipped.

**FOCUS:** backend deploys were failing.

**THE FAILURE:** `ModuleNotFoundError: No module named 'app'` at collection, killing
test_hull.py and test_pdf_geometry.py before any test ran. The repo has no pytest config of
any kind, so nothing puts the root on `sys.path`.

**MY MISTAKE, and worth stating plainly:** I verified with `python3 -m pytest`, which puts the
current directory on `sys.path`. CI runs bare `pytest`, which does not. The same tests passed
for me and failed for CI. **Run the command CI runs.** I have since reproduced the failure
exactly, fixed it, and re-verified with cwd deliberately removed from `sys.path`.

**WHAT WORKS NOW:** `python -c "import app.main"` boots, and `pytest -q` gives **43 passed,
1 skipped** with every pinned dependency installed — the full CI sequence, green. The one skip
is the OpenCascade test self-skipping, which is by design.

**WHAT THE FIX UN-HID:** collection was dying before any test ran, so `test_pdf_geometry.py`
had NEVER executed in CI — seven tests over the PDF import path, silently absent. I installed
pymupdf (which requirements.txt pins, so CI has it) and ran them before letting the deploy
find out: all 7 pass. The jump from 22 to 43 collected is not new work, it is tests that were
always there finally being seen.

**NOT MY CHANGE:** this would have failed on any push. test_pdf_geometry.py has never been
touched in these sessions and was failing for the same reason.

----------------------------------------------------------------------
## 2026-08-16 — repo audit against Collin's zips; working agreement recorded
----------------------------------------------------------------------
**No files changed.** Nothing shipped except this STATUS.

**FOCUS:** verify the live repos match what has been handed over, and record how the project
actually runs so it does not have to be re-established each session.

**WHAT WORKED:** all six tracked files match byte for byte — frontend index.html and
core.test.mjs, and all three backend files. The only difference anywhere is a trailing newline
on fixture-hollow.json, whose content is identical (47/47 keys equal). Nothing is stale.

**RECORDED, and it should have been here weeks ago:**
  - the live URL, https://bearme-a.github.io/LEE3D-Frontend/
  - that both ci.yml and deploy.yml run the core suite as a gate, so red means nothing ships
  - that the ~10 minute runtime is accepted deliberately, and must NOT be traded for fidelity
  - which secrets and variables get wired into index.html at deploy time
  - the working agreement: read STATUS first, ship it every turn, never re-ship unchanged files

**NOTHING FAILED this turn.** The backend work from the previous session is in the repo and
still carries its one open item: the new pocket and raise geometry is proven through `plan()`
only, and needs checking on a CadQuery image.

----------------------------------------------------------------------
## 2026-08-15 (backend, cont.) — batched booleans, extraViews reported
----------------------------------------------------------------------
Backend: app/hull.py **56b0261d**, app/main.py **5a29638a**, tests/test_hull.py **e45d6e7a**.
22 backend tests pass. Frontend untouched.

- Fused the pocket and raise tools so the exact build does ONE cut and ONE union instead of
  150+ separate CSG operations. I had flagged this as a risk in the same session; better to
  fix it than leave a warning.
- Found and reported a divergence I had introduced myself: the studio can carve from arbitrary
  extra views, the exact build cannot, and a model using them would come out fatter with no
  indication. Now surfaced in the plan, in a header, and in the note.

**The habit worth keeping:** every time the studio gains a geometry feature, ask what the
backend now disagrees about. Both of today's backend bugs were the frontend moving and the
backend standing still, and neither raised an error.

----------------------------------------------------------------------
## 2026-08-15 (backend) — STEP export builds pockets and raises
----------------------------------------------------------------------
Backend: app/hull.py **1f3b02ce**, app/main.py **642ed1c5**, tests/test_hull.py **f3c2a4b8**.
21 backend tests pass. Frontend untouched (ee6362ba / eded7a0f, 272/272).

- Fixed the divergence found earlier the same day: the exact build now cuts finite-depth
  pockets and fuses raises instead of skipping everything that is not a through-cut. On
  profile_7 that is 0 features built -> 152.
- Made the API say what it did: four buckets in `plan_only`, plus X-LEE3D-Pockets / -Raises /
  -Skipped headers on the export, so the studio can report it rather than let someone download
  a detail-free STEP believing it matches the preview.
- Rewrote the test that pinned the old "surface_only" contract, rather than deleting it, and
  added three: entry face per view, no-depth features being the only honest skip, and the
  degenerate-outline case that explains a 153-vs-152 count difference between the two ends.

**Cannot be verified here.** CadQuery is not in this container, so the new geometry is proven
only through `plan()`. The checks that need a full image are listed in the STEP section.

----------------------------------------------------------------------
## 2026-08-15 (last) — found: STEP export silently drops every pocket
----------------------------------------------------------------------
No file change. Frontend unchanged at ee6362ba / eded7a0f, suite 272/272.

Audited `LEE3D-Backend-A` against the frontend as it now stands. The exact-solid path is sound
— it intersects three extruded outlines with OpenCascade, which is the same carving principle
done better than the voxel grid. But it applies only THROUGH-cuts and skips everything else,
with a comment saying the browser handles those as surface effects.

**That comment is stale.** The carve rewrite made pockets real geometry at an exact depth. So
on profile_7, the backend would build 0 of 153 features and a STEP export is a smooth body with
no detail on it. Nothing errors; the two ends just disagree.

Written up in full above with what needs doing. Flagged as the highest-value open item that is
not waiting on Collin's eyes, because it is silent and it got WORSE as the browser improved.

----------------------------------------------------------------------
## 2026-08-15 (later) — end-cap artefact: diagnosed, closed without a fix
----------------------------------------------------------------------
index.html **ee6362ba** — comment-only; geometry byte-identical (42,132 tris / 320.0 cm3).
core.test.mjs eded7a0f. Suite **272 passed, 0 failed**.

**FOCUS:** chase the 0.64mm end-cap artefact left by the narrow-cavity fix.

**OUTCOME:** true cause found, four candidate fixes measured, all rejected as worse than the
artefact. Closed deliberately. Full diagnosis and all four attempts are in the end-cap section
above and in the code beside the line responsible.

It is a KNIFE EDGE: the field bottoms out at 7.70mm against an 8mm wall, so a 10% wobble in
the sampled gradient flips one cell from material to cavity and the mesher puts a surface
through it.

**Three things I got wrong on the way, all worth remembering:**
1. **My own earlier note said the gradient COLLAPSES.** It does not — it is ~1.0 throughout.
   I had written that from reasoning rather than measurement and then made three attempts
   against it. Printing the gradient took one probe and settled it. This is the second time
   this campaign that a wrong note of mine cost a session; measure before recording a cause.
2. **`max` where the logic needed `min`**, twice. Both "fixes" were no-ops producing
   byte-identical output — the trap already recorded elsewhere in this file, hit again.
3. **The most promising fix broke the thing the engine exists for.** Believing the raw field
   where the two readings disagree fixes the end cap and cuts the wall under a carved pocket
   from 5.11mm to 3.54mm. The test suite caught it immediately; without those six tests it
   would have shipped looking like a clean win.

----------------------------------------------------------------------
## 2026-08-15 — narrow cavities: collapse fixed
----------------------------------------------------------------------
Shipped: index.html **d68b59e0**, core.test.mjs **eded7a0f**, fixture-hollow.json 68f75b4a.
Suite **272 passed, 0 failed** (was 269).

- Fixed the narrow-cavity defect recorded last session — and corrected the record, because I
  had it backwards. It is not a material sliver; the CAVITY collapses into air slivers around
  a solid core, so a part reports itself hollow while being solid. Reading the runs properly
  instead of trusting my own note is what found it.
- A 6mm cavity that used to fake being hollow now genuinely opens; a 4mm one that cannot be
  built now closes cleanly to a solid rib.
- Tried widening the rule from one cell to two to catch a remaining end-cap artefact.
  Measured that it broke two cases that were working, and reverted. The artefact stays,
  documented, with a test pinning it at 0.5mm.

----------------------------------------------------------------------
## 2026-08-14 — adaptive wall retired; a narrow-cavity limit found
----------------------------------------------------------------------
Shipped: index.html **541d7fdb**, core.test.mjs **8e4936d6**, fixture-hollow.json 68f75b4a.
Suite **269 passed, 0 failed** (was 265).

- Set out to give the adaptive wall a UI. Checked whether it still worked first, and it did
  not: on a 90mm body with nothing thin about it, it was cutting the wall from 8mm to 5mm.
  Fixed the cause (`reach()` returning its march limit instead of Infinity) and then swept ten
  geometries: **not one clean win**. Retired it, with the numbers in the code and here.
- The wall safety gate is what caught it — a 0.00mm patch over 855 readings on a watertight
  mesh with a healthy median wall. It was built two sessions ago on synthetic cases; this is
  it earning its place on a real one.
- Found and documented a separate limit in the ORDINARY path: a cavity under ~2 cells leaves a
  sub-millimetre sliver. Tried a gate for it, measured that the gate fired where nothing was
  wrong, and reverted rather than shipping a half-fix.

**Two tests of mine asserted things that turned out to be false**, and both were rewritten to
match measured reality rather than loosened: that a thin slab should be thinned (it should be
left solid), and that a plain thin slab has no thin patch (it has a 0.28mm one).

----------------------------------------------------------------------
## 2026-08-13 (later) — Build quality selector
----------------------------------------------------------------------
Shipped: index.html **fa62ab58**, core.test.mjs **55097bc6**, fixture-hollow.json 68f75b4a.
Suite **265 passed, 0 failed** (was 260).

- Added `p.hullQuality` (fast / normal / fine) with a UI selector. Normal is the default and
  is byte-identical to an unset build, so no saved model changes.
- This closes the dead end shipped two sessions ago: a detail too small to build could only be
  reported, never fixed. A 2mm badge on a 200mm car builds 9.29mm proud at Normal and 5.86mm
  at Fine, and the warning now names the step to switch to.
- The report only promises a rescue that exists. A 0.75mm badge is flagged with `fixedBy:null`
  at every step, and the message says no setting can resolve it.
- Tested that Fast/Normal/Fine all still produce watertight, finite-coordinate solids.

**The key implementation detail, in case this is ever revisited:** quality has to scale the
resolution REQUEST, not just the cap. profile_7 asks for 72 and is capped at 80 — raising only
the cap would have shipped a setting that did nothing on the project's own reference model.

----------------------------------------------------------------------
## 2026-08-13 — extra views precomputed into tables (6.8x on many views)
----------------------------------------------------------------------
Shipped: index.html **d5efd672**, core.test.mjs 7c7e7319, fixture-hollow.json 68f75b4a.
Suite **260 passed, 0 failed**.

- Extra views now sample their outline into a distance table once and interpolate, the same
  way the three axis views always have. 60 views: 21.5s -> 3.2s. Answers unchanged to 0.1 cm3.
- Existing models byte-identical across solid, thin wall, thick wall and as-saved.
- Measured before optimising, per the usual lesson — but note the measurement that mattered
  was not a profile, it was knowing the axis views already solved this problem and the extra
  views had simply not been given the same treatment.

**Also corrected a claim I had put in this file myself**: the suite runs that "died without
output" were my launching method, not a fault in the suite. Memory is flat at ~200MB across a
full run. Worth saying plainly, because a note in here saying the tests are unstable would
have sent the next session chasing nothing.

----------------------------------------------------------------------
## 2026-08-12 (later still) — details too small for the grid
----------------------------------------------------------------------
Shipped: index.html **e81a0a98**, core.test.mjs **7c7e7319**, fixture-hollow.json 68f75b4a.
Suite **260 passed, 0 failed** (was 256).

- A feature narrower than about one and a half cells is now reported instead of being built
  wrong in silence. Folded into the existing warning banner rather than adding a second one.
- Wrote two tests on wrong premises and let them fail rather than adjusting the code: raising
  hullRes cannot rescue a small detail (capped at 80), and neither can shrinking the model
  (the cell shrinks too). Both corrections are recorded above, because both are the kind of
  thing that looks like it should work.
- Existing models byte-identical.

**The suite now takes ~10 minutes**, up from ~5 a few sessions ago. Worth trimming: the mesh
audit builds 30 models and the any-angle tests build a sphere many times over.
CORRECTION, next session: the "died without output" part was my own fault, not the suite's. A
plain-backgrounded child is reaped when the shell that started it ends; `setsid nohup ...
< /dev/null` survives. Memory was watched across a full run and is FLAT at ~200MB — there is
no leak. The runtime is real, the instability was not.

----------------------------------------------------------------------
## 2026-08-12 (later) — perspective cameras
----------------------------------------------------------------------
Shipped: index.html **6abe0110**, core.test.mjs **0b4e1ae2**, fixture-hollow.json 68f75b4a.
Suite **256 passed, 0 failed** (was 253).

- `extraViews` entries now accept `from:[x,y,z]` and become real perspective cameras. That
  closes the gap between the carving engine and an actual photograph.
- Verified three independent ways: correct tangent-cone silhouettes land within 0.3% of a
  known sphere at 120/250/600mm; the naive r/D silhouette under-carves by 14.1% exactly as
  predicted; and a 20m lens reproduces the orthographic answer to 0.00 cm3.
- Existing models byte-identical again — everything here is opt-in.

Remaining for real photographs: camera pose (where each shot was taken from) and scale. Both
are solved problems outside this engine — pose by structure-from-motion or by the pipeline
that generated the views, scale by a reference object or a typed dimension.

----------------------------------------------------------------------
## 2026-08-12 — carving from any angle (p.extraViews)
----------------------------------------------------------------------
Shipped: index.html **a520ab54**, core.test.mjs **3806b462**, fixture-hollow.json 68f75b4a.
Suite **253 passed, 0 failed** (was 248).

- Generalised the carve from three axis-aligned views to N arbitrary directions. The rule was
  already right; only the assumption that views are axis-aligned had to go.
- Proved it on a sphere, where the answer is known in closed form: 0 extra views gives 298.6
  cm3 against the three-cylinder theory of 299.9, and it converges monotonically to 267.5 at
  26 views against a true sphere of 268.1. Watertight throughout.
- Existing models are byte-identical — `extraViews` absent means the old path exactly.
- Recorded the architectural limit (a visual hull cannot recover concavities) and the scale
  problem, so neither is discovered late.

This is the geometric groundwork for building from photographs, which was the point of doing
it before any machine learning: the ML generates views, this turns views into a printable
solid, and the second half is the part that has to be right.

----------------------------------------------------------------------
## 2026-08-11 (night, last) — carve engine in the UI, and a verification list
----------------------------------------------------------------------
Shipped: index.html **c557c385**, core.test.mjs fb22fec0, fixture-hollow.json 68f75b4a.
Suite **248 passed, 0 failed**.

- Exposed the carve engine as **How details are cut** under Shape style, with plain-language
  labels. Wired through state, profile, save and load.
- Verified first that `carveMode` only applies in Follow my drawing (makeVisualHull is reached
  only for `mode==="projection"`), so the control hides in Smooth mode rather than offering a
  choice that does nothing.
- Old saved files default to the stamp engine so re-opening a part does not reshape it.
- Added **FOR COLLIN TO CHECK** at the top of this file: a standing list of things verified in
  code and numbers but not by a person using the app. Keep it there; add to it whenever a
  change touches something visual.

----------------------------------------------------------------------
## 2026-08-11 (night, later) — thin-wall warning UI
----------------------------------------------------------------------
Shipped: index.html **36bfa28f**, core.test.mjs **fb22fec0**, fixture-hollow.json 68f75b4a.
Suite **248 passed, 0 failed** (unchanged — this is UI, and the geometry is byte-identical:
profile_7 still 43,768 tris / 309.5 cm3).

- Built the visible half of the safety gate: an amber banner under the readout, hidden unless
  there is a thin patch, plus a **Show me** button that puts the spot in the middle of the
  screen. Position stored in mesh coordinates and converted on click, so a rebuild cannot make
  it stale.
- Reused the app's existing `--warn` colour and stamp border treatment rather than inventing a
  second warning language.
- Suppressed on solid bodies and mid-drag; the whole block is in a try/catch so a warning can
  never be what breaks a build.

**Needs Collin's eyes** — this is the one piece that cannot be verified headlessly. What to
check on the live app: the banner appears on a model with a thin spot and NOT on a healthy
one, the wording reads as a decision rather than a statistic, and Show me actually frames the
right place.

----------------------------------------------------------------------
## 2026-08-11 (night) — wall safety gate detection
----------------------------------------------------------------------
Shipped: index.html **d52fdf16**, core.test.mjs **fb22fec0**, fixture-hollow.json 68f75b4a.
Suite **248 passed, 0 failed** (was 244).

- Built the detection half of Curtis's safety gate: `shellWallStats().worstPatch` clusters
  under-spec readings into regions and reports the worst one with its position. A median could
  not have done this — it reads 5.00mm on a shell with a 2.5mm patch — and neither could
  `min`, which swings 4.91 -> 3.76mm with sample count on a healthy shell.
- No false positives across five healthy shells; correctly flags the 2.5mm patch the stamp
  carve leaves under a pocket, and correctly stays clear on the field carve.
- **Found real thin spots in profile_7**: 0.55mm (field) and 1.04mm (stamp) against a 4.2mm
  request, at the extremities where the traced outline pinches. Worth showing Collin.
- UI not built. Detection is the hard, testable half; the warning itself needs a browser.

----------------------------------------------------------------------
## 2026-08-11 (evening) — zero-area faces fixed, mesh audit added
----------------------------------------------------------------------
Shipped: index.html **1523bdb0**, core.test.mjs **62927c6f**, fixture-hollow.json 68f75b4a.
Suite **244 passed, 0 failed** (was 232).

- Fixed the 94 zero-area faces with an edge-scoped weld: coincident vertices are merged only
  when they already share a triangle edge, so a shell's two sheets can touch without being
  fused. A blind weld made 8 non-manifold edges on a thin wall — caught by the suite, not by
  inspection.
- Tried and reverted two plausible fixes; both are written up above with their measurements
  so they are not re-attempted. The quarter-cell vertex slack and the zero-area faces each
  turn out to be preventing something worse.
- Added `mesh audit:` — 30 combinations of shape, feature kind and carve engine, each checked
  for non-finite coordinates, collapsed faces, zero-area faces, holes and welded sheets.

**Process note:** two of the three "obvious" cleanups in this session made the mesh worse, and
both looked correct on the model I was holding. Checking a fix against a SPREAD of shapes is
what caught them — which is why the audit is a matrix rather than one case.

----------------------------------------------------------------------
## 2026-08-11 (later still) — carveMode toggle, and a NaN defect fixed
----------------------------------------------------------------------
Shipped: index.html **0d02301a**, core.test.mjs **a2938559**, fixture-hollow.json 68f75b4a.
Suite **232 passed, 0 failed** (was 225).

- Added `p.carveMode` ("field" default / "stamp"), so both carving engines are selectable and
  the winner can be chosen later on real parts. Seven `carve mode:` tests keep both honest,
  including that selecting one silences the other.
- **Found and fixed NaN coordinates in the mesh** — 1,488 of them, on any model with a raise,
  present in the shipped 158ee1ed build. `look` clamped its table indices only when growing,
  so a padding-ring sample read `T.d[-3]` and got undefined. Nothing in the suite caught it
  because a NaN vertex still balances every other invariant.
- Also pinned that a pocket may never make the body taller than the plain one.

**Process note:** my first instinct on the NaN was that my probe had hit a degenerate sliver,
and I started making the TEST more robust. Counting the NaNs (1,488) proved it was the mesh.
A test that fails is a claim to check, not a claim to soften.

----------------------------------------------------------------------
## 2026-08-11 (later) — carve green and shipped
----------------------------------------------------------------------
Shipped: index.html **158ee1ed**, core.test.mjs **51cace2f**, fixture-hollow.json 68f75b4a.
Suite **225 passed, 0 failed** (was 217 without carve).

- Fixed the last carve bug: `depth < 0` was rejecting the face itself, because outerAt's
  interpolated crossing returns ~1e-16 rather than a clean zero on a flank that sits exactly
  at the field's y=0. 1694 of `side`'s 2350 samples discarded at one line. All six views now
  carve symmetrically.
- **Established that the volume rise is correct, and that the OLD behaviour was the bug.**
  The vertex-push path leaves 2.5mm of wall under a 3mm pocket in a 5mm-wall shell; the field
  carve keeps 5.1mm. A shell that gets lighter when carved has taken the material out of its
  wall — a weak spot exactly where a detail was drawn, invisible to watertightness and to a
  median wall reading. Three `carved shell:` tests now pin it.
- Verified the featureless path is unchanged from the previous shipped build: 45,316 tris,
  300.6 cm3, watertight.
- Build time on a heavily-featured model is ~20s vs 3.4s. Accepted deliberately for now.

**Process note:** the bug was found by counting rejections at each gate per view, not by
reading code. The gates were innocent; the march rejected 86% for one view and 37% for
another, which pointed straight at the culprit. Also: a logger that rounds to 2 decimals will
print a -1e-16 as "0" and hide exactly this class of bug.

----------------------------------------------------------------------
## 2026-08-11 — carve: six bugs fixed, face-locality tests added, one live bug left
----------------------------------------------------------------------
Deploy trio UNCHANGED and still green: index.html **9d317df1**, core.test.mjs **65dcc705**,
fixture-hollow.json 68f75b4a, **217 passed 0 failed**. Carve work is in the container at
/home/claude/work/cvt at 218/222 — see the CARVE section for the full list.

- Fixed six bugs in the carve path; the largest was a front-view pocket carving the ENTIRE
  model because the march took the nearest surface along the cut axis rather than the
  outermost. Replaced with a cached per-line outer-surface scan.
- **Added five `face-local:` tests**, on a saddle fixture (roof 60mm, floor 21mm, both
  visible from above) that reproduces the arch problem in miniature. They found bug 5 on
  their first run. This closes the gap where the suite passed 217/217 while a feature was
  carving the whole model.
- Rewrote three `detail:` tests whose `dent` helper binned mesh VERTICES by cell and took the
  extreme — it could not see a pocket at all (a perfect 4mm pocket read 0.00mm) and could not
  tell a pocket from a whole face moving. Replaced with ray casting plus volume.
- Performance: counted rather than guessed. 68 MILLION bodyAt calls from 2.4M marches, 28
  evaluations each. d0 is a true signed distance so the face is bracketed — bisection gives
  the same answer in 14 calls. Feature pass 18.1s -> 7.0s.

**Measurement mistakes made this session — all cost real time, all worth avoiding:**
- Judging a pocket by the extreme surface per column. It cannot distinguish a pocket from a
  moved face; it reported a 4mm pocket as a 60mm through-cut and later as 0.00mm. Volume and
  a single ray settled it in one call each. Prefer them.
- A test that flagged "33.60mm movement" was measuring a vertical step shifting sideways as
  the wall was correctly cut back. The sign is the tell: a pocket only ever REMOVES, so only
  downward movement is a depth.
- Coarse sampling missed 213 lines whose visible face is shallower than x=120 (the wheels,
  genuinely visible from the nose), and nearly led to "fixing" correct behaviour.
- An edit that produced BYTE-IDENTICAL output was treated as a too-small fix rather than as
  proof the code path never ran. It had not applied. Check that first, every time.
- Matching arithmetic is not evidence. A 1mm error on a 2mm grid looked exactly like
  half-cell snapping; it was not, and a direct test disproved it immediately.

----------------------------------------------------------------------
## 2026-08-10 (later still) — outline fidelity
----------------------------------------------------------------------
Shipped: index.html **9d317df1**, core.test.mjs **65dcc705**, fixture-hollow.json 68f75b4a.
Suite **217 passed, 0 failed** (was 213).

- Fixed `resamplePoly`, which thinned traced outlines by list index and moved corners up to
  3.33mm. Now Douglas-Peucker bisected onto the budget: exact, and with fewer points.
- Built a trustworthy outline-fidelity probe and validated it against known answers. The
  mesher is good — 0.001-0.002mm on test shapes, 0.075mm mean on profile_7 with a closed
  bottom. Earlier reports of ~1.2mm and ~8.4mm errors were both my own measurement faults,
  recorded above so they are not chased again.
- No geometry or performance change to existing models; the fix only affects outlines that
  exceed the point budget, which is the DXF case.

----------------------------------------------------------------------
## 2026-08-10 (later still) — fins solved
----------------------------------------------------------------------
Shipped: index.html **661f15aa**, core.test.mjs **2d8f493b**, fixture-hollow.json 68f75b4a.
Suite **213 passed, 0 failed** (was 210).

- Solved the long-standing bad-directed-edge item. It was not a winding bug: the surface was
  genuinely non-orientable, proven by a union-find parity test that found 275 odd-cycle
  conflicts. The winding pass had been correctly refusing an impossible job all along.
- Root cause: single-vertex dual contouring welds two sheets wherever a shell pinches, either
  at a thin wall or a thin cavity. Fixed by detecting ambiguous cells via corner-sign
  connectivity and resolving them towards material.
- Wall thickness, width accuracy and orientability all improved together; cost is +1.4%
  material, a thicker p90 wall, and ~0.4s of build time.
- Added three `no fins:` tests. Recorded that boundary/non-manifold counts cannot detect this
  class of defect, so the parity test belongs in any future mesh check.

----------------------------------------------------------------------
## 2026-08-10 (later) — carve forward-port
----------------------------------------------------------------------
Produced `WIP-do-not-deploy/carve-port-WIP.html` **7cb474a7**, 206/210. **Not shipped.**
The deploy trio is unchanged: index.html **db59792c**, core.test.mjs **c5a9e013**,
fixture-hollow.json **68f75b4a**, still 210/210.

- Ported `carve-wip-641002b6` (based on repo build f3a43b5e) onto db59792c by **three-way
  merge**, zero conflicts. A first attempt to apply the five hunks by line number failed —
  the offsets shift cumulatively and the arithmetic mangled the file. Use
  `git merge-file <current> <base> <wip>`; do not hand-roll it.
- **Corrected the previous handoff's assessment of the 5 red carve tests.** They were said to
  encode old surface-stamp behaviour needing honest rewriting. They were reporting a real
  bug: carve depth was measured from the sampling box rather than the body, so every pocket
  was short by the body-to-box clearance and shallow ones vanished entirely (2mm ask -> 0.00mm
  cut on a block with 3mm of clearance). Fixed by referencing depth to the body field
  (`-d0`, captured before any feature on the pass). Pockets now cut 2.00 / 4.00 / 6.00mm
  exactly at res 44 and 80. Same fix applied to `maskHold`.
- Suite 203/210 -> 206/210. The 4 remaining reds are diagnosed and categorised in the CARVE
  section; two are the raise band reaching past D because the hull field's gradient is not 1,
  one is a genuine design question about whether a carve on an extremity may reduce the
  model's overall length, one is undiagnosed.
- Nothing was rubber-stamped. No carve test was edited.

----------------------------------------------------------------------
## 2026-08-10 — field hollow ON by default, wall reporting, adaptive wall rebuilt
----------------------------------------------------------------------
Shipped: `index.html` **db59792c**, `test/core.test.mjs` **c5a9e013**,
`test/fixture-hollow.json` **68f75b4a**. Suite **210 passed, 0 failed**.
Intermediate build **805fd16a / 2b1c2f90** at 205 green is superseded.

**Diagnosis**
- Established the plank is a **deletion, not an addition**. Rendered the deck cross-section
  against a solid reference: solid is a full-width slab z 44.9->56.1; the old build kept only
  z 53.3->56.1 and dropped the underside entirely. Field hollow restores it as a closed box.
- Therefore the "solid fraction below 14.5%" win condition was **scoring missing geometry**.
  Retired it. The fixed build correctly holds MORE material (183 -> 253 cm3).
- Corrected "always verify at res 80": profile_7 has 72 stations so its real resolution is
  **72**. Building at the profile's own default reproduced the locked repro exactly
  (37,368 tris / 24,176 verts / 183.0 cm3). Forcing 80 gives a different mesh — this is why
  detectors kept giving false all-clears.
- Proved the wall shortfall is **discretisation, not a field error**: converges 3.81 -> 4.03
  -> 4.15mm at res 72/110/160. Added no fudge factor as a result.

**Built**
- Shell field rewritten to `max(b, -(dist+wall))` — only the INNER term gradient-normalised.
  Step 2 normalised both, which slid the mesher's edge interpolation and moved the outer skin
  0.3mm (0.9mm with a coarser gradient). Outer skin is now the solid build's, untouched.
- Gradient computed only in the wall band (skipped outside the body and deep in the core).
- `p.fieldHollow` now defaults ON. `fieldHollow:false` still reproduces the legacy build
  byte-for-byte (37,368 tris / 183.0 cm3 on profile_7).
- `HOLLOW_WALL_CELLS = 1.45` adequacy gate — below it the shell self-cancels; falls back to
  the vertex-offset path.
- `shellWallStats()` — measures the wall that will actually print, marching in along each
  face normal, with an optional height band for the rim. 167ms on 46k tris. Foundation for
  Curtis's gate.
- `makeVisualHull` now returns `fieldHollow` and `hullRes`.
- **Adaptive wall rebuilt** on bilateral thickness, `p.adaptiveWall`, default OFF, plus
  `HOLLOW_THIN_CELLS = 2.0`. See the STEP 3 section above for measurements.
- Test suite: async runner (`PENDING[]` + `Promise.all`), 8 point-cloud tests, 5 field-hollow
  tests, 3 wall-report tests, 5 adaptive-wall tests, 11 new names in `NAMES`.

**Tried and REMOVED — do not re-add without reading this**
- A resolution auto-raise when hollowing. The solid build kept the original resolution, so
  merely ticking "hollow" moved the outside half a millimetre — the exact invariant being
  protected. And where the wall was far too thin the grid climbed to the cap, cost ~7x the
  build time, and was rejected by the gate anyway. Gone.
- The bilateral adaptive wall was **designed, measured, and initially withheld** on the
  grounds that it trades strength for material. Rebuilt on request, flag-gated OFF, with the
  trade documented rather than decided silently.

**Honest regressions / gaps introduced this session**
- Rim test coverage is thinner. Old version read `vc = P.length/6` (vertex-offset layout) and
  reported a 4.2mm rim as 111mm on a dual-contoured mesh. Rewritten to measure geometrically
  on both paths, but the "wander" half needed a rim ring a closed mesh does not have. Flagged
  in the test file rather than left as a green tick over nothing.
- Bad directed edges on profile_7 went 42 -> 61 with the new shell field. Still unexplained.

**Process failure worth remembering**
- Spliced the test file by searching for the next `t(`. That ate a block opener and the shared
  `dent` / `blockProfile` helpers, and surfaced only as a syntax error hundreds of lines away.
  Rebuilt from the pristine repo copy with every edit re-applied brace-aware. Edit by unique
  anchor or with a brace matcher; never by "next occurrence".

**Repo state found at session start**
- `LEE3D-Frontend/index.html` was **f3a43b5e** — the pre-point-cloud build. All ten
  point-cloud functions absent. Committed suite was the old 189-test version with zero
  point-cloud references. `fixture-hollow.json` WAS correctly committed (68f75b4a).
- The 197-test suite from the previous handoff exists nowhere; the suite here is a
  reconstruction from the 189-test version, not a recovery.
- Backend and Lib: checked, no action needed this session.

----------------------------------------------------------------------
## Earlier sessions (undated — predate this log)
----------------------------------------------------------------------
- **Field-hollow session.** Diagnosed the plank; built field-hollow steps 1/2/3 behind a flag
  defaulting OFF; `dropTinyShells` added because `dropStrayShells` keeps a fixed count of
  components and was discarding the inner wall (773 cm3 solid lump). Locked the profile_7
  repro. Steps 1 and 2 sound; step 3 regressing.
- **Point-cloud session.** `.PLY` (binary + text), `.XYZ`, `.PCD`, both directions, format
  auto-detection, density selector, Three.js point display. Round-trip on a real car body:
  24,176 points, 283KB binary PLY, zero coordinate error. Shipped as f3b6d1d4 — but see
  above, it never reached the repo.
- **Deploy-unblock session.** `fixture-hollow.json` was never committed, so the four hollow
  tests hard-failed, CI exited 1, and Pages kept serving an old build.
- **Backend session.** Render blueprint pointed at a `./Dockerfile` that never existed; STEP
  export always returned solid because the planner read `sepBottom` instead of `hullHollow`
  and `/solid`'s `hollow` parameter defaulted false and was never sent by the frontend.
- **Carve session.** Pockets rebuilt as real field prisms with flat floors at exact depth.
  `carve-wip-641002b6.html`, 184/189 green, 5 red tests encoding old surface-stamp behaviour.
  Still parked, still pre-point-cloud.
