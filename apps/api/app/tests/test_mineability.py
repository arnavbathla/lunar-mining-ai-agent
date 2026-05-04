"""Mineability scoring tests."""
from __future__ import annotations

from app.simulation.site_generator import compute_mineability


def test_high_resource_low_hazard_scores_higher() -> None:
    high = compute_mineability(
        resource_score=0.9,
        illumination_pct=85.0,
        comms_quality=0.85,
        slope_deg=4.0,
        hazard_score=0.05,
    )
    low = compute_mineability(
        resource_score=0.2,
        illumination_pct=85.0,
        comms_quality=0.85,
        slope_deg=4.0,
        hazard_score=0.85,
    )
    assert high > low


def test_slope_over_max_is_penalised() -> None:
    base = compute_mineability(
        resource_score=0.8,
        illumination_pct=80.0,
        comms_quality=0.8,
        slope_deg=10.0,
        hazard_score=0.1,
        max_slope_deg=12.0,
    )
    over = compute_mineability(
        resource_score=0.8,
        illumination_pct=80.0,
        comms_quality=0.8,
        slope_deg=20.0,
        hazard_score=0.1,
        max_slope_deg=12.0,
    )
    assert over < base * 0.5  # 0.25x penalty applied


def test_comms_shadow_is_penalised() -> None:
    bright = compute_mineability(
        resource_score=0.6,
        illumination_pct=80.0,
        comms_quality=0.7,
        slope_deg=4.0,
        hazard_score=0.2,
    )
    shadow = compute_mineability(
        resource_score=0.6,
        illumination_pct=80.0,
        comms_quality=0.10,  # below 0.25 threshold
        slope_deg=4.0,
        hazard_score=0.2,
    )
    assert shadow < bright


def test_high_hazard_is_penalised() -> None:
    safe = compute_mineability(
        resource_score=0.6,
        illumination_pct=80.0,
        comms_quality=0.7,
        slope_deg=4.0,
        hazard_score=0.5,
    )
    dangerous = compute_mineability(
        resource_score=0.6,
        illumination_pct=80.0,
        comms_quality=0.7,
        slope_deg=4.0,
        hazard_score=0.85,
    )
    assert dangerous < safe
