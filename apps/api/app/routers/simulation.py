"""Simulation routes."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import SimulationRun
from app.schemas.domain import AnomalyOut, SimulationRunOut
from app.services.anomaly_service import list_anomalies_for_run

router = APIRouter(tags=["simulation"])


@router.get("/simulation-runs/{run_id}", response_model=SimulationRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)) -> SimulationRunOut:
    sim = db.get(SimulationRun, run_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return SimulationRunOut.model_validate(sim)


@router.get("/simulation-runs/{run_id}/telemetry")
def get_telemetry(run_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    sim = db.get(SimulationRun, run_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    from app.simulation.engine import battery_curve, power_curve, production_curve

    return {
        "telemetry": sim.telemetry_json,
        "production_curve": production_curve(sim),
        "battery_curve": battery_curve(sim),
        "power_curve": power_curve(sim),
    }


@router.get(
    "/simulation-runs/{run_id}/anomalies", response_model=List[AnomalyOut]
)
def get_run_anomalies(
    run_id: str, db: Session = Depends(get_db)
) -> List[AnomalyOut]:
    sim = db.get(SimulationRun, run_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return [
        AnomalyOut.model_validate(a) for a in list_anomalies_for_run(db, run_id)
    ]
