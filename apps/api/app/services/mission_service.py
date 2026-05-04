"""Mission service: seeded demo + lookup helpers."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Mission

DEMO_MISSION_NAME = "Shackleton Ridge ISRU Demo"
DEMO_OBJECTIVE = (
    "Produce 100 kg water-equivalent output over 168 hours while preserving "
    "25% battery margin and avoiding slopes above 12 degrees."
)


def get_mission(db: Session, mission_id: str) -> Optional[Mission]:
    return db.get(Mission, mission_id)


def find_demo_mission(db: Session) -> Optional[Mission]:
    return (
        db.execute(select(Mission).where(Mission.name == DEMO_MISSION_NAME))
        .scalars()
        .first()
    )


def latest_mission(db: Session) -> Optional[Mission]:
    return (
        db.execute(select(Mission).order_by(Mission.created_at.desc()).limit(1))
        .scalars()
        .first()
    )


def seed_demo_mission(db: Session) -> Mission:
    """Idempotently create the seeded demo mission."""
    existing = find_demo_mission(db)
    if existing:
        return existing

    mission = Mission(
        id=str(uuid.uuid4()),
        name=DEMO_MISSION_NAME,
        objective=DEMO_OBJECTIVE,
        duration_hours=168,
        target_resource="water_ice",
        target_amount_kg=100.0,
        safety_battery_margin_pct=25.0,
        max_slope_deg=12.0,
    )
    db.add(mission)
    db.flush()
    return mission


def reset_all(db: Session) -> None:
    """Wipe all mission-scoped data so /demo/seed gives a fresh state."""
    from app.db.models import (
        Anomaly,
        Approval,
        Asset,
        LunarSite,
        Mission as M,
        Plan,
        Report,
        SimulationRun,
    )

    db.query(Approval).delete()
    db.query(Anomaly).delete()
    db.query(Report).delete()
    db.query(SimulationRun).delete()
    db.query(Plan).delete()
    db.query(Asset).delete()
    db.query(LunarSite).delete()
    db.query(M).delete()
    db.flush()
