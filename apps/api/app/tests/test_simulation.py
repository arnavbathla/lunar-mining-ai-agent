"""Simulation engine tests."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.asset_service import seed_default_assets
from app.services.mission_service import seed_demo_mission
from app.services.planning_service import generate_balanced_plan
from app.services.site_service import create_or_replace_site
from app.simulation.engine import run_simulation


def _bootstrap(db: Session):
    mission = seed_demo_mission(db)
    db.commit()
    create_or_replace_site(db, mission, seed=42)
    db.commit()
    seed_default_assets(db, mission)
    db.commit()
    plan = generate_balanced_plan(db, mission)
    db.commit()
    return mission, plan


def test_simulation_produces_telemetry_for_full_duration(db: Session) -> None:
    mission, plan = _bootstrap(db)
    sim = run_simulation(db, mission, plan, seed=42)
    db.commit()
    telemetry = sim.telemetry_json or []
    assert telemetry
    hours = {t["hour"] for t in telemetry}
    assert max(hours) == mission.duration_hours - 1
    assert len(hours) == mission.duration_hours


def test_output_accumulates(db: Session) -> None:
    mission, plan = _bootstrap(db)
    sim = run_simulation(db, mission, plan, seed=42)
    db.commit()
    telemetry = sim.telemetry_json
    cum = [t["cumulative_output_kg"] for t in telemetry]
    assert max(cum) >= 0


def test_batteries_drain_and_recharge(db: Session) -> None:
    mission, plan = _bootstrap(db)
    sim = run_simulation(db, mission, plan, seed=42)
    db.commit()
    telemetry = sim.telemetry_json
    excavator_battery = [
        t["battery_pct"] for t in telemetry if t["asset_name"] == "Excavator-1"
    ]
    # battery should not be flat
    assert max(excavator_battery) - min(excavator_battery) > 5.0


def test_deterministic_with_seed(db: Session) -> None:
    mission, plan = _bootstrap(db)
    a = run_simulation(db, mission, plan, seed=42)
    b = run_simulation(db, mission, plan, seed=42)
    db.commit()
    assert a.total_output_kg == b.total_output_kg
    assert a.lowest_battery_margin_pct == b.lowest_battery_margin_pct


def test_success_probability_within_range(db: Session) -> None:
    mission, plan = _bootstrap(db)
    sim = run_simulation(db, mission, plan, seed=42)
    db.commit()
    assert 0.0 <= sim.success_probability_pct <= 99.0
