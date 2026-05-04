"""Tool registry for the Lunar MineOps Claude agent.

Each tool maps a JSON schema input to a real backend operation. Tools are
strict about input validation; failures are returned as ``tool_result``
blocks with ``is_error=true`` so the model can self-correct.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Anomaly,
    Approval,
    LunarSite,
    Mission,
    Plan,
    SimulationRun,
)
from app.services.anomaly_service import (
    get_anomaly,
    list_anomalies_for_run,
    recommend_response,
    serialize_anomaly,
    serialize_approval,
)
from app.services.asset_service import (
    asset_summary,
    get_assets,
    seed_default_assets,
)
from app.services.mission_service import get_mission
from app.services.planning_service import (
    autonomy_artifacts_for_mission,
    generate_balanced_plan,
    latest_plan_for_mission,
    serialize_plan,
)
from app.services.readiness_service import score_readiness
from app.services.report_service import generate_report
from app.services.site_service import (
    create_or_replace_site,
    get_site_for_mission,
    score_site,
    serialize_site,
    site_summary,
)
from app.services.source_service import (
    FACT_CATEGORIES,
    get_source_context as _get_source_context,
    list_sources,
    refresh_sources,
)
from app.simulation.engine import (
    battery_curve,
    power_curve,
    production_curve,
    run_simulation,
    telemetry_summary,
)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


ToolFunc = Callable[[Session, Dict[str, Any]], Dict[str, Any]]


def get_tool_definitions() -> List[Dict[str, Any]]:
    """JSON schema definitions exposed to Anthropic via the tools= parameter."""
    return [
        {
            "name": "refresh_public_sources",
            "description": (
                "Refresh the official NASA/PDS public source documents. "
                "Returns counts and per-source freshness/fallback flags."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"force": {"type": "boolean"}},
            },
        },
        {
            "name": "get_source_context",
            "description": (
                "Return source-grounded facts and source freshness "
                "for the requested categories."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        {
            "name": "get_mission_context",
            "description": (
                "Return mission, site summary, assets, latest plan, "
                "latest simulation, and anomalies."
            ),
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {"mission_id": {"type": "string"}},
            },
        },
        {
            "name": "generate_synthetic_lunar_site",
            "description": "Generate or replace the synthetic 30x30 polar site.",
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {
                    "mission_id": {"type": "string"},
                    "seed": {"type": "integer"},
                },
            },
        },
        {
            "name": "score_site_mineability",
            "description": (
                "Compute mineability stats: top dig zones, processor placement, "
                "power placement, hazard zones, comms-risk zones."
            ),
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {"mission_id": {"type": "string"}},
            },
        },
        {
            "name": "seed_default_assets",
            "description": "Seed the seven default mission assets if missing.",
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {"mission_id": {"type": "string"}},
            },
        },
        {
            "name": "generate_balanced_mission_plan",
            "description": "Generate the balanced plan with risk register and autonomy artifacts.",
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {"mission_id": {"type": "string"}},
            },
        },
        {
            "name": "run_mission_simulation",
            "description": (
                "Run the deterministic hourly simulation for the latest "
                "plan and return metrics, readiness, telemetry summary, and anomalies."
            ),
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {
                    "mission_id": {"type": "string"},
                    "plan_id": {"type": "string"},
                    "seed": {"type": "integer"},
                },
            },
        },
        {
            "name": "get_simulation_details",
            "description": (
                "Return full simulation: telemetry, production/battery/power curves, "
                "anomalies, readiness verdict."
            ),
            "input_schema": {
                "type": "object",
                "required": ["simulation_run_id"],
                "properties": {"simulation_run_id": {"type": "string"}},
            },
        },
        {
            "name": "recommend_anomaly_response",
            "description": "Return a structured recommendation for an anomaly.",
            "input_schema": {
                "type": "object",
                "required": ["simulation_run_id", "anomaly_id"],
                "properties": {
                    "simulation_run_id": {"type": "string"},
                    "anomaly_id": {"type": "string"},
                },
            },
        },
        {
            "name": "create_approval",
            "description": "Create an approval row for a pending anomaly response.",
            "input_schema": {
                "type": "object",
                "required": ["anomaly_id", "recommended_action"],
                "properties": {
                    "anomaly_id": {"type": "string"},
                    "recommended_action": {"type": "string"},
                },
            },
        },
        {
            "name": "generate_autonomy_artifacts",
            "description": "Generate (or refresh) autonomy artifacts for a plan.",
            "input_schema": {
                "type": "object",
                "required": ["mission_id"],
                "properties": {
                    "mission_id": {"type": "string"},
                    "plan_id": {"type": "string"},
                },
            },
        },
        {
            "name": "generate_mission_report",
            "description": "Generate the markdown mission readiness report.",
            "input_schema": {
                "type": "object",
                "required": ["mission_id", "simulation_run_id"],
                "properties": {
                    "mission_id": {"type": "string"},
                    "simulation_run_id": {"type": "string"},
                },
            },
        },
    ]


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


def _need(payload: Dict[str, Any], key: str, type_: type) -> Any:
    if key not in payload:
        raise ValueError(f"Missing required field '{key}'.")
    val = payload[key]
    if not isinstance(val, type_):
        raise ValueError(
            f"Field '{key}' must be of type {type_.__name__}, got {type(val).__name__}."
        )
    return val


def _ensure_mission(db: Session, mission_id: str) -> Mission:
    mission = get_mission(db, mission_id)
    if not mission:
        raise ValueError(f"Mission {mission_id} not found.")
    return mission


def _build_mission_context(db: Session, mission: Mission) -> Dict[str, Any]:
    site = get_site_for_mission(db, mission.id)
    assets = get_assets(db, mission.id)
    plan = latest_plan_for_mission(db, mission.id)
    sim_row = (
        db.execute(
            select(SimulationRun)
            .where(SimulationRun.mission_id == mission.id)
            .order_by(SimulationRun.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    anomalies: List[Anomaly] = []
    if sim_row is not None:
        anomalies = list_anomalies_for_run(db, sim_row.id)

    return {
        "mission": {
            "id": mission.id,
            "name": mission.name,
            "objective": mission.objective,
            "duration_hours": mission.duration_hours,
            "target_resource": mission.target_resource,
            "target_amount_kg": mission.target_amount_kg,
            "safety_battery_margin_pct": mission.safety_battery_margin_pct,
            "max_slope_deg": mission.max_slope_deg,
        },
        "site_summary": site_summary(site, mission) if site else None,
        "assets": [asset_summary(a) for a in assets],
        "latest_plan": serialize_plan(plan) if plan else None,
        "latest_simulation": (
            {
                "id": sim_row.id,
                "total_output_kg": sim_row.total_output_kg,
                "total_regolith_moved_kg": sim_row.total_regolith_moved_kg,
                "average_power_kw": sim_row.average_power_kw,
                "lowest_battery_margin_pct": sim_row.lowest_battery_margin_pct,
                "downtime_hours": sim_row.downtime_hours,
                "anomaly_count": sim_row.anomaly_count,
                "success_probability_pct": sim_row.success_probability_pct,
                "readiness": sim_row.readiness_json,
                "created_at": sim_row.created_at.isoformat(),
            }
            if sim_row
            else None
        ),
        "anomalies": [serialize_anomaly(a) for a in anomalies],
    }


# ---- Tool implementations -------------------------------------------------


def tool_refresh_public_sources(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    return refresh_sources(db, force=bool(payload.get("force", False)))


def tool_get_source_context(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    cats = payload.get("categories") or list(FACT_CATEGORIES)
    if not isinstance(cats, list):
        raise ValueError("categories must be a list of strings.")
    return _get_source_context(db, cats)


def tool_get_mission_context(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    mission = _ensure_mission(db, mission_id)
    return _build_mission_context(db, mission)


def tool_generate_synthetic_lunar_site(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    seed = int(payload.get("seed", 42))
    mission = _ensure_mission(db, mission_id)
    site = create_or_replace_site(db, mission, seed=seed)
    scoring = score_site(site, mission)
    return {
        "site": serialize_site(site),
        "grid_stats": scoring["mineability_statistics"],
        "resource_zones": scoring["top_dig_zones"],
        "hazard_zones": scoring["hazard_zones"],
    }


def tool_score_site_mineability(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    mission = _ensure_mission(db, mission_id)
    site = get_site_for_mission(db, mission.id)
    if site is None:
        raise ValueError("Site missing; call generate_synthetic_lunar_site first.")
    scoring = score_site(site, mission)
    return {
        "top_dig_zones": scoring["top_dig_zones"],
        "processor_placement": scoring["processor_placement"],
        "power_placement": scoring["power_placement"],
        "hazard_zones": scoring["hazard_zones"],
        "comms_risk_zones": scoring["comms_risk_zones"],
        "mineability_statistics": scoring["mineability_statistics"],
    }


def tool_seed_default_assets(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    mission = _ensure_mission(db, mission_id)
    assets = seed_default_assets(db, mission)
    return {"assets": [asset_summary(a) for a in assets]}


def tool_generate_balanced_mission_plan(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    mission = _ensure_mission(db, mission_id)
    plan = generate_balanced_plan(db, mission)
    return {
        "plan": serialize_plan(plan),
        "tasks": plan.tasks_json,
        "expected_output_kg": plan.expected_output_kg,
        "confidence_pct": plan.confidence_pct,
        "risk_register": plan.risk_register_json,
        "autonomy_artifacts": plan.autonomy_artifacts_json,
    }


def tool_run_mission_simulation(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    seed = int(payload.get("seed", 42))
    plan_id = payload.get("plan_id")

    mission = _ensure_mission(db, mission_id)
    plan = (
        db.get(Plan, plan_id) if plan_id else latest_plan_for_mission(db, mission.id)
    )
    if plan is None:
        plan = generate_balanced_plan(db, mission)
    sim = run_simulation(db, mission, plan, seed=seed)

    site = get_site_for_mission(db, mission.id)
    scoring = score_site(site, mission)
    anomalies = [
        serialize_anomaly(a) for a in list_anomalies_for_run(db, sim.id)
    ]
    readiness = score_readiness(
        mission=mission,
        sim=sim,
        site_scoring=scoring,
        anomalies_serialized=anomalies,
    )
    sim.readiness_json = readiness
    db.flush()

    return {
        "simulation_run_id": sim.id,
        "metrics": telemetry_summary(sim),
        "readiness": readiness,
        "telemetry_summary": {
            "telemetry_points": len(sim.telemetry_json or []),
            "duration_hours": mission.duration_hours,
        },
        "anomalies": anomalies,
    }


def tool_get_simulation_details(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    sim_id = _need(payload, "simulation_run_id", str)
    sim = db.get(SimulationRun, sim_id)
    if sim is None:
        raise ValueError(f"Simulation run {sim_id} not found.")
    anomalies = [serialize_anomaly(a) for a in list_anomalies_for_run(db, sim.id)]
    return {
        "simulation_run": {
            "id": sim.id,
            "mission_id": sim.mission_id,
            "plan_id": sim.plan_id,
            "seed": sim.seed,
            "status": sim.status,
            "total_output_kg": sim.total_output_kg,
            "total_regolith_moved_kg": sim.total_regolith_moved_kg,
            "average_power_kw": sim.average_power_kw,
            "lowest_battery_margin_pct": sim.lowest_battery_margin_pct,
            "downtime_hours": sim.downtime_hours,
            "anomaly_count": sim.anomaly_count,
            "success_probability_pct": sim.success_probability_pct,
            "created_at": sim.created_at.isoformat(),
        },
        "telemetry": sim.telemetry_json,
        "production_curve": production_curve(sim),
        "battery_curve": battery_curve(sim),
        "power_curve": power_curve(sim),
        "anomalies": anomalies,
        "readiness": sim.readiness_json,
    }


def tool_recommend_anomaly_response(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    sim_id = _need(payload, "simulation_run_id", str)
    anomaly_id = _need(payload, "anomaly_id", str)
    sim = db.get(SimulationRun, sim_id)
    if sim is None:
        raise ValueError(f"Simulation run {sim_id} not found.")
    anomaly = get_anomaly(db, anomaly_id)
    if anomaly is None or anomaly.simulation_run_id != sim_id:
        raise ValueError(
            f"Anomaly {anomaly_id} not found in simulation {sim_id}."
        )
    return recommend_response(db, anomaly)


def tool_create_approval(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    anomaly_id = _need(payload, "anomaly_id", str)
    recommended_action = _need(payload, "recommended_action", str)
    anomaly = get_anomaly(db, anomaly_id)
    if anomaly is None:
        raise ValueError(f"Anomaly {anomaly_id} not found.")

    existing = (
        db.execute(
            select(Approval).where(Approval.anomaly_id == anomaly_id).limit(1)
        )
        .scalars()
        .first()
    )
    if existing:
        return {"approval": serialize_approval(existing)}

    approval = Approval(
        id=str(uuid.uuid4()),
        anomaly_id=anomaly_id,
        recommended_action=recommended_action,
        status="pending",
        operator_note="",
    )
    db.add(approval)
    db.flush()
    return {"approval": serialize_approval(approval)}


def tool_generate_autonomy_artifacts(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    mission = _ensure_mission(db, mission_id)
    plan_id = payload.get("plan_id")
    plan = (
        db.get(Plan, plan_id) if plan_id else latest_plan_for_mission(db, mission.id)
    )
    artifacts = autonomy_artifacts_for_mission(db, mission, plan)
    return artifacts


def tool_generate_mission_report(
    db: Session, payload: Dict[str, Any]
) -> Dict[str, Any]:
    mission_id = _need(payload, "mission_id", str)
    sim_id = _need(payload, "simulation_run_id", str)
    mission = _ensure_mission(db, mission_id)
    sim = db.get(SimulationRun, sim_id)
    if sim is None or sim.mission_id != mission_id:
        raise ValueError(f"Simulation {sim_id} not found for mission {mission_id}.")
    report = generate_report(db, mission, sim)
    return {"markdown": report.markdown, "report_id": report.id}


# Registry table -----------------------------------------------------------


TOOLS: Dict[str, ToolFunc] = {
    "refresh_public_sources": tool_refresh_public_sources,
    "get_source_context": tool_get_source_context,
    "get_mission_context": tool_get_mission_context,
    "generate_synthetic_lunar_site": tool_generate_synthetic_lunar_site,
    "score_site_mineability": tool_score_site_mineability,
    "seed_default_assets": tool_seed_default_assets,
    "generate_balanced_mission_plan": tool_generate_balanced_mission_plan,
    "run_mission_simulation": tool_run_mission_simulation,
    "get_simulation_details": tool_get_simulation_details,
    "recommend_anomaly_response": tool_recommend_anomaly_response,
    "create_approval": tool_create_approval,
    "generate_autonomy_artifacts": tool_generate_autonomy_artifacts,
    "generate_mission_report": tool_generate_mission_report,
}


def execute_tool(
    db: Session, name: str, payload: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if name not in TOOLS:
        raise ValueError(f"Unknown tool '{name}'.")
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValueError("Tool input must be a JSON object.")
    return TOOLS[name](db, payload)


def list_available_actions() -> List[str]:
    return list(TOOLS.keys())
