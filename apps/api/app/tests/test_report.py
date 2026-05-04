"""Report markdown generator tests."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.asset_service import seed_default_assets
from app.services.mission_service import seed_demo_mission
from app.services.planning_service import generate_balanced_plan
from app.services.readiness_service import score_readiness
from app.services.report_service import generate_report
from app.services.site_service import create_or_replace_site, score_site
from app.services.source_service import ensure_sources_seeded
from app.simulation.engine import run_simulation


def _bootstrap_full(db: Session):
    mission = seed_demo_mission(db)
    db.commit()
    create_or_replace_site(db, mission, seed=42)
    db.commit()
    seed_default_assets(db, mission)
    db.commit()
    plan = generate_balanced_plan(db, mission)
    db.commit()
    ensure_sources_seeded(db)
    db.commit()
    sim = run_simulation(db, mission, plan, seed=42)
    db.commit()

    site = mission.sites[0]
    scoring = score_site(site, mission)
    sim.readiness_json = score_readiness(
        mission=mission,
        sim=sim,
        site_scoring=scoring,
        anomalies_serialized=[],
    )
    db.flush()
    db.commit()
    return mission, sim


def test_report_contains_required_sections(db: Session) -> None:
    mission, sim = _bootstrap_full(db)
    report = generate_report(db, mission, sim)
    db.commit()
    md = report.markdown
    for header in (
        "# Lunar MineOps Mission Readiness Report",
        "## Source Context",
        "## Executive Summary",
        "## Mission Configuration",
        "## Site Intelligence",
        "## Generated Autonomy Plan",
        "## Simulation Results",
        "## Anomaly Response",
        "## Autonomy Artifacts",
        "## Limitations",
    ):
        assert header in md, f"missing header: {header}"


def test_report_includes_readiness_verdict(db: Session) -> None:
    mission, sim = _bootstrap_full(db)
    report = generate_report(db, mission, sim)
    db.commit()
    md = report.markdown.lower()
    assert "mission readiness verdict" in md
    assert any(
        v in md for v in ("go", "conditional go", "no go")
    )


def test_report_includes_limitations(db: Session) -> None:
    mission, sim = _bootstrap_full(db)
    report = generate_report(db, mission, sim)
    db.commit()
    md = report.markdown
    assert "Synthetic terrain" in md
    assert "Simulation only" in md
    assert "Not flight critical" in md
