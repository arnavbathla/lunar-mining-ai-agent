"""Demo mission routes: seed, reset, default-dashboard."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.api import DefaultDashboardOut, DemoSeedOut
from app.schemas.domain import (
    AnomalyOut,
    AssetOut,
    LunarSiteOut,
    MissionOut,
    PlanOut,
    SimulationRunOut,
    SourceDocumentOut,
)
from app.services.anomaly_service import list_anomalies_for_run
from app.services.asset_service import get_assets, seed_default_assets
from app.services.mission_service import (
    find_demo_mission,
    latest_mission,
    reset_all,
    seed_demo_mission,
)
from app.services.planning_service import latest_plan_for_mission
from app.services.site_service import (
    create_or_replace_site,
    get_site_for_mission,
)
from app.services.source_service import ensure_sources_seeded, list_sources, refresh_sources

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed", response_model=DemoSeedOut)
def seed_demo(db: Session = Depends(get_db)) -> DemoSeedOut:
    """Seed (or reuse) the demo mission, site, and assets."""
    mission = seed_demo_mission(db)
    site = get_site_for_mission(db, mission.id) or create_or_replace_site(
        db, mission, seed=42
    )
    assets = get_assets(db, mission.id) or seed_default_assets(db, mission)
    sources = list_sources(db)
    if not sources:
        # Try a live refresh first; fall back to seeded fallback content.
        try:
            result = refresh_sources(db)
            used_fallback = result["used_fallback"]
            sources = list_sources(db)
        except Exception:
            ensure_sources_seeded(db)
            sources = list_sources(db)
            used_fallback = True
    else:
        used_fallback = any(s.is_fallback for s in sources)

    db.commit()

    return DemoSeedOut(
        mission=MissionOut.model_validate(mission),
        site=LunarSiteOut.model_validate(site),
        assets=[AssetOut.model_validate(a) for a in assets],
        sources_count=len(sources),
        sources_used_fallback=used_fallback,
    )


@router.post("/reset")
def reset_demo(db: Session = Depends(get_db)) -> Dict[str, str]:
    reset_all(db)
    db.commit()
    return {"status": "reset"}


@router.get("/default-dashboard", response_model=DefaultDashboardOut)
def default_dashboard(db: Session = Depends(get_db)) -> DefaultDashboardOut:
    mission = find_demo_mission(db) or latest_mission(db)
    if mission is None:
        return DefaultDashboardOut(sources=[
            SourceDocumentOut.model_validate(d) for d in list_sources(db)
        ])
    site = get_site_for_mission(db, mission.id)
    assets = get_assets(db, mission.id)
    plan = latest_plan_for_mission(db, mission.id)

    sim = None
    if mission is not None:
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

    anomalies: List[Any] = []
    if sim is not None:
        anomalies = list_anomalies_for_run(db, sim.id)

    return DefaultDashboardOut(
        mission=MissionOut.model_validate(mission) if mission else None,
        site=LunarSiteOut.model_validate(site) if site else None,
        assets=[AssetOut.model_validate(a) for a in assets],
        latest_plan=PlanOut.model_validate(plan) if plan else None,
        latest_simulation=SimulationRunOut.model_validate(sim) if sim else None,
        anomalies=[AnomalyOut.model_validate(a) for a in anomalies],
        sources=[SourceDocumentOut.model_validate(d) for d in list_sources(db)],
    )
