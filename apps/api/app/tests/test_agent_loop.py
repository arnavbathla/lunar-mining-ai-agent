"""Agent loop tests using the fake Anthropic client."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.agent_loop import run_agent_loop
from app.agents.fake_client import FakeAnthropicClient, final_text_turn, tool_use_turn
from app.db.models import AgentRun
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


def test_fake_tool_use_flow_persists_agent_run(db: Session) -> None:
    mission = _bootstrap(db)

    # Script: get_source_context -> get_mission_context -> final JSON.
    client = FakeAnthropicClient(
        turns=[
            tool_use_turn(
                "get_source_context", "tu_1", {"categories": ["isru"]}
            ),
            tool_use_turn(
                "get_mission_context", "tu_2", {"mission_id": mission.id}
            ),
            final_text_turn(
                '```json\n{"executive_recommendation": "Conditional Go.", '
                '"next_actions": ["Refresh sources", "Re-run simulation"]}\n```'
            ),
        ]
    )

    result = run_agent_loop(
        db=db,
        client=client,
        agent_type="run_readiness_analysis",
        mission_id=mission.id,
        user_prompt="Run readiness analysis",
    )
    db.commit()

    assert result["final_json"]["executive_recommendation"] == "Conditional Go."
    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][0]["tool"] == "get_source_context"

    persisted = db.get(AgentRun, result["agent_run_id"])
    assert persisted is not None
    assert persisted.agent_type == "run_readiness_analysis"
    assert persisted.tool_calls_json
    assert persisted.final_response_json["executive_recommendation"] == "Conditional Go."


def test_missing_api_key_returns_clear_error_for_real_endpoint() -> None:
    # We import lazily to avoid affecting other tests' settings.
    from app.agents.anthropic_client import make_real_client
    import app.config as cfg

    original = cfg.settings.ANTHROPIC_API_KEY
    cfg.settings.ANTHROPIC_API_KEY = ""
    try:
        with pytest.raises(ValueError) as exc:
            make_real_client()
        assert "ANTHROPIC_API_KEY required" in str(exc.value)
    finally:
        cfg.settings.ANTHROPIC_API_KEY = original


def test_tool_error_recovers_via_tool_result(db: Session) -> None:
    mission = _bootstrap(db)
    client = FakeAnthropicClient(
        turns=[
            tool_use_turn("get_mission_context", "tu_1", {"mission_id": "missing"}),
            final_text_turn('```json\n{"executive_recommendation": "Recovered."}\n```'),
        ]
    )
    result = run_agent_loop(
        db=db,
        client=client,
        agent_type="run_readiness_analysis",
        mission_id=mission.id,
        user_prompt="Test recovery",
    )
    db.commit()
    # First tool call errored but loop continued.
    assert result["tool_calls"][0]["is_error"] is True
    assert result["final_json"]["executive_recommendation"] == "Recovered."
