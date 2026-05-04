"""Agent tool registry tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy.orm import Session

from app.agents.tool_registry import execute_tool, get_tool_definitions
from app.services.asset_service import seed_default_assets
from app.services.mission_service import seed_demo_mission
from app.services.site_service import create_or_replace_site


def _bootstrap(db: Session):
    mission = seed_demo_mission(db)
    db.commit()
    create_or_replace_site(db, mission, seed=42)
    db.commit()
    seed_default_assets(db, mission)
    db.commit()
    return mission


def test_definitions_cover_13_tools() -> None:
    defs = get_tool_definitions()
    names = {d["name"] for d in defs}
    assert names == {
        "refresh_public_sources",
        "get_source_context",
        "get_mission_context",
        "generate_synthetic_lunar_site",
        "score_site_mineability",
        "seed_default_assets",
        "generate_balanced_mission_plan",
        "run_mission_simulation",
        "get_simulation_details",
        "recommend_anomaly_response",
        "create_approval",
        "generate_autonomy_artifacts",
        "generate_mission_report",
    }


def test_each_tool_executes(db: Session) -> None:
    mission = _bootstrap(db)
    # source seeding via fallback
    out = execute_tool(db, "refresh_public_sources", {"force": True})
    assert "sources" in out

    out = execute_tool(db, "get_source_context", {"categories": ["isru"]})
    assert "facts" in out

    out = execute_tool(db, "get_mission_context", {"mission_id": mission.id})
    assert out["mission"]["id"] == mission.id

    out = execute_tool(db, "score_site_mineability", {"mission_id": mission.id})
    assert "top_dig_zones" in out

    out = execute_tool(db, "seed_default_assets", {"mission_id": mission.id})
    assert len(out["assets"]) >= 5

    out = execute_tool(db, "generate_balanced_mission_plan", {"mission_id": mission.id})
    assert out["expected_output_kg"] >= 0
    plan_id = out["plan"]["id"]

    out = execute_tool(
        db,
        "run_mission_simulation",
        {"mission_id": mission.id, "plan_id": plan_id, "seed": 42},
    )
    sim_id = out["simulation_run_id"]

    out = execute_tool(db, "get_simulation_details", {"simulation_run_id": sim_id})
    assert "telemetry" in out

    out = execute_tool(db, "generate_autonomy_artifacts", {"mission_id": mission.id})
    assert "behavior_tree" in out

    out = execute_tool(
        db,
        "generate_mission_report",
        {"mission_id": mission.id, "simulation_run_id": sim_id},
    )
    assert out["markdown"]
    # JSON-serialisable
    json.dumps(out)


def test_invalid_mission_id_raises_clear_error(db: Session) -> None:
    with pytest.raises(ValueError) as exc:
        execute_tool(db, "get_mission_context", {"mission_id": "does-not-exist"})
    assert "not found" in str(exc.value).lower()


def test_invalid_tool_name(db: Session) -> None:
    with pytest.raises(ValueError) as exc:
        execute_tool(db, "no_such_tool", {})
    assert "Unknown tool" in str(exc.value)
