"""Anthropic Claude agent routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.agent_loop import run_agent_loop
from app.agents.anthropic_client import make_real_client
from app.agents.prompts import (
    ANOMALY_USER_PROMPT,
    READINESS_USER_PROMPT,
    REFRESH_SOURCES_USER_PROMPT,
    REPORT_USER_PROMPT,
)
from app.agents.tool_registry import list_available_actions
from app.config import settings
from app.db.database import get_db
from app.db.models import SimulationRun
from app.schemas.api import (
    AgentAnomalyResponseOut,
    AgentAnomalyResponseRequest,
    AgentReportOut,
    AgentReportRequest,
    AgentRunReadinessOut,
    AgentRunReadinessRequest,
    AgentStatusOut,
)
from app.services.anomaly_service import recommend_response, get_anomaly
from app.services.mission_service import get_mission

router = APIRouter(prefix="/agent", tags=["agent"])


def _coerce_next_actions(items: Any) -> list[str]:
    """Normalize Claude's next_actions output into a list of strings.

    Claude sometimes returns objects like {"priority": 1, "action": "..."}
    instead of plain strings. We accept either shape and surface a clean
    list[str] to the frontend.
    """
    if not items:
        return []
    if not isinstance(items, list):
        items = [items]
    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            priority = item.get("priority")
            action = (
                item.get("action")
                or item.get("description")
                or item.get("title")
                or item.get("text")
            )
            if action and priority is not None:
                out.append(f"{priority}. {action}")
            elif action:
                out.append(str(action))
            else:
                out.append(", ".join(f"{k}: {v}" for k, v in item.items()))
        else:
            out.append(str(item))
    return out


def _require_anthropic() -> None:
    if not settings.anthropic_configured:
        raise HTTPException(
            status_code=400,
            detail="ANTHROPIC_API_KEY required for Claude agent execution.",
        )


def _build_client() -> Any:
    try:
        return make_real_client()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=str(exc) or "ANTHROPIC_API_KEY required for Claude agent execution.",
        ) from exc


def _surface_anthropic_error(exc: Exception) -> HTTPException:
    msg = str(exc)
    if "model" in msg.lower():
        return HTTPException(
            status_code=400,
            detail=(
                f"Anthropic returned a model error: {msg}. "
                "Set ANTHROPIC_MODEL to a valid model identifier in apps/api/.env "
                "(for example, claude-sonnet-4-6) and restart the backend."
            ),
        )
    return HTTPException(status_code=502, detail=f"Anthropic error: {msg}")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get("/status", response_model=AgentStatusOut)
def status() -> AgentStatusOut:
    return AgentStatusOut(
        anthropic_configured=settings.anthropic_configured,
        model=settings.ANTHROPIC_MODEL,
        available_agent_actions=list_available_actions(),
    )


# ---------------------------------------------------------------------------
# Run readiness analysis
# ---------------------------------------------------------------------------


@router.post("/run-readiness-analysis", response_model=AgentRunReadinessOut)
def run_readiness(
    body: AgentRunReadinessRequest,
    db: Session = Depends(get_db),
) -> AgentRunReadinessOut:
    _require_anthropic()
    mission = get_mission(db, body.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")

    client = _build_client()
    user_prompt = READINESS_USER_PROMPT.format(
        mission_id=body.mission_id, seed=body.seed
    )

    try:
        result = run_agent_loop(
            db=db,
            client=client,
            agent_type="run_readiness_analysis",
            mission_id=body.mission_id,
            user_prompt=user_prompt,
        )
    except RuntimeError as exc:
        raise _surface_anthropic_error(exc) from exc

    db.commit()

    final = result["final_json"] or {}
    return AgentRunReadinessOut(
        agent_run_id=result["agent_run_id"],
        tool_calls=result["tool_calls"],
        plan=final.get("plan"),
        simulation=final.get("simulation"),
        readiness=final.get("readiness"),
        executive_recommendation=final.get("executive_recommendation", ""),
        source_grounding_summary=final.get("source_grounding_summary", ""),
        next_actions=_coerce_next_actions(final.get("next_actions")),
        model=result["model"],
        created_at=result["created_at"],
    )


# ---------------------------------------------------------------------------
# Anomaly response
# ---------------------------------------------------------------------------


@router.post("/anomaly-response", response_model=AgentAnomalyResponseOut)
def anomaly_response(
    body: AgentAnomalyResponseRequest,
    db: Session = Depends(get_db),
) -> AgentAnomalyResponseOut:
    _require_anthropic()
    sim = db.get(SimulationRun, body.simulation_run_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    anomaly = get_anomaly(db, body.anomaly_id)
    if anomaly is None or anomaly.simulation_run_id != sim.id:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    client = _build_client()
    user_prompt = ANOMALY_USER_PROMPT.format(
        simulation_run_id=body.simulation_run_id,
        anomaly_id=body.anomaly_id,
    )

    try:
        result = run_agent_loop(
            db=db,
            client=client,
            agent_type="anomaly_response",
            mission_id=sim.mission_id,
            user_prompt=user_prompt,
        )
    except RuntimeError as exc:
        raise _surface_anthropic_error(exc) from exc

    db.commit()

    final = result["final_json"] or {}
    recommendation = final.get("recommendation") or recommend_response(db, anomaly)
    return AgentAnomalyResponseOut(
        agent_run_id=result["agent_run_id"],
        tool_calls=result["tool_calls"],
        recommendation=recommendation,
        approval_id=final.get("approval_id"),
        operator_message=final.get("operator_message", ""),
        model=result["model"],
        created_at=result["created_at"],
    )


# ---------------------------------------------------------------------------
# Mission report
# ---------------------------------------------------------------------------


@router.post("/report", response_model=AgentReportOut)
def report(
    body: AgentReportRequest,
    db: Session = Depends(get_db),
) -> AgentReportOut:
    _require_anthropic()
    sim = db.get(SimulationRun, body.simulation_run_id)
    if sim is None or sim.mission_id != body.mission_id:
        raise HTTPException(status_code=404, detail="Simulation run not found")

    client = _build_client()
    user_prompt = REPORT_USER_PROMPT.format(
        mission_id=body.mission_id,
        simulation_run_id=body.simulation_run_id,
    )

    try:
        result = run_agent_loop(
            db=db,
            client=client,
            agent_type="report",
            mission_id=body.mission_id,
            user_prompt=user_prompt,
        )
    except RuntimeError as exc:
        raise _surface_anthropic_error(exc) from exc

    db.commit()

    final = result["final_json"] or {}
    markdown = final.get("markdown") or ""

    # Fallback to deterministic report if the model didn't return markdown
    if not markdown:
        from app.services.report_service import generate_report

        mission = get_mission(db, body.mission_id)
        if mission is not None:
            report_row = generate_report(db, mission, sim)
            db.commit()
            markdown = report_row.markdown
            return AgentReportOut(
                agent_run_id=result["agent_run_id"],
                tool_calls=result["tool_calls"],
                report_id=report_row.id,
                markdown=markdown,
                model=result["model"],
                created_at=result["created_at"],
            )

    return AgentReportOut(
        agent_run_id=result["agent_run_id"],
        tool_calls=result["tool_calls"],
        report_id=None,
        markdown=markdown,
        model=result["model"],
        created_at=result["created_at"],
    )


# ---------------------------------------------------------------------------
# Refresh sources via Claude
# ---------------------------------------------------------------------------


@router.post("/refresh-sources")
def agent_refresh_sources(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    _require_anthropic()
    client = _build_client()
    try:
        result = run_agent_loop(
            db=db,
            client=client,
            agent_type="refresh_sources",
            mission_id=None,
            user_prompt=REFRESH_SOURCES_USER_PROMPT,
        )
    except RuntimeError as exc:
        raise _surface_anthropic_error(exc) from exc
    db.commit()
    return {
        "agent_run_id": result["agent_run_id"],
        "tool_calls": result["tool_calls"],
        "summary": result["final_json"],
        "model": result["model"],
        "created_at": result["created_at"],
    }
