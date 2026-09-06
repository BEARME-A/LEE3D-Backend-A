"""
LEE3D shared data contract.

The `Profile` model below is the SINGLE source of truth that flows between the
three repos:

    LEE3D-Frontend  --(exports profile.json)-->  LEE3D-Backend-A
    LEE3D-Backend-A --(generates STL/STEP)----->  LEE3D-Lib

Field names match the JSON the browser app writes, byte-for-byte, so a profile
exported in the UI drops straight into `POST /generate`.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


Point = List[float]  # [x_fraction (0..1), value_in_mm]


class Wheel(BaseModel):
    x: float = Field(..., description="Axle X position in mm, measured from body centre")
    z: float = Field(..., description="Axle centre height in mm")
    r: float = Field(..., gt=0, description="Wheel radius in mm")
    width: float = Field(26.0, gt=0, description="Wheel width in mm (for the boolean cutter)")


class WheelLayout(BaseModel):
    wheelbaseFrac: float = 0.62
    track: float = 62.0
    radius: float = 16.0
    width: float = 26.0
    rideHeight: float = 13.0


class Profile(BaseModel):
    schema_: str = Field("lee3d.profile/v1", alias="schema")
    units: str = "mm"
    name: str = "untitled-body"

    length: float = Field(180.0, gt=0)
    stations: int = Field(72, ge=8, le=400)
    arcSegments: int = Field(56, ge=8, le=400)
    roofFlatness: float = 1.4
    wallThickness: float = Field(1.8, gt=0)
    # SCALE. Both optional and neither touches geometry: `length` stays the model size that
    # everything is built from, so a profile without these behaves exactly as it did. They
    # exist because a building cannot be expressed as a model dimension alone — an architect
    # works at 1:100 or 1:200 and the model size FOLLOWS from the real size. Without somewhere
    # to keep the real figure it is lost the moment the model length is typed in.
    # A TURNED OBJECT. "lathe" revolves the side elevation about the vertical axis — the only
    # way to build a fountain or a column, because a visual hull comes out 36% out of round
    # (all but a square) anywhere the body narrows below its widest plan circle.
    shape: Optional[str] = None
    revProfileV: Optional[List[List[float]]] = None     # [[height fraction, radius mm], …]
    revHeight: Optional[float] = Field(None, gt=0)      # tall, in mm — NOT length, which is the diameter
    realLength: Optional[float] = Field(None, gt=0)     # the real thing, in mm. 24m -> 24000
    modelScale: Optional[float] = Field(None, gt=0)     # denominator: 200 means 1:200
    archLift: float = 1.0

    topProfile: List[Point]
    bottomProfile: List[Point]
    widthProfile: List[Point]
    # Optional normalized cross-section from a front view: [x_fraction, z_fraction] pairs.
    # Accepted for round-trip + storage; the CadQuery generator currently lofts its own
    # section, so this is forward-compatible metadata (used by the browser studio today).
    section: Optional[List[Point]] = None
    # Cross-section cuts {at, prof:[[t,zNorm]], src} morphed along the length. This field
    # exists in LEE3D-Lib's copy of the contract and was missing here, which is precisely
    # the drift the docstring above says must not happen.
    sections: Optional[list] = None
    mode: Optional[str] = None              # 'loft' | 'projection' (studio reconstruction method)
    frontHull: Optional[List[Point]] = None # absolute-mm front silhouette for projection mode
    wheels: List[Wheel] = []
    wheelLayout: Optional[WheelLayout] = None

    # ---- THE TRACED SHAPE, and everything carved into it -------------------------------
    # These were the fields the comment below is about: the ones that got silently deleted.
    # Naming them does three things — the auto-generated API docs describe a real profile,
    # `extra="allow"` stops being the only thing protecting the traced shape, and the schema
    # coverage checker in LEE3D-Lib stops reporting 40 undeclared keys.
    # All Optional with a None default, because ABSENT and NULL must mean the same thing here.
    # Verified, not assumed: `_hollow_wanted` returns True for hullHollow absent, hullHollow
    # null, and both null together — the sepBottom/hullHollow trap described below does not
    # reopen by declaring these.
    sidePoly: Optional[List[Point]] = None      # side silhouette, 0..1 of length by 0..1 of height
    sidePolyR: Optional[List[Point]] = None     # right flank when it differs; None = symmetric
    topPoly: Optional[List[Point]] = None       # plan silhouette
    frontPoly: Optional[List[Point]] = None     # front silhouette
    bottomPoly: Optional[List[Point]] = None    # underside silhouette
    extraViews: Optional[List[dict]] = None     # silhouettes from arbitrary angles (photo path)
    features: Optional[List[dict]] = None       # carved details: -depth cuts, +depth raises
    carveMode: Optional[str] = None             # "field" | "stamp"

    # ---- hollowing ---------------------------------------------------------------------
    hullHollow: Optional[bool] = None           # None means "ask sepBottom", see _hollow_wanted
    wallThickness: Optional[float] = None
    wallPerFace: Optional[bool] = None
    wallTop: Optional[float] = None             # the load-bearing control: a thick floor to
    wallSide: Optional[float] = None            # bolt through with thin walls elsewhere
    wallBottom: Optional[float] = None
    closedBottom: Optional[bool] = None
    openArches: Optional[bool] = None           # older name for openUnderside; both are written
    openUnderside: Optional[bool] = None
    fieldHollow: Optional[bool] = None
    adaptiveWall: Optional[bool] = None         # retired; honoured so older files load unchanged

    # ---- build settings ----------------------------------------------------------------
    hullCrisp: Optional[float] = None           # 0 = smooth body, 1 = exactly the traced outline
    hullRes: Optional[int] = None
    hullQuality: Optional[str] = None           # "fast" | "normal" | "fine"
    hullFast: Optional[bool] = None             # set only mid-drag; never saved deliberately
    noDetail: Optional[bool] = None
    sepBottom: Optional[bool] = None
    category: Optional[str] = None
    sculpt: Optional[List[float]] = None
    sculptStrokes: Optional[List[dict]] = None

    # KEEP WHAT WE DON'T UNDERSTAND.
    # pydantic's default is extra="ignore", so every field this model doesn't name was
    # dropped on the way in: sidePoly, sidePolyR, topPoly, frontPoly, bottomPoly, features,
    # hullCrisp, hullHollow, openUnderside, wallTop/wallSide/wallBottom, sculpt — the entire
    # traced shape, in other words. Nothing errored; the fields simply weren't there any
    # more. /generate then wrote that stripped object into the versions table via
    # model_dump_json, so restoring a saved version handed back a model with no tracing in
    # it. The studio moves faster than this file, so the contract has to carry fields it
    # hasn't been taught yet rather than quietly delete them.
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class GenerateOptions(BaseModel):
    """Controls for the CadQuery generator (the 'production' body)."""
    fmt: str = Field("stl", pattern="^(stl|step)$")
    open_bottom: bool = True            # shell out the underside for a body shell
    cut_wheels: bool = True             # boolean-cut true wheel openings
    section: str = Field("super", pattern="^(ellipse|super)$")  # cross-section style
    commit_to_library: bool = False     # also push the result into LEE3D-Lib
    project_id: Optional[int] = None


class ProjectIn(BaseModel):
    name: str
    notes: str = ""


class CommitFile(BaseModel):
    """A single file to write into the LEE3D-Lib repo via the GitHub API."""
    path: str = Field(..., description="Repo-relative path, e.g. 'drawings/charger/side.png'")
    content_base64: str
    message: str = "LEE3D: add file"
