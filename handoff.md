# LEE3D — HANDOFF

Read this first, then `STATUS.md`. This is the operating manual and the live state;
`STATUS.md` is the reasoning record and is far longer. Where they disagree, `STATUS.md` is
right about *why* and this is right about *now*.

---

## 1. WHAT THIS IS

LEE3D turns 2D orthographic views into printable 3D models. Two ends that must agree:

- **LEE3D-Frontend** — `index.html`, the whole studio in one file. Browser-only, no backend
  needed. Builds on a voxel grid: fast, always watertight, approximate.
- **LEE3D-Backend-A** — FastAPI + CadQuery/OpenCascade. Exact B-rep, exports STEP and STL.
- **LEE3D-Lib** — the schemas both ends read, plus `check_schema_coverage.py`, which verifies
  that every `x-read-by` claim in a schema is true of the actual source.

**The core discipline of this project: the two ends must not disagree about the part.** Most of
the bugs in `STATUS.md` are one end quietly building something different from the other.

---

## 2. CURRENT FILE MANIFEST — verify these before touching anything

    LEE3D-Frontend/index.html                      2ec42560
    LEE3D-Frontend/test/core.test.mjs              da8bf2ac
    LEE3D-Backend-A/app/hull.py                    8d7a6e0d
    LEE3D-Backend-A/app/main.py                    91536f59
    LEE3D-Backend-A/app/schemas.py                 ac7d7611
    LEE3D-Backend-A/app/pdf_import.py              70a44f01
    LEE3D-Backend-A/app/cad.py                     a1ce4b21
    LEE3D-Backend-A/tests/test_hull.py             f64df4f3
    LEE3D-Backend-A/tests/test_deploy.py           96b345ed
    LEE3D-Backend-A/tests/test_schema_contract.py  eba4d6fd
    LEE3D-Backend-A/tests/test_pdf_geometry.py     e1fc7cb5
    LEE3D-Backend-A/tests/test_cad.py              a5d53a3e
    LEE3D-Backend-A/conftest.py                    75d923b5   (repo ROOT, not app/)
    LEE3D-Backend-A/requirements.txt               62d4dba6
    LEE3D-Backend-A/.github/workflows/ci.yml       (rewritten 2026-09-21 — see STATUS)
    LEE3D-Lib/schema/profile.schema.json           a22798fa
    LEE3D-Lib/schema/sheet.schema.json             1cc234fa
    LEE3D-Lib/tools/check_schema_coverage.py       32e2bae1

**Audit every one of these against the uploaded zips before the first edit.** A previous
session rebuilt from memory after a container reset and silently dropped a shipped feature.
If one differs, say so and stop — it means a ship did not land, which has happened twice.

---

## 3. ENVIRONMENT — do these two things immediately after unzipping

```bash
pip install cadquery --break-system-packages     # plain pip is refused here (PEP 668)
cd repos && ln -s LEE3D-Lib-main LEE3D-Lib       # and Frontend, Backend-A
```

The zips extract as `LEE3D-Lib-main`; the tests look for `LEE3D-Lib` **beside** the backend.

**Without both, nineteen tests skip and a skip reads as a pass in the summary line.** A
previous session shipped schema changes for several turns with the schema contract tests
silently skipping and reported "98 passed" the whole time.

**And until 2026-09-21 the repo's own `ci.yml` had the same gap** — it checked out one repo, so
ten tests skipped on every push and CI reported `114 passed`. Both jobs now check out all three
and a step fails the build if the schema contract or the studio-vs-backend tests skip. If you
ever see those two skip locally, the sibling layout above is wrong; that is the whole of it.

    wrong setup    98 passed,  20 skipped
    right setup   124 passed,   1 skipped, 1 deselected

The one legitimate skip is a clean-error path that can only be exercised *without* OpenCascade.

---

## 4. HOW TO RUN THE GATES

**Backend** (~20s):
```bash
cd LEE3D-Backend-A-main && python3 -m pytest -q --deselect tests/test_cad.py::test_generate_stl_full_resolution
cd repos && python3 LEE3D-Lib-main/tools/check_schema_coverage.py \
  --schema LEE3D-Lib-main/schema/profile.schema.json --profiles LEE3D-Lib-main/schema \
  --frontend LEE3D-Frontend-main --backend LEE3D-Backend-A-main
```

`test_generate_stl_full_resolution` is ~290s as a single test and **cannot** fit a tool call.
`test_generate_stl_fast` covers the same path at 16/12 in ~10s. Note the rename: pytest
`--deselect` matches node ids by PREFIX, so the old shared prefix deselected both.

**Frontend** — 290 tests, too slow to run whole. Copy to a scratch dir, inject a slice guard,
run in seven slices:

```
0:84  84:164  164:184  184:204  204:234  234:259  259:300
```

(These moved by 4 on 2026-09-21: four tests were added at indices 28-31, ahead of every old
boundary. Re-derive them whenever tests are added early in the file, or a slice silently covers
the wrong tests.)

Slice `164:184` is the slow geometry one (~150-250s) — give it its own call with `timeout 280`.
Others take 10-120s; pair them at most two per call or you will hit the 300s command ceiling.
The scratch copy needs `index.html` symlinked beside `test/`. **Never ship the sliced copy** —
the slice guard is a scratch hack.

**Always total the slices and compare against `t_calls=N`** printed by the guard. That is what
catches a test silently not running.

---

## 5. WHERE THE WORK IS: reading construction drawings

The last stretch of work was making the app read real construction PDFs instead of making
someone retype what the drawing already says. Collin's rule, in his words:

> manual input for PICTURES, never for information (words, measurements, gradings)

Test file: `Drawings.pdf` — ELM Studio, Saratoga Springs / Cathedral Oak Parkway, 8 pages,
16.4 MB. Sheets L201B, L301B, L400, L403, L404, L405, L406. **Every sheet is rotated 270.**

### What works, measured on that real file

    page 0  L201B   48,932 strokes   1:240   21 dimensions   10 survey points
    page 4  L403    16,234 strokes   1:96    17 dimensions
    page 5  L404    59,794 strokes   1:48    92 dimensions   10 titled details
    page 7  L406   163,293 strokes   1:48    93 dimensions    9 titled details (1:48 AND 1:32)

- **Imperial dimensions and scales** — `4'-0"`, `12'-4"`, `42'-1¾"`, `1/4" = 1'-0"`. The
  importer previously understood only metric `1:200`, so Dylan's entire set read as nothing.
- **Dimensions linked to line work by ARITHMETIC, not proximity** — a line drawn L mm at 1:S
  measures L×S, and the text says what that should be. A match is a check.
- **Per-detail scales** — L406 mixes 1:48 and 1:32; measuring its wayfinding sign at the sheet
  scale made six dimensions *vanish*, not merely be wrong.
- **Scale inference** from the line work when no scale is printed.
- **Survey schedule** — all ten northings/eastings exact, and `survey_span` reproduces the
  hand reduction (50.8405 ft, bearing 104.1526°).
- **Frame segmentation** — the sheet draws an exact 181.0 × 368.3mm grid; 160,438 of 163,293
  strokes assign to a frame, 9 of 9 details placed.
- **`render_detail`** — one detail cropped for tracing, right way up.
- **Endpoints** — `POST /import/pdf/sheet` and `POST /import/pdf/detail`. Both index the
  SAME list, `sheet["details"]`; a detail the sheet never boxed 404s by name rather than
  returning the next one. This has now been got wrong twice, in opposite directions.
- **Studio** — a dropped PDF is read, its details listed and tappable, the chosen one loaded as
  a trace reference at the scale it was drawn at.

### What cannot be done, and why — do not spend a session on it

**A construction detail is not a picture of one object.** Measured on L406: the drawn ink
covers 152 × 184mm while the column is 25.4 × 78.3mm — six times the object's area — because
the frame holds the column *plus* its footing, the finished grade and the compacted subgrade.
74% of strokes are under 0.5mm (stone hatch). Which part is "the object" is a judgement the
geometry does not carry.

So **the trace stays**. What changed is everything around it: one framed detail at its own
known scale, dimensions already read, instead of a 725 × 952mm sheet.

---

## 6. THE ONE OPEN DECISION — pick this up first

`profileScaleFromTrace()` in `index.html` is written and tested. It turns a trace into a real
size — a traced 4'-0" × 12'-4" column reads 1219.2mm and 3759.4mm. **Nothing calls it.**

The association is plain in the source, at the crop-to-view assignment:

```js
for(const bx of pg.boxes){                    // pg IS the page, which carries pg.drawing
  const {canvas,cf,topPts,botPts}=cropToViewTrace(bx);
  const view=V[role];
  setRefImage(view,canvas); view.scale=sPxPerMm*cf;
```

`view.drawing = pg.drawing` would carry it. **One line, and it would be silently wrong.**

`cropToViewTrace(bx)` calls `cropCanvas(bx)`, which crops a **box** out of the page — so a
view's traced points are in the BOX canvas, while `drawing.crop.frame_mm` describes the whole
PAGE crop. Measuring the trace as a fraction of the box and multiplying by the page's paper
size makes a building covering a third of the page come out **three times too small**.
Plausible, and nothing downstream can tell.

**Two fixes, and Collin has been asked to choose:**

1. Convert traced points to PAGE coordinates (box offset, then `cf`) and pass the page image
   size. One basis throughout; larger change.
2. Scale `frame_mm` by the box's fraction of the page. Smaller; leaves two bases alive in the
   code, which is how this class of bug recurs.

Either needs the box rect carried alongside the drawing record.

---

## 7. NEEDS A HUMAN — cannot be settled by code

1. **Item 0c in `STATUS.md`** — a car in Workshop with its bottom plate. `makeBottom` lays the
   plate at `-L/2..L/2` while the projection body spans `0..L`, half a length out. Workshop now
   applies the studio's rule so the plate should be *absent*. If it was visibly there and
   correct, the arithmetic is wrong somewhere and that change should be reverted.
2. **The picker panel** — whether it sits sensibly over the sheet. Needs a drop of
   `Drawings.pdf` on a real device with a backend address set.
3. **Carve-mode default.** `carveMode` is studio-only — measured, the backend gives 88.654 cm³
   regardless. So it is a PREVIEW choice, not a fidelity one, and the STEP is identical either
   way. `field` is closer to the export but has 86 badly-wound edges; `stamp` is clean but
   overstates material removed by ~2.7×. Neither affects what prints.
4. **`test_cad.py` full resolution** — CI only, and it has **not** run against the lathe
   changes in `hull.py`. Last confirmed green at the older `3d50756e`.
5. **A thick-floor part with the underside open.** The 2026-09-21 fix removes a floating slab
   that the exact build used to leave whenever the floor was thicker than the cavity
   (`3*wall > height` uniform, `2*bottom + top > height` per face). It is measured on a ray and
   pinned by a test, but nobody has looked at such a part on screen or printed one. Anything
   short and thick-walled is the case to try.
6. **A PDF whose details are not all boxed.** `/import/pdf/detail` now refuses an unboxed detail
   by name instead of handing back its neighbour's drawing. Worth one drop of a real sheet to
   see that the refusal reads sensibly in the picker.

---

## 8. HOW TO WORK HERE — the rules that keep being relearned

These are distilled from `STATUS.md`. Every one cost a session.

**Measure, do not assume.**
- Check whether something already exists before building it. Workshop got two bugs from
  reimplementing decisions the studio had already made. `pdf_import.py` already existed with
  most of what was needed.
- Publish a cause only after a disconfirming test. "Features that touch the view edge cause
  the bad winding" was falsified by removing them and getting *more*.
- Ask what a measurement is invariant under before believing it. A whole-file 304.8mm offset
  was invisible to lengths, spans, proximity, framing, error percentages and even whether a
  crop contained ink. **Only an absolute check found it.**
- Time nothing on a kernel's first call. OpenCascade init made "no wheels" look 8× slower.

**Tests must be able to fail.**
- Mutate the code and watch the test go red. Several tests here passed their first mutation
  and proved nothing.
- A fixture must reproduce the geometry that CAUSED the bug, not merely its shape. Six
  separate fixtures have now failed this: a decoy ranked by the term under test, a sheet number
  listed first so first-seen and largest agreed, 20mm of clearance that made 12mm padding
  harmless, a 5mm wall on a 40mm block that could not show a sweep overshooting its cavity, a
  one-detail sheet that could not show a filter dropping one, and a frame in the middle of the
  page that could not show a clip truncated at its edge. The question is not "is this the right
  kind of object" but "does this one actually reach the branch".
- Ask what a fix at ONE end leaves true at the other. The PDF index bug was reintroduced by its
  own fix: the listing gained a frame per detail and the endpoint kept filtering on it.
- A test for a string's ABSENCE is fooled by a comment describing that string. Prefer a
  positional or behavioural check.
- `t()` blocks, `h()` only warns. Using `h()` for something that must block means it ships.

**Ship whole.**
- When two files must change together, ship them together. A feature and its test are one
  change; twice a pair half-landed and left live code unguarded for turns.
- Never ship a no-op behind a comment claiming a fix. One was reverted for exactly this, and
  `build_lathe` carried another for months: `inner.translate((0, 0, -drop * 0.0))`.
- **A fix applied in the container is not applied in the repo.** The nineteen-skips finding was
  fixed by making symlinks and left unfixed in `ci.yml`, where it went on happening on every
  push. When an environment problem bites, ask which of CI, the repo and the container it
  actually lives in.
- **A stale instruction is worse than a missing one.** "cadquery is not pip-reliable" was
  corrected in one of four files and cost this project months of unchecked geometry from the
  other three. When a claim is corrected, grep for it.
- A segmentation or an answer that is *roughly* right is worse than none when nothing
  downstream can detect the difference.

**JavaScript specifics.**
- An invented helper parses perfectly and fails only when it runs. `apiBase()`, `backendOn()`,
  `escapeHTML()` were all invented in drafts. There is now a test asserting every helper the
  import path calls is defined — use it.
- Untrusted strings go in with `textContent`. This app never builds HTML around them.

---

## 9. DELIVERY FORMAT Collin expects

- Never attach zipped folder exports.
- Show only changed files, inline, each with its `Repo / path` and md5.
- **Always ship `STATUS.md`**, even on a turn where it did not change.
- Keep responses tight.
- Clearly separate what was statically verified from what needs visual confirmation. He has an
  industrial design background and will catch a geometric approximation.
