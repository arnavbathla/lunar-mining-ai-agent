"""Asset seed tests."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.asset_service import (
    DEFAULT_ASSET_SPECS,
    get_assets,
    seed_default_assets,
)
from app.services.mission_service import seed_demo_mission


EXPECTED_NAMES = {spec["name"] for spec in DEFAULT_ASSET_SPECS}
EXPECTED_TYPES = {spec["type"] for spec in DEFAULT_ASSET_SPECS}


def test_seeded_assets_are_created(db: Session) -> None:
    mission = seed_demo_mission(db)
    db.commit()
    seed_default_assets(db, mission)
    db.commit()

    assets = get_assets(db, mission.id)
    assert len(assets) == len(DEFAULT_ASSET_SPECS)
    assert {a.name for a in assets} == EXPECTED_NAMES
    assert {a.type for a in assets} >= EXPECTED_TYPES - {"power_unit"} | {"power_unit"}


def test_idempotent_seed(db: Session) -> None:
    mission = seed_demo_mission(db)
    db.commit()
    first = seed_default_assets(db, mission)
    second = seed_default_assets(db, mission)
    assert {a.id for a in first} == {a.id for a in second}
