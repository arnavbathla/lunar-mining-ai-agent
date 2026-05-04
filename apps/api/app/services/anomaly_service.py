"""Anomaly response service: lookups + recommendation generator."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Anomaly, Approval, Asset, SimulationRun


def list_anomalies_for_run(
    db: Session, simulation_run_id: str
) -> List[Anomaly]:
    return list(
        db.execute(
            select(Anomaly)
            .where(Anomaly.simulation_run_id == simulation_run_id)
            .order_by(Anomaly.hour)
        )
        .scalars()
        .all()
    )


def get_anomaly(db: Session, anomaly_id: str) -> Optional[Anomaly]:
    return db.get(Anomaly, anomaly_id)


def serialize_anomaly(a: Anomaly) -> Dict[str, Any]:
    return {
        "id": a.id,
        "simulation_run_id": a.simulation_run_id,
        "hour": a.hour,
        "asset_id": a.asset_id,
        "type": a.type,
        "severity": a.severity,
        "description": a.description,
        "root_cause_hypothesis": a.root_cause_hypothesis,
        "recommended_action": a.recommended_action,
        "production_impact_kg": a.production_impact_kg,
        "requires_human_approval": bool(a.requires_human_approval),
        "created_at": a.created_at.isoformat(),
    }


def recommend_response(
    db: Session, anomaly: Anomaly
) -> Dict[str, Any]:
    """Build a structured anomaly response recommendation.

    The Claude agent layers tone and explanation on top of this; this
    deterministic core ensures the agent always has a grounded answer.
    """
    severity = anomaly.severity
    confidence = {
        "low": 78.0,
        "medium": 72.0,
        "high": 66.0,
        "critical": 60.0,
    }.get(severity, 70.0)

    alternative_actions = _alternatives_for(anomaly.type)
    safety_impact = _safety_impact_for(anomaly.type, severity)

    return {
        "root_cause_hypothesis": anomaly.root_cause_hypothesis,
        "recommended_action": anomaly.recommended_action,
        "alternative_actions": alternative_actions,
        "safety_impact": safety_impact,
        "production_impact_kg": anomaly.production_impact_kg,
        "approval_required": bool(anomaly.requires_human_approval),
        "confidence_pct": confidence,
    }


def _alternatives_for(anom_type: str) -> List[str]:
    table = {
        "wheel_slip": [
            "Switch to lower gear and reduce traverse speed.",
            "Reroute via cells with slope < mission limit.",
        ],
        "dust_on_solar": [
            "Manual operator wipe pass on solar array (deferred operation).",
            "Reduce processor utilization to 50% until mitigation completes.",
        ],
        "processor_overheat": [
            "Pause processor 2 hours then resume at 70% utilization.",
            "Run forced cooling cycle between 20-min processing windows.",
        ],
        "low_battery": [
            "Stagger remaining haul cycles onto second hauler.",
            "Defer non-critical tasks until battery reaches 50%.",
        ],
        "route_blocked": [
            "Use alternate corridor through cells with verified comms.",
            "Hold haul cycles for 2 hours pending inspection sweep.",
        ],
        "comms_blackout": [
            "Continue local plan execution until next comms window.",
            "Trigger SAFE_MODE if blackout exceeds expected window.",
        ],
        "excavator_jam": [
            "Run reverse-bucket clear sequence twice.",
            "Switch to second excavator for remainder of cycle.",
        ],
        "hauler_fault": [
            "Drop payload at staging buffer for manual recovery.",
            "Schedule mid-mission maintenance within 6 hours.",
        ],
    }
    return table.get(anom_type, ["Investigate further; revise plan if recurring."])


def _safety_impact_for(anom_type: str, severity: str) -> str:
    if severity == "critical":
        return "Critical safety impact; human approval required before any further automated action."
    if severity == "high":
        return "Elevated safety risk; recommend operator review prior to next cycle."
    return "Limited safety impact; automated mitigation acceptable with logging."


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


def list_approvals_for_run(
    db: Session, simulation_run_id: str
) -> List[Approval]:
    rows = (
        db.execute(
            select(Approval, Anomaly)
            .join(Anomaly, Anomaly.id == Approval.anomaly_id)
            .where(Anomaly.simulation_run_id == simulation_run_id)
            .order_by(Approval.created_at)
        )
        .all()
    )
    return [r[0] for r in rows]


def serialize_approval(a: Approval) -> Dict[str, Any]:
    return {
        "id": a.id,
        "anomaly_id": a.anomaly_id,
        "recommended_action": a.recommended_action,
        "status": a.status,
        "operator_note": a.operator_note,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }
