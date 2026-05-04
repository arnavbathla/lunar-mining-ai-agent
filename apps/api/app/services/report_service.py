"""Mission readiness report (markdown) generator.

Deterministic generator. The Claude agent loop also routes through
``generate_mission_report`` and may layer additional narrative on top, but
this baseline guarantees a complete and accurate report regardless of LLM
availability.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Anomaly,
    Approval,
    Asset,
    LunarSite,
    Mission,
    Plan,
    Report,
    SimulationRun,
)
from app.services.anomaly_service import (
    list_anomalies_for_run,
    list_approvals_for_run,
)
from app.services.asset_service import get_assets
from app.services.planning_service import latest_plan_for_mission
from app.services.site_service import get_site_for_mission, score_site
from app.services.source_service import list_sources


def _format_sources_section(db: Session) -> str:
    docs = list_sources(db)
    if not docs:
        return "## Source Context\n\nNo source documents present.\n"
    lines = ["## Source Context", ""]
    for d in docs:
        flag = "FALLBACK" if d.is_fallback else "LIVE"
        lines.append(
            f"- **{d.title}** [{flag}] - fetched_at {d.fetched_at.isoformat()} - {d.url}"
        )
    lines.append("")
    lines.append("Source-grounded facts:")
    seen = set()
    for d in docs:
        for cat, fs in (d.extracted_facts_json or {}).items():
            for f in fs[:1]:
                key = f.strip()[:100]
                if key in seen:
                    continue
                seen.add(key)
                lines.append(f"- ({cat}) {f}")
    lines.append("")
    return "\n".join(lines)


def _format_executive_summary(
    mission: Mission,
    sim: SimulationRun,
    readiness: Dict[str, Any],
) -> str:
    target = mission.target_amount_kg
    out = sim.total_output_kg
    bottleneck = "battery margin and route hazard" if sim.lowest_battery_margin_pct < mission.safety_battery_margin_pct else "anomaly cadence"
    verdict = readiness["mission_readiness"]["status"].replace("_", " ").upper()
    return (
        "## Executive Summary\n\n"
        f"- Mission readiness verdict: **{verdict}**\n"
        f"- Target output: {target:.1f} kg | Simulated output: {out:.1f} kg\n"
        f"- Success probability: {sim.success_probability_pct:.1f}%\n"
        f"- Biggest bottleneck: {bottleneck}\n"
        f"- Recommendation: {readiness['mission_readiness']['explanation']}\n"
    )


def _format_mission_config(
    mission: Mission, assets: List[Asset]
) -> str:
    lines = [
        "## Mission Configuration",
        "",
        f"- Duration: {mission.duration_hours} h",
        f"- Target resource: {mission.target_resource}",
        f"- Target amount: {mission.target_amount_kg:.1f} kg",
        f"- Battery safety margin: {mission.safety_battery_margin_pct:.0f}%",
        f"- Max slope: {mission.max_slope_deg:.1f} deg",
        "",
        "Assets:",
    ]
    for a in assets:
        meta = a.metadata_json or {}
        meta_str = ", ".join(f"{k}={v}" for k, v in meta.items())
        lines.append(
            f"- {a.name} ({a.type}) | health={a.health_pct:.0f}% | "
            f"battery={a.battery_kwh:.0f}/{a.max_battery_kwh:.0f} kWh | {meta_str}"
        )
    lines.append("")
    return "\n".join(lines)


def _format_site_intelligence(
    site: LunarSite, mission: Mission
) -> str:
    scoring = score_site(site, mission)
    digs = scoring["top_dig_zones"]
    hazards = scoring["hazard_zones"]
    stats = scoring["mineability_statistics"]
    proc = scoring["processor_placement"]
    power = scoring["power_placement"]

    lines = [
        "## Site Intelligence",
        "",
        f"- Grid: {site.grid_width}x{site.grid_height} cells (synthetic).",
        f"- Avg mineability: {stats.get('avg_mineability_score', 0):.3f}",
        f"- Max mineability: {stats.get('max_mineability_score', 0):.3f}",
        "",
        "Top dig zones:",
    ]
    for c in digs:
        lines.append(
            f"- ({c['x']},{c['y']}) mineability={c['mineability_score']:.3f} "
            f"resource={c['resource_score']:.2f} slope={c['slope_deg']:.1f}deg "
            f"hazard={c['hazard_score']:.2f} comms={c['comms_quality']:.2f} "
            f"illum={c['illumination_pct']:.1f}%"
        )
    lines.append("")
    lines.append(f"Processor placement: ({proc.get('x')},{proc.get('y')}).")
    lines.append(f"Power placement: ({power.get('x')},{power.get('y')}).")
    lines.append("")
    if hazards:
        lines.append("Hazard zones:")
        for h in hazards[:5]:
            lines.append(
                f"- ({h['x']},{h['y']}) hazard={h['hazard_score']:.2f} "
                f"slope={h['slope_deg']:.1f}deg"
            )
    lines.append("")
    return "\n".join(lines)


def _format_plan_section(plan: Plan) -> str:
    tasks = plan.tasks_json or []
    risks = plan.risk_register_json or []
    artifacts = plan.autonomy_artifacts_json or {}

    lines = [
        "## Generated Autonomy Plan",
        "",
        f"- Summary: {plan.summary}",
        f"- Expected output: {plan.expected_output_kg:.1f} kg",
        f"- Confidence: {plan.confidence_pct:.1f}%",
        f"- Total tasks: {len(tasks)}",
        "",
        "Risk register:",
    ]
    for r in risks:
        lines.append(
            f"- [{r['severity']}/{r['likelihood']}] {r['risk']} -> {r['mitigation']}"
        )
    lines.append("")
    lines.append("Top 8 tasks:")
    for t in sorted(tasks, key=lambda x: x["start_hour"])[:8]:
        lines.append(
            f"- h{t['start_hour']:>3}-{t['end_hour']:>3} | {t['asset_name']:<18} | "
            f"{t['task_type']:<11} | {t.get('rationale', '')[:80]}"
        )
    lines.append("")
    return "\n".join(lines)


def _format_simulation_section(sim: SimulationRun) -> str:
    return (
        "## Simulation Results\n\n"
        f"- Total output: {sim.total_output_kg:.1f} kg water-ice equivalent\n"
        f"- Regolith moved: {sim.total_regolith_moved_kg:.1f} kg\n"
        f"- Average power: {sim.average_power_kw:.1f} kW\n"
        f"- Lowest battery margin: {sim.lowest_battery_margin_pct:.1f}%\n"
        f"- Downtime: {sim.downtime_hours:.1f} h\n"
        f"- Anomalies: {sim.anomaly_count}\n"
        f"- Success probability: {sim.success_probability_pct:.1f}%\n"
    )


def _format_anomaly_section(
    db: Session, sim: SimulationRun
) -> str:
    anomalies = list_anomalies_for_run(db, sim.id)
    approvals = {a.anomaly_id: a for a in list_approvals_for_run(db, sim.id)}
    lines = ["## Anomaly Response", ""]
    if not anomalies:
        lines.append("- No anomalies recorded.")
    for a in anomalies:
        ap = approvals.get(a.id)
        ap_status = ap.status if ap else "none"
        lines.append(
            f"- h{a.hour:>3} | {a.severity:<8} | {a.type:<18} | asset={a.asset_id or '-'} | "
            f"impact={a.production_impact_kg:.2f} kg | approval={ap_status}"
        )
        lines.append(f"    root_cause: {a.root_cause_hypothesis}")
        lines.append(f"    action: {a.recommended_action}")
    lines.append("")
    return "\n".join(lines)


def _format_artifacts_section(plan: Plan) -> str:
    artifacts = plan.autonomy_artifacts_json or {}
    bt = artifacts.get("behavior_tree", "(missing)")
    sm = artifacts.get("state_machine", "(missing)")
    runbook = artifacts.get("operator_runbook", "(missing)")
    ros = artifacts.get("ros_task_messages", [])
    sample_msg = ros[0] if ros else {
        "asset_id": "Excavator-1",
        "task_type": "excavate",
        "target_zone": {"x": 12, "y": 18},
        "duration_hours": 3,
        "constraints": {
            "min_battery_pct": 25,
            "max_slope_deg": 12,
            "abort_on_comms_loss": False,
        },
    }
    import json as _json

    return (
        "## Autonomy Artifacts\n\n"
        "Behavior tree:\n```\n"
        f"{bt}\n"
        "```\n\n"
        "ROS-style task message example:\n```json\n"
        f"{_json.dumps(sample_msg, indent=2)}\n"
        "```\n\n"
        "State machine:\n```\n"
        f"{sm}\n"
        "```\n\n"
        "Operator runbook:\n```\n"
        f"{runbook}\n"
        "```\n"
    )


def _format_limitations() -> str:
    return (
        "## Limitations\n\n"
        "- Synthetic terrain; not derived from raw LOLA DEM products.\n"
        "- Public-source context only; no proprietary mission data.\n"
        "- Simulation only - no real hardware control.\n"
        "- Not flight critical; autonomy artifacts are draft.\n"
        "- No raw DEM ingestion in v1.\n"
    )


def _build_markdown(
    db: Session,
    mission: Mission,
    site: LunarSite,
    plan: Plan,
    sim: SimulationRun,
    readiness: Dict[str, Any],
) -> str:
    assets = get_assets(db, mission.id)
    parts = [
        "# Lunar MineOps Mission Readiness Report",
        "",
        f"_Mission: {mission.name}_",
        "",
        _format_sources_section(db),
        _format_executive_summary(mission, sim, readiness),
        _format_mission_config(mission, assets),
        _format_site_intelligence(site, mission),
        _format_plan_section(plan),
        _format_simulation_section(sim),
        _format_anomaly_section(db, sim),
        _format_artifacts_section(plan),
        _format_limitations(),
    ]
    return "\n".join(parts)


def generate_report(
    db: Session,
    mission: Mission,
    sim: SimulationRun,
) -> Report:
    """Build markdown report and persist a Report row."""
    site = get_site_for_mission(db, mission.id)
    if site is None:
        raise ValueError("Site missing.")
    plan = db.get(Plan, sim.plan_id)
    if plan is None:
        plan = latest_plan_for_mission(db, mission.id)
    if plan is None:
        raise ValueError("Plan missing.")
    readiness = sim.readiness_json or {}
    md = _build_markdown(db, mission, site, plan, sim, readiness)

    report = Report(
        id=str(uuid.uuid4()),
        mission_id=mission.id,
        simulation_run_id=sim.id,
        markdown=md,
    )
    db.add(report)
    db.flush()
    return report


def latest_report_for_run(
    db: Session, simulation_run_id: str
) -> Optional[Report]:
    return (
        db.execute(
            select(Report)
            .where(Report.simulation_run_id == simulation_run_id)
            .order_by(Report.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
