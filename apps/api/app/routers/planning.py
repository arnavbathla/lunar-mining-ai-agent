"""Planning routes."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Plan
from app.schemas.domain import PlanOut
from app.services.planning_service import list_plans

router = APIRouter(tags=["planning"])


@router.get("/missions/{mission_id}/plans", response_model=List[PlanOut])
def list_mission_plans(
    mission_id: str, db: Session = Depends(get_db)
) -> List[PlanOut]:
    plans = list_plans(db, mission_id)
    return [PlanOut.model_validate(p) for p in plans]


@router.get("/plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: str, db: Session = Depends(get_db)) -> PlanOut:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanOut.model_validate(plan)
