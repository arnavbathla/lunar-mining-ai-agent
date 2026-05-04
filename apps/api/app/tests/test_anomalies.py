"""Anomaly tests."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.anomaly_service import (
    list_anomalies_for_run,
    recommend_response,
)
from app.services.asset_service import seed_default_assets
from app.services.mission_service import seed_demo_mission
from app.services.planning_service import generate_balanced_plan
from app.services.site_service import create_or_replace_site
from app.simulation.engine import run_simulation


def _bootstrap(db: Session, seed: int = 42):
    mission = seed_demo_mission(db)
    db.commit()
    create_or_replace_site(db, mission, seed=seed)
    db.commit()
    seed_default_assets(db, mission)
    db.commit()
    plan = generate_balanced_plan(db, mission)
    db.commit()
    return mission, plan


def test_anomalies_deterministic_with_seed(db: Session) -> None:
    mission, plan = _bootstrap(db)
    a = run_simulation(db, mission, plan, seed=7)
    db.commit()
    a_anoms = [(x.hour, x.type, x.severity) for x in list_anomalies_for_run(db, a.id)]

    # Re-run with same seed; expect same sequence (independent of prior run state).
    b = run_simulation(db, mission, plan, seed=7)
    db.commit()
    b_anoms = [(x.hour, x.type, x.severity) for x in list_anomalies_for_run(db, b.id)]
    assert a_anoms == b_anoms


def test_critical_requires_approval(db: Session) -> None:
    mission, plan = _bootstrap(db)
    sim = run_simulation(db, mission, plan, seed=99)
    db.commit()
    anomalies = list_anomalies_for_run(db, sim.id)
    for a in anomalies:
        if a.severity == "critical":
            assert a.requires_human_approval is True


def test_recommendation_includes_action_and_impact(db: Session) -> None:
    mission, plan = _bootstrap(db)
    sim = run_simulation(db, mission, plan, seed=11)
    db.commit()
    anomalies = list_anomalies_for_run(db, sim.id)
    if not anomalies:
        return
    rec = recommend_response(db, anomalies[0])
    assert "recommended_action" in rec
    assert rec["production_impact_kg"] >= 0
    assert "alternative_actions" in rec
