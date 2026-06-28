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
from pydantic import BaseModel, Field


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
    archLift: float = 1.0

    topProfile: List[Point]
    bottomProfile: List[Point]
    widthProfile: List[Point]
    # Optional normalized cross-section from a front view: [x_fraction, z_fraction] pairs.
    # Accepted for round-trip + storage; the CadQuery generator currently lofts its own
    # section, so this is forward-compatible metadata (used by the browser studio today).
    section: Optional[List[Point]] = None
    mode: Optional[str] = None              # 'loft' | 'projection' (studio reconstruction method)
    frontHull: Optional[List[Point]] = None # absolute-mm front silhouette for projection mode
    wheels: List[Wheel] = []
    wheelLayout: Optional[WheelLayout] = None

    class Config:
        populate_by_name = True


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
