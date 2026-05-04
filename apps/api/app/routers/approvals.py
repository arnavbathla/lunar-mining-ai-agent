"""Approval routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Approval, SimulationRun
from app.schemas.api import ApprovalAction
from app.schemas.domain import ApprovalOut
from app.services.anomaly_service import list_approvals_for_run

router = APIRouter(tags=["approvals"])


@router.get(
    "/simulation-runs/{run_id}/approvals", response_model=List[ApprovalOut]
)
def list_run_approvals(
    run_id: str, db: Session = Depends(get_db)
) -> List[ApprovalOut]:
    sim = db.get(SimulationRun, run_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return [ApprovalOut.model_validate(a) for a in list_approvals_for_run(db, run_id)]


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut)
def approve(
    approval_id: str,
    action: ApprovalAction = Body(default_factory=ApprovalAction),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = "approved"
    approval.operator_note = action.operator_note or approval.operator_note or ""
    approval.updated_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()
    return ApprovalOut.model_validate(approval)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut)
def reject(
    approval_id: str,
    action: ApprovalAction = Body(default_factory=ApprovalAction),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = "rejected"
    approval.operator_note = action.operator_note or approval.operator_note or ""
    approval.updated_at = datetime.now(timezone.utc)
    db.flush()
    db.commit()
    return ApprovalOut.model_validate(approval)
