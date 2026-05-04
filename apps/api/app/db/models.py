"""SQLAlchemy ORM models for Lunar MineOps AI OS."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="ok")
    content_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
    raw_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extracted_facts_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    is_fallback: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=168)
    target_resource: Mapped[str] = mapped_column(String, nullable=False, default="water_ice")
    target_amount_kg: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    safety_battery_margin_pct: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    max_slope_deg: Mapped[float] = mapped_column(Float, nullable=False, default=12.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    sites: Mapped[list["LunarSite"]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    plans: Mapped[list["Plan"]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    simulation_runs: Mapped[list["SimulationRun"]] = relationship(
        back_populates="mission", cascade="all, delete-orphan"
    )


class LunarSite(Base):
    __tablename__ = "lunar_sites"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, default="Synthetic Polar Site")
    region: Mapped[str] = mapped_column(String, nullable=False, default="south_pole")
    grid_width: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    grid_height: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    cells_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    mission: Mapped[Mission] = relationship(back_populates="sites")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="idle")
    battery_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_battery_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    power_draw_kw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    location_x: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    location_y: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_payload_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    health_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    metadata_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    mission: Mapped[Mission] = relationship(back_populates="assets")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tasks_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    risk_register_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    expected_output_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    autonomy_artifacts_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    mission: Mapped[Mission] = relationship(back_populates="plans")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    total_output_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_regolith_moved_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    average_power_kw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lowest_battery_margin_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    downtime_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_probability_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    telemetry_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    readiness_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    mission: Mapped[Mission] = relationship(back_populates="simulation_runs")
    anomalies: Mapped[list["Anomaly"]] = relationship(
        back_populates="simulation_run", cascade="all, delete-orphan"
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.id"), nullable=False
    )
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    asset_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    root_cause_hypothesis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    production_impact_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    requires_human_approval: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    simulation_run: Mapped[SimulationRun] = relationship(back_populates="anomalies")
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="anomaly", cascade="all, delete-orphan"
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    anomaly_id: Mapped[str] = mapped_column(ForeignKey("anomalies.id"), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    operator_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    anomaly: Mapped[Anomaly] = relationship(back_populates="approvals")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    agent_type: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False, default="")
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_calls_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    final_response_json: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    final_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id"), nullable=False)
    simulation_run_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.id"), nullable=False
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
