"""Asset seeding service for the demo mission."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Asset, Mission

DEFAULT_ASSET_SPECS: List[Dict[str, Any]] = [
    {
        "name": "Excavator-1",
        "type": "excavator",
        "max_battery_kwh": 100.0,
        "battery_kwh": 100.0,
        "power_draw_kw": 8.0,
        "max_payload_kg": 0.0,
        "health_pct": 90.0,
        "metadata": {
            "excavation_rate_kg_per_hour": 80.0,
            "cut_depth_cm": 10.0,
            "traction_factor": 0.82,
        },
    },
    {
        "name": "Excavator-2",
        "type": "excavator",
        "max_battery_kwh": 100.0,
        "battery_kwh": 100.0,
        "power_draw_kw": 8.0,
        "max_payload_kg": 0.0,
        "health_pct": 88.0,
        "metadata": {
            "excavation_rate_kg_per_hour": 80.0,
            "cut_depth_cm": 10.0,
            "traction_factor": 0.82,
        },
    },
    {
        "name": "Hauler-1",
        "type": "hauler",
        "max_battery_kwh": 120.0,
        "battery_kwh": 120.0,
        "power_draw_kw": 6.0,
        "max_payload_kg": 200.0,
        "health_pct": 92.0,
        "metadata": {"speed_m_per_hour": 250.0},
    },
    {
        "name": "Hauler-2",
        "type": "hauler",
        "max_battery_kwh": 120.0,
        "battery_kwh": 120.0,
        "power_draw_kw": 6.0,
        "max_payload_kg": 200.0,
        "health_pct": 89.0,
        "metadata": {"speed_m_per_hour": 250.0},
    },
    {
        "name": "Processor-1",
        "type": "processor",
        "max_battery_kwh": 0.0,
        "battery_kwh": 0.0,
        "power_draw_kw": 20.0,
        "max_payload_kg": 0.0,
        "health_pct": 95.0,
        "metadata": {
            "input_rate_kg_per_hour": 120.0,
            "extraction_efficiency_pct": 8.0,
            "output_resource": "water_ice",
        },
    },
    {
        "name": "SolarArray-1",
        "type": "power_unit",
        "max_battery_kwh": 500.0,
        "battery_kwh": 500.0,
        "power_draw_kw": 0.0,
        "max_payload_kg": 0.0,
        "health_pct": 95.0,
        "metadata": {
            "generation_kw": 35.0,
            "storage_kwh": 500.0,
            "uptime_pct": 92.0,
        },
    },
    {
        "name": "InspectionRover-1",
        "type": "inspection_rover",
        "max_battery_kwh": 80.0,
        "battery_kwh": 80.0,
        "power_draw_kw": 3.0,
        "max_payload_kg": 0.0,
        "health_pct": 94.0,
        "metadata": {},
    },
]


def get_assets(db: Session, mission_id: str) -> List[Asset]:
    return list(
        db.execute(
            select(Asset).where(Asset.mission_id == mission_id).order_by(Asset.name)
        )
        .scalars()
        .all()
    )


def seed_default_assets(db: Session, mission: Mission) -> List[Asset]:
    """Idempotently seed the 7 default assets for the demo mission."""
    existing = get_assets(db, mission.id)
    if existing:
        return existing

    created: List[Asset] = []
    for spec in DEFAULT_ASSET_SPECS:
        asset = Asset(
            id=str(uuid.uuid4()),
            mission_id=mission.id,
            name=spec["name"],
            type=spec["type"],
            status="idle",
            battery_kwh=spec["battery_kwh"],
            max_battery_kwh=spec["max_battery_kwh"],
            power_draw_kw=spec["power_draw_kw"],
            location_x=15,
            location_y=15,
            payload_kg=0.0,
            max_payload_kg=spec["max_payload_kg"],
            health_pct=spec["health_pct"],
            metadata_json=spec["metadata"],
        )
        db.add(asset)
        created.append(asset)
    db.flush()
    return created


def asset_summary(asset: Asset) -> Dict[str, Any]:
    return {
        "id": asset.id,
        "name": asset.name,
        "type": asset.type,
        "status": asset.status,
        "battery_kwh": asset.battery_kwh,
        "max_battery_kwh": asset.max_battery_kwh,
        "power_draw_kw": asset.power_draw_kw,
        "location_x": asset.location_x,
        "location_y": asset.location_y,
        "payload_kg": asset.payload_kg,
        "max_payload_kg": asset.max_payload_kg,
        "health_pct": asset.health_pct,
        "metadata": asset.metadata_json,
    }
