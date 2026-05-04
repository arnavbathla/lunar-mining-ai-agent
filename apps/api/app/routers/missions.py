"""Mission lookup routes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.domain import (
    AnomalyOut,
    AssetOut,
    LunarSiteOut,
    MissionOut,
    PlanOut,
    SimulationRunOut,
)
from app.services.anomaly_service import list_anomalies_for_run
from app.services.asset_service import get_assets
from app.services.mission_service import get_mission
from app.services.planning_service import latest_plan_for_mission
from app.services.site_service import get_site_for_mission

router = APIRouter(prefix="/missions", tags=["missions"])


@router.get("/{mission_id}")
def get_mission_route(
    mission_id: str, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    mission = get_mission(db, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    site = get_site_for_mission(db, mission.id)
    assets = get_assets(db, mission.id)
    plan = latest_plan_for_mission(db, mission.id)

    from sqlalchemy import select

    from app.db.models import SimulationRun

    sim = (
        db.execute(
            select(SimulationRun)
            .where(SimulationRun.mission_id == mission.id)
            .order_by(SimulationRun.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    anomalies = list_anomalies_for_run(db, sim.id) if sim else []

    return {
        "mission": MissionOut.model_validate(mission).model_dump(mode="json"),
        "site": LunarSiteOut.model_validate(site).model_dump(mode="json") if site else None,
        "assets": [
            AssetOut.model_validate(a).model_dump(mode="json") for a in assets
        ],
        "latest_plan": PlanOut.model_validate(plan).model_dump(mode="json") if plan else None,
        "latest_simulation": SimulationRunOut.model_validate(sim).model_dump(mode="json") if sim else None,
        "anomalies": [
            AnomalyOut.model_validate(a).model_dump(mode="json") for a in anomalies
        ],
    }
