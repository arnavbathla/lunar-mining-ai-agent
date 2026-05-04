"""Deterministic synthetic lunar polar site generator.

Produces a 30x30 grid with realistic-feeling distributions of:
- elevation
- slope
- illumination
- resource score (water-ice-equivalent)
- hazard score
- comms quality
- temperature
- mineability score (computed via :func:`compute_mineability`)

The generator only uses Python's ``random.Random(seed)`` for stable
cross-platform determinism without numpy as a dependency.
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Tuple

GRID_W = 30
GRID_H = 30


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _gauss_falloff(dx: float, dy: float, sigma: float) -> float:
    return math.exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Mineability formula (used by site generator and site_service)
# ---------------------------------------------------------------------------


def compute_mineability(
    *,
    resource_score: float,
    illumination_pct: float,
    comms_quality: float,
    slope_deg: float,
    hazard_score: float,
    max_slope_deg: float = 12.0,
) -> float:
    """Implements the spec's mineability formula and penalties."""
    illumination_normalized = illumination_pct / 100.0
    inverse_slope_score = max(0.0, 1.0 - slope_deg / 25.0)
    inverse_hazard_score = max(0.0, 1.0 - hazard_score)

    base = (
        0.35 * resource_score
        + 0.20 * illumination_normalized
        + 0.15 * comms_quality
        + 0.15 * inverse_slope_score
        + 0.15 * inverse_hazard_score
    )

    score = base
    if slope_deg > max_slope_deg:
        score *= 0.25
    if hazard_score > 0.75:
        score *= 0.50
    if comms_quality < 0.25:
        score *= 0.70
    if illumination_pct < 20.0:
        score *= 0.80

    return round(_clamp(score, 0.0, 1.0), 4)


# ---------------------------------------------------------------------------
# Site generation
# ---------------------------------------------------------------------------


def _zone_centers(rng: random.Random) -> Dict[str, List[Tuple[float, float, float]]]:
    """Pick deterministic zone centers (x, y, sigma)."""
    # 3 high-resource zones
    resource_zones: List[Tuple[float, float, float]] = [
        (8.0, 7.0, 3.5),
        (20.0, 12.0, 3.2),
        (15.0, 22.0, 3.8),
    ]
    # 2 crater-edge high-hazard zones
    hazard_zones: List[Tuple[float, float, float]] = [
        (5.0, 25.0, 3.0),
        (24.0, 5.0, 3.2),
    ]
    # 1 comms shadow region
    comms_shadow: List[Tuple[float, float, float]] = [(3.0, 3.0, 4.0)]
    # 1 high-illumination ridge (a long, narrow band)
    illum_ridge: List[Tuple[float, float, float]] = [(GRID_W / 2.0, GRID_H / 2.0, 7.0)]

    # Slight jitter per seed to avoid being identical across regenerations;
    # but keep within the same character. Bounded jitter remains deterministic.
    def jitter(zones: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        out = []
        for x, y, s in zones:
            jx = x + rng.uniform(-0.6, 0.6)
            jy = y + rng.uniform(-0.6, 0.6)
            out.append((jx, jy, s))
        return out

    return {
        "resource": jitter(resource_zones),
        "hazard": jitter(hazard_zones),
        "comms_shadow": jitter(comms_shadow),
        "illumination_ridge": jitter(illum_ridge),
    }


def generate_site(
    seed: int = 42,
    width: int = GRID_W,
    height: int = GRID_H,
    max_slope_deg: float = 12.0,
) -> List[Dict[str, Any]]:
    """Generate a deterministic 30x30 polar site as a list of cells."""
    rng = random.Random(seed)
    zones = _zone_centers(rng)

    cells: List[Dict[str, Any]] = []

    base_elev = -200.0  # crater floor reference (m)
    elev_noise_scale = 35.0

    for y in range(height):
        for x in range(width):
            # Resource score from gaussian peaks
            resource = 0.0
            for cx, cy, sigma in zones["resource"]:
                resource += _gauss_falloff(x - cx, y - cy, sigma)
            resource = _clamp(resource * 0.95 + rng.uniform(-0.05, 0.05))

            # Hazard score from crater edges
            hazard = 0.0
            for cx, cy, sigma in zones["hazard"]:
                hazard += _gauss_falloff(x - cx, y - cy, sigma) * 0.95
            hazard += rng.uniform(0.0, 0.08)
            hazard = _clamp(hazard)

            # Illumination ridge - high in the middle band, lower at edges
            illum_factor = 0.0
            for cx, cy, sigma in zones["illumination_ridge"]:
                illum_factor += _gauss_falloff(x - cx, y - cy, sigma)
            base_illum = 35.0 + 60.0 * illum_factor + rng.uniform(-6.0, 6.0)
            illumination_pct = max(2.0, min(98.0, base_illum))
            # Polar shadowing dips
            if x < 4 and y > 22:
                illumination_pct *= 0.4
            if x > 25 and y < 6:
                illumination_pct *= 0.5

            # Comms quality - reduced in shadow, decent elsewhere
            comms = 0.85 - 0.55 * sum(
                _gauss_falloff(x - cx, y - cy, sigma)
                for cx, cy, sigma in zones["comms_shadow"]
            )
            comms += rng.uniform(-0.06, 0.06)
            comms = _clamp(comms)

            # Slope - higher near hazard zones and edges
            slope = 2.0 + 14.0 * hazard + rng.uniform(-1.0, 2.0)
            edge_dist = min(x, y, width - 1 - x, height - 1 - y)
            if edge_dist <= 1:
                slope += 4.0
            slope_deg = max(0.0, min(28.0, slope))

            # Elevation - ridge centre raised; crater near hazard
            elevation = base_elev
            elevation += 80.0 * illum_factor
            elevation -= 60.0 * hazard
            elevation += rng.uniform(-elev_noise_scale * 0.3, elev_noise_scale * 0.3)

            # Temperature - colder in shadow, warmer in light
            temperature_c = -180.0 + 80.0 * (illumination_pct / 100.0)
            temperature_c += rng.uniform(-3.0, 3.0)

            mineability = compute_mineability(
                resource_score=resource,
                illumination_pct=illumination_pct,
                comms_quality=comms,
                slope_deg=slope_deg,
                hazard_score=hazard,
                max_slope_deg=max_slope_deg,
            )

            cells.append(
                {
                    "x": x,
                    "y": y,
                    "elevation_m": round(elevation, 2),
                    "slope_deg": round(slope_deg, 2),
                    "illumination_pct": round(illumination_pct, 2),
                    "resource_score": round(resource, 4),
                    "hazard_score": round(hazard, 4),
                    "comms_quality": round(comms, 4),
                    "temperature_c": round(temperature_c, 2),
                    "mineability_score": mineability,
                }
            )

    return cells


def grid_stats(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not cells:
        return {}
    n = len(cells)

    def avg(key: str) -> float:
        return round(sum(c[key] for c in cells) / n, 4)

    def mn(key: str) -> float:
        return round(min(c[key] for c in cells), 4)

    def mx(key: str) -> float:
        return round(max(c[key] for c in cells), 4)

    return {
        "cell_count": n,
        "avg_resource_score": avg("resource_score"),
        "avg_hazard_score": avg("hazard_score"),
        "avg_illumination_pct": avg("illumination_pct"),
        "avg_slope_deg": avg("slope_deg"),
        "avg_comms_quality": avg("comms_quality"),
        "avg_mineability_score": avg("mineability_score"),
        "max_mineability_score": mx("mineability_score"),
        "min_mineability_score": mn("mineability_score"),
    }
