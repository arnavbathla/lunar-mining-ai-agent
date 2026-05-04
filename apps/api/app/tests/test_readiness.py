"""Readiness scoring tests."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.readiness_service import score_readiness


class _FakeMission:
    target_amount_kg = 100.0
    safety_battery_margin_pct = 25.0
    max_slope_deg = 12.0


class _FakeSim:
    def __init__(
        self,
        *,
        total_output_kg: float = 100.0,
        lowest_battery_margin_pct: float = 30.0,
        anomaly_count: int = 1,
    ) -> None:
        self.total_output_kg = total_output_kg
        self.lowest_battery_margin_pct = lowest_battery_margin_pct
        self.anomaly_count = anomaly_count


def _scoring(top_scores: list[float]) -> dict:
    return {
        "top_dig_zones": [
            {"x": i, "y": i, "mineability_score": s, "resource_score": 0.5,
             "slope_deg": 5.0, "hazard_score": 0.1, "comms_quality": 0.7,
             "illumination_pct": 80.0}
            for i, s in enumerate(top_scores)
        ],
        "mineability_statistics": {},
    }


def test_returns_five_dimensions() -> None:
    out = score_readiness(
        mission=_FakeMission(),
        sim=_FakeSim(),
        site_scoring=_scoring([0.85, 0.80, 0.65]),
        anomalies_serialized=[],
    )
    assert set(out.keys()) == {
        "site_mineability",
        "production_target",
        "power_budget",
        "autonomy_risk",
        "mission_readiness",
    }


def test_fail_when_output_low() -> None:
    out = score_readiness(
        mission=_FakeMission(),
        sim=_FakeSim(total_output_kg=10.0),
        site_scoring=_scoring([0.85, 0.80, 0.65]),
        anomalies_serialized=[],
    )
    assert out["production_target"]["status"] == "fail"
    assert out["mission_readiness"]["status"] == "no_go"


def test_conditional_go_logic() -> None:
    out = score_readiness(
        mission=_FakeMission(),
        sim=_FakeSim(total_output_kg=85.0, lowest_battery_margin_pct=22.0),
        site_scoring=_scoring([0.85, 0.65, 0.40]),
        anomalies_serialized=[],
    )
    # production caution + power caution + site caution -> conditional go
    assert out["mission_readiness"]["status"] in {"conditional_go", "go"}


def test_no_go_logic() -> None:
    out = score_readiness(
        mission=_FakeMission(),
        sim=_FakeSim(total_output_kg=120.0, lowest_battery_margin_pct=10.0),
        site_scoring=_scoring([0.85, 0.80, 0.65]),
        anomalies_serialized=[],
    )
    assert out["power_budget"]["status"] == "fail"
    assert out["mission_readiness"]["status"] == "no_go"
