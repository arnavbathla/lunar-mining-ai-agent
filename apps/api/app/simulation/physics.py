"""Deterministic physics helpers used by the simulation engine."""
from __future__ import annotations

from typing import Any, Dict


def excavation_kg(
    *,
    excavation_rate_kg_per_hour: float,
    resource_score: float,
    mineability_score: float,
    slope_deg: float,
    max_slope_deg: float,
    hazard_score: float,
    health_pct: float,
    available_power_factor: float,
) -> float:
    """Compute regolith excavated for one hour."""
    health_factor = max(0.5, health_pct / 100.0)
    slope_factor = 1.0 if slope_deg <= max_slope_deg else 0.5
    hazard_factor = max(0.55, 1.0 - 0.6 * hazard_score)
    base = (
        excavation_rate_kg_per_hour
        * (0.55 + 0.45 * resource_score)
        * (0.55 + 0.45 * mineability_score)
        * slope_factor
        * hazard_factor
        * health_factor
        * available_power_factor
    )
    return max(0.0, base)


def haul_kg_delivered(
    *,
    payload_kg: float,
    distance_cells: float,
    speed_m_per_hour: float,
    cell_size_m: float = 50.0,
    power_factor: float = 1.0,
    health_pct: float = 100.0,
    route_hazard: float = 0.0,
) -> float:
    """Approximate kg delivered per hour for a hauler.

    The hauler can deliver its full payload when distance is short enough to
    complete the round trip in one hour, otherwise output is reduced
    proportionally.
    """
    if payload_kg <= 0 or speed_m_per_hour <= 0:
        return 0.0
    round_trip_m = max(1.0, 2.0 * distance_cells * cell_size_m)
    cycles_per_hour = (speed_m_per_hour / round_trip_m) if round_trip_m > 0 else 0.0
    delivered = (
        payload_kg
        * cycles_per_hour
        * power_factor
        * max(0.55, health_pct / 100.0)
        * max(0.5, 1.0 - 0.4 * route_hazard)
    )
    return max(0.0, delivered)


def processor_water_kg(
    *,
    available_input_kg: float,
    input_rate_kg_per_hour: float,
    extraction_efficiency_pct: float,
    health_pct: float,
    available_power_factor: float,
) -> Dict[str, float]:
    consumed = min(
        available_input_kg,
        input_rate_kg_per_hour
        * available_power_factor
        * max(0.5, health_pct / 100.0),
    )
    output = consumed * (extraction_efficiency_pct / 100.0)
    return {"consumed_input_kg": consumed, "output_kg": output}


def solar_generation_kwh(
    *,
    generation_kw: float,
    average_illumination_factor: float,
    uptime_pct: float,
) -> float:
    return max(
        0.0,
        generation_kw * average_illumination_factor * (uptime_pct / 100.0),
    )
