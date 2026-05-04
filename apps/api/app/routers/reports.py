"""Report routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import SimulationRun
from app.services.mission_service import get_mission
from app.services.report_service import generate_report, latest_report_for_run

router = APIRouter(tags=["reports"])


@router.get("/simulation-runs/{run_id}/report.md", response_class=PlainTextResponse)
def get_report_markdown(
    run_id: str, db: Session = Depends(get_db)
) -> PlainTextResponse:
    sim = db.get(SimulationRun, run_id)
    if sim is None:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    report = latest_report_for_run(db, run_id)
    if report is None:
        mission = get_mission(db, sim.mission_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        report = generate_report(db, mission, sim)
        db.commit()
    return PlainTextResponse(content=report.markdown, media_type="text/markdown")
