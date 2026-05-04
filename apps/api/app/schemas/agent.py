"""Tool I/O schemas for the Anthropic Claude tool-use agent."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    name: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    is_error: bool = False
    iteration: int = 0


class AgentInvocation(BaseModel):
    agent_run_id: str
    tool_calls: List[ToolCallRecord]
    final_text: str
    final_json: Dict[str, Any]
    model: str
    created_at: str


class RefreshSourcesInput(BaseModel):
    force: bool = False


class GetSourceContextInput(BaseModel):
    categories: List[str] = Field(default_factory=list)


class GetMissionContextInput(BaseModel):
    mission_id: str


class GenerateSyntheticLunarSiteInput(BaseModel):
    mission_id: str
    seed: int = 42


class ScoreSiteMineabilityInput(BaseModel):
    mission_id: str


class SeedDefaultAssetsInput(BaseModel):
    mission_id: str


class GenerateBalancedPlanInput(BaseModel):
    mission_id: str


class RunMissionSimulationInput(BaseModel):
    mission_id: str
    plan_id: Optional[str] = None
    seed: int = 42


class GetSimulationDetailsInput(BaseModel):
    simulation_run_id: str


class RecommendAnomalyResponseInput(BaseModel):
    simulation_run_id: str
    anomaly_id: str


class CreateApprovalInput(BaseModel):
    anomaly_id: str
    recommended_action: str


class GenerateAutonomyArtifactsInput(BaseModel):
    mission_id: str
    plan_id: Optional[str] = None


class GenerateMissionReportInput(BaseModel):
    mission_id: str
    simulation_run_id: str
