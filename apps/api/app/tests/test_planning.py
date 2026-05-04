"""Planning service tests."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.asset_service import get_assets, seed_default_assets
from app.services.mission_service import seed_demo_mission
from app.services.planning_service import generate_balanced_plan
from app.services.site_service import create_or_replace_site


def _bootstrap(db: Session):
    mission = seed_demo_mission(db)
    db.commit()
    create_or_replace_site(db, mission, seed=42)
    db.commit()
    seed_default_assets(db, mission)
    db.commit()
    return mission


def test_plan_has_tasks(db: Session) -> None:
    mission = _bootstrap(db)
    plan = generate_balanced_plan(db, mission)
    db.commit()
    assert plan is not None
    assert len(plan.tasks_json) > 0


def test_tasks_reference_valid_assets(db: Session) -> None:
    mission = _bootstrap(db)
    plan = generate_balanced_plan(db, mission)
    db.commit()
    assets = {a.id for a in get_assets(db, mission.id)}
    for task in plan.tasks_json:
        assert task["asset_id"] in assets


def test_expected_output_positive(db: Session) -> None:
    mission = _bootstrap(db)
    plan = generate_balanced_plan(db, mission)
    db.commit()
    assert plan.expected_output_kg > 0
    assert plan.confidence_pct > 0


def test_risk_register_and_artifacts(db: Session) -> None:
    mission = _bootstrap(db)
    plan = generate_balanced_plan(db, mission)
    db.commit()
    assert plan.risk_register_json
    assert all("risk" in r for r in plan.risk_register_json)
    artifacts = plan.autonomy_artifacts_json or {}
    assert "behavior_tree" in artifacts
    assert "ros_task_messages" in artifacts
    assert "state_machine" in artifacts
    assert "operator_runbook" in artifacts
