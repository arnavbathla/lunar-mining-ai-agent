"""Lunar site service: generation, mineability, and placement helpers."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LunarSite, Mission
from app.simulation.site_generator import (
    GRID_H,
    GRID_W,
    compute_mineability,
    generate_site,
    grid_stats,
)


def get_site_for_mission(db: Session, mission_id: str) -> Optional[LunarSite]:
    return (
        db.execute(select(LunarSite).where(LunarSite.mission_id == mission_id))
        .scalars()
        .first()
    )


def create_or_replace_site(
    db: Session,
    mission: Mission,
    seed: int = 42,
) -> LunarSite:
    """Generate a fresh site for a mission, replacing any prior site."""
    cells = generate_site(
        seed=seed,
        width=GRID_W,
        height=GRID_H,
        max_slope_deg=mission.max_slope_deg,
    )

    existing = get_site_for_mission(db, mission.id)
    if existing:
        db.delete(existing)
        db.flush()

    site = LunarSite(
        id=str(uuid.uuid4()),
        mission_id=mission.id,
        name="Synthetic Polar Site",
        region="south_pole",
        grid_width=GRID_W,
        grid_height=GRID_H,
        cells_json=cells,
    )
    db.add(site)
    db.flush()
    return site


def _cells_with_min_mineability(
    cells: List[Dict[str, Any]], threshold: float
) -> List[Dict[str, Any]]:
    return [c for c in cells if c["mineability_score"] >= threshold]


def _enforce_min_distance(
    candidates: List[Dict[str, Any]], min_dist: float = 3.0
) -> List[Dict[str, Any]]:
    chosen: List[Dict[str, Any]] = []
    for cell in candidates:
        if all(
            ((cell["x"] - c["x"]) ** 2 + (cell["y"] - c["y"]) ** 2) ** 0.5 >= min_dist
            for c in chosen
        ):
            chosen.append(cell)
    return chosen


def top_dig_zones(
    cells: List[Dict[str, Any]], k: int = 3
) -> List[Dict[str, Any]]:
    sorted_cells = sorted(
        cells, key=lambda c: c["mineability_score"], reverse=True
    )
    spread = _enforce_min_distance(sorted_cells, min_dist=4.0)
    return spread[:k]


def hazard_zones(
    cells: List[Dict[str, Any]], threshold: float = 0.65
) -> List[Dict[str, Any]]:
    flagged = [c for c in cells if c["hazard_score"] >= threshold]
    flagged.sort(key=lambda c: -c["hazard_score"])
    return _enforce_min_distance(flagged, min_dist=3.0)[:8]


def comms_risk_zones(
    cells: List[Dict[str, Any]], threshold: float = 0.30
) -> List[Dict[str, Any]]:
    flagged = [c for c in cells if c["comms_quality"] <= threshold]
    flagged.sort(key=lambda c: c["comms_quality"])
    return _enforce_min_distance(flagged, min_dist=3.0)[:6]


def _cell_at(cells: List[Dict[str, Any]], x: int, y: int) -> Optional[Dict[str, Any]]:
    for c in cells:
        if c["x"] == x and c["y"] == y:
            return c
    return None


def processor_placement(
    cells: List[Dict[str, Any]],
    dig_zones: List[Dict[str, Any]],
    max_slope_deg: float,
) -> Dict[str, Any]:
    """Place processor near weighted centroid of dig zones, away from hazards."""
    if not dig_zones:
        # Default to grid center.
        center = _cell_at(cells, GRID_W // 2, GRID_H // 2) or cells[0]
        return {**center, "rationale": "Default placement near grid centre."}

    cx = sum(z["x"] for z in dig_zones) / len(dig_zones)
    cy = sum(z["y"] for z in dig_zones) / len(dig_zones)

    def score(cell: Dict[str, Any]) -> float:
        # Lower is better - distance from centroid plus penalties
        dx = cell["x"] - cx
        dy = cell["y"] - cy
        d = (dx * dx + dy * dy) ** 0.5
        slope_pen = 5.0 if cell["slope_deg"] > max_slope_deg else 0.0
        hazard_pen = 6.0 * cell["hazard_score"]
        comms_pen = 3.0 * (1.0 - cell["comms_quality"])
        return d + slope_pen + hazard_pen + comms_pen

    candidate = min(cells, key=score)
    return {**candidate, "rationale": "Weighted centroid of top dig zones, avoiding slope/hazard/comms penalties."}


def power_placement(
    cells: List[Dict[str, Any]],
    processor_cell: Dict[str, Any],
    max_slope_deg: float,
) -> Dict[str, Any]:
    """High-illumination cell near processor."""
    px, py = processor_cell["x"], processor_cell["y"]

    def score(cell: Dict[str, Any]) -> float:
        if cell["x"] == px and cell["y"] == py:
            return 1e9
        dx = cell["x"] - px
        dy = cell["y"] - py
        d = (dx * dx + dy * dy) ** 0.5
        if d > 6.0:
            return 1e9
        if cell["slope_deg"] > max_slope_deg:
            return 1e9
        return -cell["illumination_pct"] + 4.0 * cell["hazard_score"] + d * 0.2

    candidate = min(cells, key=score)
    return {**candidate, "rationale": "High-illumination cell near processor for solar generation."}


def score_site(
    site: LunarSite, mission: Mission
) -> Dict[str, Any]:
    cells: List[Dict[str, Any]] = list(site.cells_json or [])
    if not cells:
        return {
            "top_dig_zones": [],
            "processor_placement": {},
            "power_placement": {},
            "hazard_zones": [],
            "comms_risk_zones": [],
            "mineability_statistics": {},
        }

    dig = top_dig_zones(cells, k=3)
    processor = processor_placement(cells, dig, mission.max_slope_deg)
    power = power_placement(cells, processor, mission.max_slope_deg)
    hazards = hazard_zones(cells)
    comms_risks = comms_risk_zones(cells)
    stats = grid_stats(cells)

    return {
        "top_dig_zones": dig,
        "processor_placement": processor,
        "power_placement": power,
        "hazard_zones": hazards,
        "comms_risk_zones": comms_risks,
        "mineability_statistics": stats,
    }


def cell_average_illumination(site: LunarSite) -> float:
    cells = site.cells_json or []
    if not cells:
        return 0.0
    return sum(c["illumination_pct"] for c in cells) / len(cells) / 100.0


def serialize_site(site: LunarSite) -> Dict[str, Any]:
    return {
        "id": site.id,
        "mission_id": site.mission_id,
        "name": site.name,
        "region": site.region,
        "grid_width": site.grid_width,
        "grid_height": site.grid_height,
        "cells": site.cells_json,
        "created_at": site.created_at.isoformat(),
    }


def site_summary(site: LunarSite, mission: Mission) -> Dict[str, Any]:
    """Compact summary used by agent context tools."""
    scoring = score_site(site, mission)
    return {
        "site_id": site.id,
        "grid_width": site.grid_width,
        "grid_height": site.grid_height,
        "top_dig_zones": [
            {"x": c["x"], "y": c["y"], "mineability_score": c["mineability_score"]}
            for c in scoring["top_dig_zones"]
        ],
        "processor_placement": {
            "x": scoring["processor_placement"].get("x"),
            "y": scoring["processor_placement"].get("y"),
        },
        "power_placement": {
            "x": scoring["power_placement"].get("x"),
            "y": scoring["power_placement"].get("y"),
        },
        "mineability_statistics": scoring["mineability_statistics"],
    }
