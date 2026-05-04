"""API request/response schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.domain import (
    AnomalyOut,
    ApprovalOut,
    AssetOut,
    LunarSiteOut,
    MissionOut,
    PlanOut,
    SimulationRunOut,
    SourceDocumentOut,
)


class HealthOut(BaseModel):
    status: str = "ok"
    anthropic_configured: bool


class DemoSeedOut(BaseModel):
    mission: MissionOut
    site: LunarSiteOut
    assets: List[AssetOut]
    sources_count: int
    sources_used_fallback: bool


class DefaultDashboardOut(BaseModel):
    mission: Optional[MissionOut] = None
    site: Optional[LunarSiteOut] = None
    assets: List[AssetOut] = []
    latest_plan: Optional[PlanOut] = None
    latest_simulation: Optional[SimulationRunOut] = None
    anomalies: List[AnomalyOut] = []
    sources: List[SourceDocumentOut] = []


class SourcesContextOut(BaseModel):
    last_refreshed_at: Optional[str] = None
    used_fallback: bool
    facts: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]


class SourcesRefreshOut(BaseModel):
    refreshed: int
    failed: int
    used_fallback: bool
    sources: List[SourceDocumentOut]


class ApprovalAction(BaseModel):
    operator_note: Optional[str] = None


class AgentStatusOut(BaseModel):
    anthropic_configured: bool
    model: str
    available_agent_actions: List[str]


class AgentRunReadinessRequest(BaseModel):
    mission_id: str
    seed: int = 42


class AgentAnomalyResponseRequest(BaseModel):
    simulation_run_id: str
    anomaly_id: str


class AgentReportRequest(BaseModel):
    mission_id: str
    simulation_run_id: str


class AgentRunReadinessOut(BaseModel):
    agent_run_id: str
    tool_calls: List[Dict[str, Any]]
    plan: Optional[Dict[str, Any]] = None
    simulation: Optional[Dict[str, Any]] = None
    readiness: Optional[Dict[str, Any]] = None
    executive_recommendation: str = ""
    source_grounding_summary: str = ""
    next_actions: List[str] = []
    model: str
    created_at: str


class AgentAnomalyResponseOut(BaseModel):
    agent_run_id: str
    tool_calls: List[Dict[str, Any]]
    recommendation: Dict[str, Any] = Field(default_factory=dict)
    approval_id: Optional[str] = None
    operator_message: str = ""
    model: str
    created_at: str


class AgentReportOut(BaseModel):
    agent_run_id: str
    tool_calls: List[Dict[str, Any]]
    report_id: Optional[str] = None
    markdown: str
    model: str
    created_at: str
