"""Domain Pydantic schemas - mirror SQLAlchemy models for API responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SourceDocumentOut(_Base):
    id: str
    url: str
    title: str
    fetched_at: datetime
    status: str
    content_hash: str
    raw_excerpt: str
    extracted_facts_json: Dict[str, Any] = {}
    is_fallback: bool


class MissionOut(_Base):
    id: str
    name: str
    objective: str
    duration_hours: int
    target_resource: str
    target_amount_kg: float
    safety_battery_margin_pct: float
    max_slope_deg: float
    created_at: datetime


class CellOut(BaseModel):
    x: int
    y: int
    elevation_m: float
    slope_deg: float
    illumination_pct: float
    resource_score: float
    hazard_score: float
    comms_quality: float
    temperature_c: float
    mineability_score: float


class LunarSiteOut(_Base):
    id: str
    mission_id: str
    name: str
    region: str
    grid_width: int
    grid_height: int
    cells_json: List[Dict[str, Any]]
    created_at: datetime


class AssetOut(_Base):
    id: str
    mission_id: str
    name: str
    type: str
    status: str
    battery_kwh: float
    max_battery_kwh: float
    power_draw_kw: float
    location_x: int
    location_y: int
    payload_kg: float
    max_payload_kg: float
    health_pct: float
    metadata_json: Dict[str, Any] = {}
    created_at: datetime


class TaskOut(BaseModel):
    id: str
    asset_id: str
    asset_name: str
    task_type: str
    start_hour: int
    end_hour: int
    from_location: Optional[Dict[str, int]] = None
    to_location: Optional[Dict[str, int]] = None
    expected_output_kg: float = 0.0
    power_required_kwh: float = 0.0
    rationale: str = ""
    status: str = "scheduled"


class RiskItem(BaseModel):
    risk: str
    severity: str
    likelihood: str
    mitigation: str


class AutonomyArtifacts(BaseModel):
    behavior_tree: str
    ros_task_messages: List[Dict[str, Any]]
    state_machine: str
    operator_runbook: str


class PlanOut(_Base):
    id: str
    mission_id: str
    summary: str
    tasks_json: List[Dict[str, Any]]
    risk_register_json: List[Dict[str, Any]]
    expected_output_kg: float
    confidence_pct: float
    autonomy_artifacts_json: Dict[str, Any]
    created_at: datetime


class TelemetryPoint(BaseModel):
    hour: int
    asset_id: str
    asset_name: str
    status: str
    battery_pct: float
    location_x: int
    location_y: int
    payload_kg: float
    health_pct: float
    power_kw: float
    cumulative_output_kg: float
    cumulative_regolith_moved_kg: float
    alert_level: str


class ReadinessDimension(BaseModel):
    status: str
    explanation: str


class ReadinessJSON(BaseModel):
    site_mineability: ReadinessDimension
    production_target: ReadinessDimension
    power_budget: ReadinessDimension
    autonomy_risk: ReadinessDimension
    mission_readiness: ReadinessDimension


class SimulationRunOut(_Base):
    id: str
    mission_id: str
    plan_id: str
    seed: int
    status: str
    total_output_kg: float
    total_regolith_moved_kg: float
    average_power_kw: float
    lowest_battery_margin_pct: float
    downtime_hours: float
    anomaly_count: int
    success_probability_pct: float
    telemetry_json: List[Dict[str, Any]]
    readiness_json: Dict[str, Any]
    created_at: datetime


class AnomalyOut(_Base):
    id: str
    simulation_run_id: str
    hour: int
    asset_id: Optional[str] = None
    type: str
    severity: str
    description: str
    root_cause_hypothesis: str
    recommended_action: str
    production_impact_kg: float
    requires_human_approval: bool
    created_at: datetime


class ApprovalOut(_Base):
    id: str
    anomaly_id: str
    recommended_action: str
    status: str
    operator_note: str
    created_at: datetime
    updated_at: datetime


class AgentRunOut(_Base):
    id: str
    mission_id: Optional[str]
    agent_type: str
    model: str
    input_prompt: str
    tool_calls_json: List[Dict[str, Any]]
    final_response_json: Dict[str, Any]
    final_markdown: str
    created_at: datetime


class ReportOut(_Base):
    id: str
    mission_id: str
    simulation_run_id: str
    markdown: str
    created_at: datetime
