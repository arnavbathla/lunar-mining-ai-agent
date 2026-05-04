"""Balanced mission planning service."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Asset, LunarSite, Mission, Plan
from app.services.asset_service import get_assets
from app.services.site_service import (
    get_site_for_mission,
    score_site,
)


# ---------------------------------------------------------------------------
# Public lookups
# ---------------------------------------------------------------------------


def latest_plan_for_mission(db: Session, mission_id: str) -> Optional[Plan]:
    return (
        db.execute(
            select(Plan)
            .where(Plan.mission_id == mission_id)
            .order_by(Plan.created_at.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def list_plans(db: Session, mission_id: str) -> List[Plan]:
    return list(
        db.execute(
            select(Plan)
            .where(Plan.mission_id == mission_id)
            .order_by(Plan.created_at.desc())
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Plan construction
# ---------------------------------------------------------------------------


def _select_dig_zones(scoring: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = scoring.get("top_dig_zones", []) or []
    chosen = [c for c in candidates if c["mineability_score"] >= 0.60][:2]
    if not chosen and candidates:
        chosen = candidates[:1]
    return chosen


def _route_distance(
    a: Dict[str, Any], b: Dict[str, Any]
) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def _build_tasks(
    mission: Mission,
    assets: List[Asset],
    dig_zones: List[Dict[str, Any]],
    processor_cell: Dict[str, Any],
    power_cell: Dict[str, Any],
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []

    by_name = {a.name: a for a in assets}
    excavators = [by_name.get("Excavator-1"), by_name.get("Excavator-2")]
    haulers = [by_name.get("Hauler-1"), by_name.get("Hauler-2")]
    processor = by_name.get("Processor-1")
    inspector = by_name.get("InspectionRover-1")
    solar = by_name.get("SolarArray-1")

    duration = mission.duration_hours
    excav_window = 6  # hours per cycle
    cycle_len = excav_window + 2  # excavate then alternate with charge gap

    if not dig_zones:
        # Fall back to a placeholder zone at processor.
        dig_zones = [processor_cell]

    def make_task(
        asset: Asset,
        task_type: str,
        start: int,
        end: int,
        from_loc: Optional[Dict[str, int]] = None,
        to_loc: Optional[Dict[str, int]] = None,
        expected_output: float = 0.0,
        power: float = 0.0,
        rationale: str = "",
    ) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "asset_id": asset.id,
            "asset_name": asset.name,
            "task_type": task_type,
            "start_hour": start,
            "end_hour": end,
            "from_location": from_loc,
            "to_location": to_loc,
            "expected_output_kg": round(expected_output, 2),
            "power_required_kwh": round(power, 2),
            "rationale": rationale,
            "status": "scheduled",
        }

    # Alternating excavation windows for the two excavators
    for i, excavator in enumerate(excavators):
        if not excavator:
            continue
        zone = dig_zones[i % len(dig_zones)]
        rate = float(excavator.metadata_json.get("excavation_rate_kg_per_hour", 80.0))
        offset = i * (cycle_len // 2)
        hour = offset
        while hour + excav_window <= duration:
            expected = rate * excav_window * 0.85  # regolith kg
            tasks.append(
                make_task(
                    excavator,
                    "excavate",
                    hour,
                    hour + excav_window,
                    from_loc={"x": zone["x"], "y": zone["y"]},
                    to_loc={"x": zone["x"], "y": zone["y"]},
                    expected_output=expected,
                    power=excavator.power_draw_kw * excav_window,
                    rationale=(
                        f"Excavate dig zone ({zone['x']},{zone['y']}) "
                        f"with mineability={zone['mineability_score']:.2f}."
                    ),
                )
            )
            hour += cycle_len * 2  # leave room for charge cycle

    # Haul loops alternate between the two haulers
    haul_window = 4
    for i, hauler in enumerate(haulers):
        if not hauler:
            continue
        zone = dig_zones[i % len(dig_zones)]
        offset = i * 2
        hour = offset
        while hour + haul_window <= duration:
            tasks.append(
                make_task(
                    hauler,
                    "haul",
                    hour,
                    hour + haul_window,
                    from_loc={"x": zone["x"], "y": zone["y"]},
                    to_loc={"x": processor_cell["x"], "y": processor_cell["y"]},
                    expected_output=0.0,
                    power=hauler.power_draw_kw * haul_window,
                    rationale=(
                        f"Haul payload from ({zone['x']},{zone['y']}) to processor "
                        f"({processor_cell['x']},{processor_cell['y']})."
                    ),
                )
            )
            hour += cycle_len * 2

    # Processor runs in 8-hour blocks, target 70-85% utilization
    if processor:
        proc_window = 8
        rate = float(processor.metadata_json.get("input_rate_kg_per_hour", 120.0))
        eff = float(processor.metadata_json.get("extraction_efficiency_pct", 8.0))
        per_block_input = rate * proc_window * 0.78  # ~78% utilization target
        per_block_output = per_block_input * (eff / 100.0)
        hour = 2
        while hour + proc_window <= duration:
            tasks.append(
                make_task(
                    processor,
                    "process",
                    hour,
                    hour + proc_window,
                    from_loc={"x": processor_cell["x"], "y": processor_cell["y"]},
                    to_loc={"x": processor_cell["x"], "y": processor_cell["y"]},
                    expected_output=per_block_output,
                    power=processor.power_draw_kw * proc_window,
                    rationale=(
                        f"Process regolith @ ~78% utilization. "
                        f"Expected water-ice yield ~{per_block_output:.1f} kg/block."
                    ),
                )
            )
            hour += proc_window + 2

    # Charging cycles preserved before battery dips below 30%
    for asset in [*excavators, *haulers, inspector]:
        if not asset:
            continue
        charge_every = 18 if asset.type == "hauler" else 22
        charge_dur = 3
        hour = charge_every
        while hour + charge_dur <= duration:
            tasks.append(
                make_task(
                    asset,
                    "charge",
                    hour,
                    hour + charge_dur,
                    from_loc={"x": power_cell["x"], "y": power_cell["y"]},
                    to_loc={"x": power_cell["x"], "y": power_cell["y"]},
                    expected_output=0.0,
                    power=-asset.max_battery_kwh * 0.5,  # charge magnitude
                    rationale="Charge to maintain >30% battery margin and preserve safety margin.",
                )
            )
            hour += charge_every

    # Inspection rover sweeps every 24h
    if inspector:
        hour = 12
        sweep = 2
        while hour + sweep <= duration:
            tasks.append(
                make_task(
                    inspector,
                    "inspect",
                    hour,
                    hour + sweep,
                    from_loc={"x": power_cell["x"], "y": power_cell["y"]},
                    to_loc={"x": dig_zones[0]["x"], "y": dig_zones[0]["y"]},
                    expected_output=0.0,
                    power=inspector.power_draw_kw * sweep,
                    rationale="Inspection sweep for hazard updates and route validation.",
                )
            )
            hour += 24

    # SolarArray uptime maintenance (low-touch)
    if solar:
        tasks.append(
            make_task(
                solar,
                "maintenance",
                0,
                duration,
                from_loc={"x": power_cell["x"], "y": power_cell["y"]},
                to_loc={"x": power_cell["x"], "y": power_cell["y"]},
                expected_output=0.0,
                power=0.0,
                rationale="Continuous solar generation with periodic dust-mitigation passes.",
            )
        )

    # Contingency: safe_mode block placeholder for high-risk segment near hour 96
    if excavators and excavators[0]:
        tasks.append(
            make_task(
                excavators[0],
                "safe_mode",
                96,
                98,
                from_loc={"x": dig_zones[0]["x"], "y": dig_zones[0]["y"]},
                to_loc={"x": power_cell["x"], "y": power_cell["y"]},
                expected_output=0.0,
                power=0.0,
                rationale="Reserved safe-mode buffer for high-risk slope traversal segment.",
            )
        )

    tasks.sort(key=lambda t: (t["start_hour"], t["asset_name"]))
    return tasks


def _risk_register(
    mission: Mission,
    scoring: Dict[str, Any],
) -> List[Dict[str, str]]:
    risks = [
        {
            "risk": "Slope traversal exceeding mission limit",
            "severity": "high",
            "likelihood": "medium",
            "mitigation": (
                f"Restrict routes to <= {mission.max_slope_deg:.1f} deg slope; "
                "use inspection rover before haul cycles."
            ),
        },
        {
            "risk": "Battery margin breach during peak processing",
            "severity": "high",
            "likelihood": "medium",
            "mitigation": (
                f"Maintain {mission.safety_battery_margin_pct:.0f}% safety margin; "
                "stagger charge cycles before margin breach."
            ),
        },
        {
            "risk": "Comms shadow during haul",
            "severity": "medium",
            "likelihood": "medium",
            "mitigation": "Pre-stage haul payload within strong-comms cells; abort_on_comms_loss=false for short windows.",
        },
        {
            "risk": "Processor under-utilization vs target",
            "severity": "medium",
            "likelihood": "low",
            "mitigation": "Hold buffer regolith inventory >= 1 processor-block; resequence haulers if buffer drops.",
        },
        {
            "risk": "Hazard zone proximity for dig zone 2",
            "severity": "medium",
            "likelihood": "medium",
            "mitigation": "Maintain 4-cell buffer from hazard centroids; defer to dig zone 1 if hazard score rises.",
        },
    ]
    if scoring.get("comms_risk_zones"):
        risks.append(
            {
                "risk": "Comms-risk zones present near route",
                "severity": "medium",
                "likelihood": "high",
                "mitigation": "Route haulers around comms-risk cells; queue messages for transit through shadow.",
            }
        )
    return risks


def _autonomy_artifacts(
    mission: Mission,
    assets: List[Asset],
    dig_zones: List[Dict[str, Any]],
    processor_cell: Dict[str, Any],
) -> Dict[str, Any]:
    behavior_tree = (
        "Root\n"
        "  CheckPowerMargin\n"
        "  CheckCommsWindow\n"
        "  NavigateToDigZone\n"
        "  ExcavateUntilPayloadReady\n"
        "  DispatchHauler\n"
        "  DeliverToProcessor\n"
        "  ProcessRegolith\n"
        "  ReturnToChargeIfNeeded\n"
        "  HandleAnomaly"
    )

    state_machine = (
        "IDLE -> NAVIGATING -> EXCAVATING -> WAITING_FOR_HAULER "
        "-> RETURNING -> CHARGING -> IDLE\n"
        "FAULT -> SAFE_MODE"
    )

    ros_messages: List[Dict[str, Any]] = []
    by_name = {a.name: a for a in assets}
    if by_name.get("Excavator-1") and dig_zones:
        ros_messages.append(
            {
                "asset_id": "Excavator-1",
                "task_type": "excavate",
                "target_zone": {"x": dig_zones[0]["x"], "y": dig_zones[0]["y"]},
                "duration_hours": 3,
                "constraints": {
                    "min_battery_pct": int(mission.safety_battery_margin_pct),
                    "max_slope_deg": int(mission.max_slope_deg),
                    "abort_on_comms_loss": False,
                },
            }
        )
    if by_name.get("Hauler-1") and dig_zones:
        ros_messages.append(
            {
                "asset_id": "Hauler-1",
                "task_type": "haul",
                "from_zone": {"x": dig_zones[0]["x"], "y": dig_zones[0]["y"]},
                "to_zone": {"x": processor_cell["x"], "y": processor_cell["y"]},
                "duration_hours": 2,
                "constraints": {
                    "min_battery_pct": int(mission.safety_battery_margin_pct),
                    "max_payload_kg": 200,
                    "abort_on_comms_loss": False,
                },
            }
        )
    if by_name.get("Processor-1"):
        ros_messages.append(
            {
                "asset_id": "Processor-1",
                "task_type": "process",
                "target_resource": mission.target_resource,
                "duration_hours": 8,
                "constraints": {
                    "min_input_buffer_kg": 100,
                    "max_temperature_c": 60,
                    "shutdown_on_low_power": True,
                },
            }
        )

    operator_runbook = (
        "Operator Runbook (Draft - Simulation Only / Not Flight Critical)\n"
        "-----------------------------------------------------------\n"
        "1. Verify source context freshness in the dashboard.\n"
        "2. Confirm site mineability >= 0.60 for at least 1 dig zone.\n"
        "3. Initiate plan execution via Run Mission Readiness Analysis.\n"
        "4. Monitor battery margin; intervene if margin trends below "
        f"{int(mission.safety_battery_margin_pct)}%.\n"
        "5. For any critical anomaly, transition fleet to SAFE_MODE and request "
        "Claude anomaly response before approval.\n"
        "6. Document approvals in the Approval Queue with operator notes.\n"
        "7. Generate final Mission Readiness Report and archive markdown."
    )

    return {
        "behavior_tree": behavior_tree,
        "ros_task_messages": ros_messages,
        "state_machine": state_machine,
        "operator_runbook": operator_runbook,
    }


def _expected_output_from_tasks(tasks: List[Dict[str, Any]]) -> float:
    process_total = sum(
        t.get("expected_output_kg", 0.0)
        for t in tasks
        if t["task_type"] == "process"
    )
    return round(process_total, 2)


def _confidence_pct(
    expected_output: float,
    target_output: float,
    scoring: Dict[str, Any],
) -> float:
    output_ratio = expected_output / target_output if target_output > 0 else 0.0
    output_factor = min(1.2, output_ratio)
    stats = scoring.get("mineability_statistics", {}) or {}
    avg_mineability = stats.get("avg_mineability_score", 0.4)
    confidence = 35.0 + 35.0 * output_factor + 30.0 * avg_mineability
    return round(max(40.0, min(95.0, confidence)), 1)


def generate_balanced_plan(
    db: Session,
    mission: Mission,
) -> Plan:
    """Generate the balanced mission plan and persist it."""
    site: LunarSite | None = get_site_for_mission(db, mission.id)
    if site is None:
        raise ValueError("Site must be generated before planning.")

    assets = get_assets(db, mission.id)
    if not assets:
        raise ValueError("Assets must be seeded before planning.")

    scoring = score_site(site, mission)
    dig_zones = _select_dig_zones(scoring)
    processor_cell = scoring["processor_placement"]
    power_cell = scoring["power_placement"]

    tasks = _build_tasks(mission, assets, dig_zones, processor_cell, power_cell)
    risks = _risk_register(mission, scoring)
    artifacts = _autonomy_artifacts(mission, assets, dig_zones, processor_cell)

    expected_output = _expected_output_from_tasks(tasks)
    confidence = _confidence_pct(expected_output, mission.target_amount_kg, scoring)

    summary_parts = [
        f"Balanced plan: 2 excavators alternating on top dig zones, "
        f"2 haulers cycling to processor at ({processor_cell.get('x')},{processor_cell.get('y')}), "
        f"processor maintained ~78% utilization, "
        f"{int(mission.safety_battery_margin_pct)}% battery margin preserved.",
        f"Expected water-ice output ~{expected_output:.1f} kg over {mission.duration_hours} h "
        f"(target {mission.target_amount_kg:.0f} kg).",
    ]
    summary = " ".join(summary_parts)

    plan = Plan(
        id=str(uuid.uuid4()),
        mission_id=mission.id,
        summary=summary,
        tasks_json=tasks,
        risk_register_json=risks,
        expected_output_kg=expected_output,
        confidence_pct=confidence,
        autonomy_artifacts_json=artifacts,
    )
    db.add(plan)
    db.flush()
    return plan


def serialize_plan(plan: Plan) -> Dict[str, Any]:
    return {
        "id": plan.id,
        "mission_id": plan.mission_id,
        "summary": plan.summary,
        "tasks": plan.tasks_json,
        "risk_register": plan.risk_register_json,
        "expected_output_kg": plan.expected_output_kg,
        "confidence_pct": plan.confidence_pct,
        "autonomy_artifacts": plan.autonomy_artifacts_json,
        "created_at": plan.created_at.isoformat(),
    }


def autonomy_artifacts_for_plan(plan: Plan) -> Dict[str, Any]:
    """Return autonomy artifacts (regenerating if missing)."""
    artifacts = plan.autonomy_artifacts_json or {}
    if not artifacts:
        return {}
    return artifacts


def autonomy_artifacts_for_mission(
    db: Session, mission: Mission, plan: Optional[Plan]
) -> Dict[str, Any]:
    site = get_site_for_mission(db, mission.id)
    assets = get_assets(db, mission.id)
    if site is None or not assets:
        return {
            "behavior_tree": "",
            "ros_task_messages": [],
            "state_machine": "",
            "operator_runbook": "",
        }
    scoring = score_site(site, mission)
    dig_zones = _select_dig_zones(scoring)
    processor_cell = scoring["processor_placement"]
    fresh = _autonomy_artifacts(mission, assets, dig_zones, processor_cell)
    if plan is not None:
        plan.autonomy_artifacts_json = fresh
        db.flush()
    return fresh

