"""Deterministic hourly simulation engine for Lunar MineOps AI OS."""
from __future__ import annotations

import math
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models import (
    Anomaly,
    Asset,
    LunarSite,
    Mission,
    Plan,
    SimulationRun,
)
from app.services.asset_service import get_assets
from app.services.site_service import (
    cell_average_illumination,
    get_site_for_mission,
    score_site,
)
from app.simulation.physics import (
    excavation_kg,
    haul_kg_delivered,
    processor_water_kg,
    solar_generation_kwh,
)


CELL_SIZE_M = 50.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tasks_by_asset_hour(
    plan: Plan,
) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """Index tasks for fast lookup: asset_id -> hour -> task."""
    index: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for task in plan.tasks_json or []:
        per = index.setdefault(task["asset_id"], {})
        for h in range(int(task["start_hour"]), int(task["end_hour"])):
            per[h] = task
    return index


def _cell_at(cells: List[Dict[str, Any]], x: int, y: int) -> Optional[Dict[str, Any]]:
    for c in cells:
        if c["x"] == x and c["y"] == y:
            return c
    return None


def _alert_level(battery_pct: float, health_pct: float) -> str:
    if battery_pct < 15 or health_pct < 70:
        return "critical"
    if battery_pct < 30 or health_pct < 80:
        return "warning"
    return "nominal"


# ---------------------------------------------------------------------------
# Anomaly generation (deterministic per seed)
# ---------------------------------------------------------------------------


ANOMALY_TYPES = (
    "wheel_slip",
    "dust_on_solar",
    "processor_overheat",
    "low_battery",
    "route_blocked",
    "comms_blackout",
    "excavator_jam",
    "hauler_fault",
)


def _severity_for(anom_type: str, health: float, battery: float) -> str:
    if anom_type == "low_battery":
        if battery < 8:
            return "critical"
        if battery < 18:
            return "high"
        return "medium"
    if anom_type == "processor_overheat" and health < 75:
        return "critical"
    if anom_type in ("hauler_fault", "excavator_jam") and health < 75:
        return "high"
    if anom_type == "route_blocked":
        return "high"
    if anom_type == "comms_blackout":
        return "medium"
    return "medium"


def _human_readable_action(anom_type: str) -> str:
    table = {
        "wheel_slip": "Reroute via lower-slope cell, reduce speed by 20%, queue inspection.",
        "dust_on_solar": "Trigger dust mitigation pass on solar array; hold processor at 60% input.",
        "processor_overheat": "Pause processor, vent heat for 1 hour, resume at 60% utilization.",
        "low_battery": "Transition asset to CHARGE state; redirect haul cycles to second asset.",
        "route_blocked": "Reroute via alternate corridor; notify operator and request approval.",
        "comms_blackout": "Queue local plan execution; resume telemetry on next comms window.",
        "excavator_jam": "Run jam-clear sequence; if unresolved, transition to SAFE_MODE for inspection.",
        "hauler_fault": "Drop payload at staging buffer; dispatch second hauler; schedule maintenance.",
    }
    return table.get(anom_type, "Investigate and request operator approval.")


def _root_cause(anom_type: str) -> str:
    table = {
        "wheel_slip": "Excessive slope or low-traction regolith encountered during traverse.",
        "dust_on_solar": "Cumulative dust deposition reduced solar array generation efficiency.",
        "processor_overheat": "Sustained high utilization without cooling reserve margin.",
        "low_battery": "Power demand exceeded generation+storage; charge cycle missed.",
        "route_blocked": "Hazard or unmapped obstacle detected on planned route.",
        "comms_blackout": "Asset entered comms shadow region with no relay coverage.",
        "excavator_jam": "Bucket bearing or cut-depth interference at high cut depth.",
        "hauler_fault": "Suspected motor or actuator fault under load.",
    }
    return table.get(anom_type, "Unknown root cause; investigate.")


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------


def run_simulation(
    db: Session,
    mission: Mission,
    plan: Plan,
    seed: int = 42,
) -> SimulationRun:
    """Run the deterministic simulation and persist results.

    Returns the SimulationRun (and inserts associated Anomaly rows).
    """
    site = get_site_for_mission(db, mission.id)
    if site is None:
        raise ValueError("Site missing; cannot simulate.")
    assets: List[Asset] = get_assets(db, mission.id)
    if not assets:
        raise ValueError("Assets missing; cannot simulate.")

    cells: List[Dict[str, Any]] = list(site.cells_json or [])
    scoring = score_site(site, mission)
    illum_factor = cell_average_illumination(site)
    tasks_idx = _tasks_by_asset_hour(plan)

    rng = random.Random(seed)

    # Per-asset state we mutate hourly
    state: Dict[str, Dict[str, Any]] = {}
    for a in assets:
        state[a.id] = {
            "battery_pct": (
                100.0
                if a.max_battery_kwh > 0
                else 100.0  # treat non-battery assets as always full
            ),
            "health_pct": float(a.health_pct),
            "payload_kg": 0.0,
            "location_x": int(a.location_x),
            "location_y": int(a.location_y),
            "status": "idle",
            "cumulative_output_kg": 0.0,
            "cumulative_regolith_moved_kg": 0.0,
            "downtime_hours": 0.0,
        }

    # Inventory available for processor (regolith waiting at processor cell)
    regolith_inventory_kg: float = 0.0

    # Site context
    processor_cell = scoring["processor_placement"]
    power_cell = scoring["power_placement"]
    dig_zone_cells = scoring["top_dig_zones"][:2] or [processor_cell]

    by_name = {a.name: a for a in assets}
    excavators = [a for a in assets if a.type == "excavator"]
    haulers = [a for a in assets if a.type == "hauler"]
    processor = by_name.get("Processor-1")
    solar = by_name.get("SolarArray-1")
    inspector = by_name.get("InspectionRover-1")

    # Power infrastructure state
    storage_kwh = float(solar.max_battery_kwh) if solar else 500.0
    max_storage_kwh = storage_kwh
    solar_gen_kw = float(solar.metadata_json.get("generation_kw", 35.0)) if solar else 35.0
    solar_uptime = float(solar.metadata_json.get("uptime_pct", 92.0)) if solar else 92.0

    telemetry: List[Dict[str, Any]] = []
    anomalies: List[Anomaly] = []

    total_output_kg = 0.0
    total_regolith_moved_kg = 0.0
    total_power_kw_sum = 0.0
    lowest_battery_margin = 100.0
    downtime_hours_total = 0.0

    # Charging behaviour: when an asset is below safety margin or scheduled to
    # charge, it gains battery. Otherwise it drains based on its hourly draw.

    safety_margin = float(mission.safety_battery_margin_pct)

    duration = int(mission.duration_hours)

    for hour in range(duration):
        hour_total_draw_kw = 0.0

        # Solar generation (kWh into storage)
        gen_kwh = solar_generation_kwh(
            generation_kw=solar_gen_kw,
            average_illumination_factor=illum_factor,
            uptime_pct=solar_uptime,
        )
        storage_kwh = min(max_storage_kwh, storage_kwh + gen_kwh)

        # ---- Excavation ----
        for ex in excavators:
            s = state[ex.id]
            task = tasks_idx.get(ex.id, {}).get(hour)
            ttype = task["task_type"] if task else "wait"
            zone = dig_zone_cells[0]
            if task and task.get("from_location"):
                z = _cell_at(cells, task["from_location"]["x"], task["from_location"]["y"])
                if z:
                    zone = z

            available_power_factor = 1.0
            if s["battery_pct"] < safety_margin:
                ttype = "charge" if ttype != "safe_mode" else "safe_mode"

            power_kw = 0.0

            if ttype == "excavate":
                rate = float(ex.metadata_json.get("excavation_rate_kg_per_hour", 80.0))
                kg = excavation_kg(
                    excavation_rate_kg_per_hour=rate,
                    resource_score=zone["resource_score"],
                    mineability_score=zone["mineability_score"],
                    slope_deg=zone["slope_deg"],
                    max_slope_deg=mission.max_slope_deg,
                    hazard_score=zone["hazard_score"],
                    health_pct=s["health_pct"],
                    available_power_factor=available_power_factor,
                )
                s["payload_kg"] = kg  # excavator stages payload locally
                s["status"] = "excavating"
                power_kw = ex.power_draw_kw
                # Pretend payload joins inventory continuously - haulers move it.
                s["location_x"], s["location_y"] = zone["x"], zone["y"]
            elif ttype == "charge":
                # Add ~12% per hour to battery, draws from storage
                charge_kw = max(2.0, ex.max_battery_kwh * 0.12)
                charge_amount = min(charge_kw, max(0.0, 100.0 - s["battery_pct"]))
                s["battery_pct"] = min(100.0, s["battery_pct"] + charge_amount)
                power_kw = charge_kw
                s["status"] = "charging"
                s["location_x"], s["location_y"] = power_cell["x"], power_cell["y"]
            elif ttype == "safe_mode":
                s["status"] = "safe_mode"
                power_kw = 1.0
                s["downtime_hours"] += 1.0
                downtime_hours_total += 1.0
            else:
                s["status"] = "idle"
                power_kw = 0.5

            # Battery drain when not charging
            if ttype not in ("charge",):
                drain_pct = (power_kw / max(1.0, ex.max_battery_kwh)) * 100.0
                s["battery_pct"] = max(0.0, s["battery_pct"] - drain_pct * 1.0)

            hour_total_draw_kw += power_kw

            telemetry.append(
                {
                    "hour": hour,
                    "asset_id": ex.id,
                    "asset_name": ex.name,
                    "status": s["status"],
                    "battery_pct": round(s["battery_pct"], 2),
                    "location_x": s["location_x"],
                    "location_y": s["location_y"],
                    "payload_kg": round(s["payload_kg"], 2),
                    "health_pct": round(s["health_pct"], 2),
                    "power_kw": round(power_kw, 2),
                    "cumulative_output_kg": round(total_output_kg, 2),
                    "cumulative_regolith_moved_kg": round(total_regolith_moved_kg, 2),
                    "alert_level": _alert_level(s["battery_pct"], s["health_pct"]),
                }
            )

            lowest_battery_margin = min(lowest_battery_margin, s["battery_pct"])

        # ---- Hauling ----
        for hl in haulers:
            s = state[hl.id]
            task = tasks_idx.get(hl.id, {}).get(hour)
            ttype = task["task_type"] if task else "wait"

            zone = dig_zone_cells[0]
            if task and task.get("from_location"):
                z = _cell_at(cells, task["from_location"]["x"], task["from_location"]["y"])
                if z:
                    zone = z

            if s["battery_pct"] < safety_margin:
                ttype = "charge"

            power_kw = 0.0
            delivered_kg = 0.0

            if ttype == "haul":
                # Pick up payload from excavators currently staging at zone
                pickup = 0.0
                for ex in excavators:
                    es = state[ex.id]
                    if es["payload_kg"] > 0 and es["location_x"] == zone["x"] and es["location_y"] == zone["y"]:
                        share = min(es["payload_kg"], hl.max_payload_kg - pickup)
                        es["payload_kg"] -= share
                        pickup += share
                        if pickup >= hl.max_payload_kg:
                            break
                # Cap payload by capacity
                s["payload_kg"] = min(hl.max_payload_kg, max(s["payload_kg"], pickup))

                distance_cells = math.hypot(
                    processor_cell["x"] - zone["x"],
                    processor_cell["y"] - zone["y"],
                )
                speed = float(hl.metadata_json.get("speed_m_per_hour", 250.0))
                delivered_kg = haul_kg_delivered(
                    payload_kg=s["payload_kg"],
                    distance_cells=distance_cells,
                    speed_m_per_hour=speed,
                    cell_size_m=CELL_SIZE_M,
                    health_pct=s["health_pct"],
                    route_hazard=zone["hazard_score"] * 0.6 + processor_cell["hazard_score"] * 0.4,
                )
                delivered_kg = min(delivered_kg, s["payload_kg"])
                s["payload_kg"] -= delivered_kg
                regolith_inventory_kg += delivered_kg
                total_regolith_moved_kg += delivered_kg
                s["cumulative_regolith_moved_kg"] += delivered_kg
                s["status"] = "hauling"
                power_kw = hl.power_draw_kw
                s["location_x"], s["location_y"] = processor_cell["x"], processor_cell["y"]
            elif ttype == "charge":
                charge_amount = min(15.0, max(0.0, 100.0 - s["battery_pct"]))
                s["battery_pct"] = min(100.0, s["battery_pct"] + charge_amount)
                power_kw = max(2.0, hl.max_battery_kwh * 0.12)
                s["status"] = "charging"
                s["location_x"], s["location_y"] = power_cell["x"], power_cell["y"]
            else:
                s["status"] = "idle"
                power_kw = 0.5

            if ttype not in ("charge",):
                drain_pct = (power_kw / max(1.0, hl.max_battery_kwh)) * 100.0
                s["battery_pct"] = max(0.0, s["battery_pct"] - drain_pct * 1.0)

            hour_total_draw_kw += power_kw

            telemetry.append(
                {
                    "hour": hour,
                    "asset_id": hl.id,
                    "asset_name": hl.name,
                    "status": s["status"],
                    "battery_pct": round(s["battery_pct"], 2),
                    "location_x": s["location_x"],
                    "location_y": s["location_y"],
                    "payload_kg": round(s["payload_kg"], 2),
                    "health_pct": round(s["health_pct"], 2),
                    "power_kw": round(power_kw, 2),
                    "cumulative_output_kg": round(total_output_kg, 2),
                    "cumulative_regolith_moved_kg": round(total_regolith_moved_kg, 2),
                    "alert_level": _alert_level(s["battery_pct"], s["health_pct"]),
                }
            )

            lowest_battery_margin = min(lowest_battery_margin, s["battery_pct"])

        # ---- Processing ----
        if processor:
            ps = state[processor.id]
            task = tasks_idx.get(processor.id, {}).get(hour)
            ttype = task["task_type"] if task else "wait"

            power_kw = 0.0
            if ttype == "process":
                rate = float(processor.metadata_json.get("input_rate_kg_per_hour", 120.0))
                eff = float(processor.metadata_json.get("extraction_efficiency_pct", 8.0))

                # Power factor based on storage availability
                power_factor = 1.0 if storage_kwh > processor.power_draw_kw else max(0.3, storage_kwh / max(1.0, processor.power_draw_kw))

                proc = processor_water_kg(
                    available_input_kg=regolith_inventory_kg,
                    input_rate_kg_per_hour=rate,
                    extraction_efficiency_pct=eff,
                    health_pct=ps["health_pct"],
                    available_power_factor=power_factor,
                )
                regolith_inventory_kg = max(0.0, regolith_inventory_kg - proc["consumed_input_kg"])
                total_output_kg += proc["output_kg"]
                ps["cumulative_output_kg"] = total_output_kg
                ps["status"] = "processing"
                power_kw = processor.power_draw_kw * power_factor
                ps["location_x"], ps["location_y"] = processor_cell["x"], processor_cell["y"]
            else:
                ps["status"] = "idle"
                power_kw = 1.0

            hour_total_draw_kw += power_kw
            telemetry.append(
                {
                    "hour": hour,
                    "asset_id": processor.id,
                    "asset_name": processor.name,
                    "status": ps["status"],
                    "battery_pct": 100.0,
                    "location_x": ps["location_x"],
                    "location_y": ps["location_y"],
                    "payload_kg": round(regolith_inventory_kg, 2),
                    "health_pct": round(ps["health_pct"], 2),
                    "power_kw": round(power_kw, 2),
                    "cumulative_output_kg": round(total_output_kg, 2),
                    "cumulative_regolith_moved_kg": round(total_regolith_moved_kg, 2),
                    "alert_level": _alert_level(100.0, ps["health_pct"]),
                }
            )

        # ---- Inspector ----
        if inspector:
            isr = state[inspector.id]
            task = tasks_idx.get(inspector.id, {}).get(hour)
            ttype = task["task_type"] if task else "wait"
            power_kw = 0.0
            if ttype == "inspect":
                isr["status"] = "inspecting"
                power_kw = inspector.power_draw_kw
                drain_pct = (power_kw / max(1.0, inspector.max_battery_kwh)) * 100.0
                isr["battery_pct"] = max(0.0, isr["battery_pct"] - drain_pct)
            else:
                isr["status"] = "idle"
                power_kw = 0.3
                isr["battery_pct"] = min(100.0, isr["battery_pct"] + 0.5)
            hour_total_draw_kw += power_kw

            telemetry.append(
                {
                    "hour": hour,
                    "asset_id": inspector.id,
                    "asset_name": inspector.name,
                    "status": isr["status"],
                    "battery_pct": round(isr["battery_pct"], 2),
                    "location_x": isr["location_x"],
                    "location_y": isr["location_y"],
                    "payload_kg": 0.0,
                    "health_pct": round(isr["health_pct"], 2),
                    "power_kw": round(power_kw, 2),
                    "cumulative_output_kg": round(total_output_kg, 2),
                    "cumulative_regolith_moved_kg": round(total_regolith_moved_kg, 2),
                    "alert_level": _alert_level(isr["battery_pct"], isr["health_pct"]),
                }
            )

            lowest_battery_margin = min(lowest_battery_margin, isr["battery_pct"])

        # ---- Solar telemetry ----
        if solar:
            ss = state[solar.id]
            telemetry.append(
                {
                    "hour": hour,
                    "asset_id": solar.id,
                    "asset_name": solar.name,
                    "status": "generating",
                    "battery_pct": round(100.0 * storage_kwh / max(1.0, max_storage_kwh), 2),
                    "location_x": power_cell["x"],
                    "location_y": power_cell["y"],
                    "payload_kg": 0.0,
                    "health_pct": round(ss["health_pct"], 2),
                    "power_kw": round(gen_kwh, 2),
                    "cumulative_output_kg": round(total_output_kg, 2),
                    "cumulative_regolith_moved_kg": round(total_regolith_moved_kg, 2),
                    "alert_level": "nominal",
                }
            )

        # Storage drain by net consumption (best-effort, not strict balance)
        consumed_kwh = max(0.0, hour_total_draw_kw - gen_kwh)
        storage_kwh = max(0.0, storage_kwh - consumed_kwh * 0.4)

        total_power_kw_sum += hour_total_draw_kw

        # ---- Anomaly probability per hour ----
        anomalies.extend(_maybe_anomaly(hour, rng, state, assets, scoring))

    # ---- Final aggregates ----
    average_power_kw = total_power_kw_sum / max(1, duration)
    anomaly_count = len(anomalies)
    critical_count = sum(1 for a in anomalies if a.severity == "critical")
    output_shortfall_pct = max(
        0.0, (mission.target_amount_kg - total_output_kg) / mission.target_amount_kg * 100.0
    )
    downtime_pct = downtime_hours_total / max(1, duration) * 100.0

    margin_violation = 0
    if lowest_battery_margin < safety_margin:
        margin_violation = 1

    success = 95.0
    success -= anomaly_count * 3.0
    success -= critical_count * 8.0
    success -= margin_violation * 15.0
    success -= output_shortfall_pct * 0.5
    success -= downtime_pct * 0.4
    success_pct = max(0.0, min(99.0, success))

    sim_run = SimulationRun(
        id=str(uuid.uuid4()),
        mission_id=mission.id,
        plan_id=plan.id,
        seed=seed,
        status="completed",
        total_output_kg=round(total_output_kg, 2),
        total_regolith_moved_kg=round(total_regolith_moved_kg, 2),
        average_power_kw=round(average_power_kw, 2),
        lowest_battery_margin_pct=round(lowest_battery_margin, 2),
        downtime_hours=round(downtime_hours_total, 2),
        anomaly_count=anomaly_count,
        success_probability_pct=round(success_pct, 2),
        telemetry_json=telemetry,
        readiness_json={},
    )
    db.add(sim_run)
    db.flush()

    for anomaly in anomalies:
        anomaly.simulation_run_id = sim_run.id
        db.add(anomaly)

    db.flush()

    return sim_run


# ---------------------------------------------------------------------------
# Anomaly inner loop
# ---------------------------------------------------------------------------


def _maybe_anomaly(
    hour: int,
    rng: random.Random,
    state: Dict[str, Dict[str, Any]],
    assets: List[Asset],
    scoring: Dict[str, Any],
) -> List[Anomaly]:
    """Generate up to one anomaly per hour, deterministic per seed."""
    out: List[Anomaly] = []

    # Probability scaffolding
    avg_haz = scoring.get("mineability_statistics", {}).get("avg_hazard_score", 0.2)
    avg_slope = scoring.get("mineability_statistics", {}).get("avg_slope_deg", 5.0)

    base_rate = 0.045 + 0.05 * float(avg_haz) + 0.005 * float(avg_slope)
    if rng.random() > base_rate:
        return out

    asset = rng.choice(assets) if assets else None
    if asset is None:
        return out
    s = state[asset.id]

    # Filter anomaly types to those relevant for the asset
    pool = list(ANOMALY_TYPES)
    if asset.type == "excavator":
        pool = ["wheel_slip", "excavator_jam", "low_battery", "comms_blackout"]
    elif asset.type == "hauler":
        pool = ["wheel_slip", "hauler_fault", "route_blocked", "low_battery", "comms_blackout"]
    elif asset.type == "processor":
        pool = ["processor_overheat", "comms_blackout"]
    elif asset.type == "power_unit":
        pool = ["dust_on_solar"]
    elif asset.type == "inspection_rover":
        pool = ["wheel_slip", "low_battery", "comms_blackout"]

    anom_type = rng.choice(pool)

    # Bias certain types when state is degraded
    if s["battery_pct"] < 25 and rng.random() < 0.6:
        anom_type = "low_battery"
    elif asset.type == "power_unit":
        anom_type = "dust_on_solar"

    severity = _severity_for(anom_type, s["health_pct"], s["battery_pct"])
    requires_approval = severity == "critical"
    impact = round(rng.uniform(0.5, 6.5) * (1.0 if severity != "critical" else 2.5), 2)

    anomaly = Anomaly(
        id=str(uuid.uuid4()),
        simulation_run_id="",  # filled by caller after sim_run is added
        hour=hour,
        asset_id=asset.id,
        type=anom_type,
        severity=severity,
        description=f"{anom_type.replace('_', ' ').title()} detected on {asset.name} at hour {hour}.",
        root_cause_hypothesis=_root_cause(anom_type),
        recommended_action=_human_readable_action(anom_type),
        production_impact_kg=impact,
        requires_human_approval=bool(requires_approval),
    )
    out.append(anomaly)

    # Reduce health slightly when anomaly fires
    if severity in ("high", "critical"):
        s["health_pct"] = max(40.0, s["health_pct"] - 1.5)
    return out


# ---------------------------------------------------------------------------
# Public helpers used by tools
# ---------------------------------------------------------------------------


def telemetry_summary(sim: SimulationRun) -> Dict[str, Any]:
    telemetry: List[Dict[str, Any]] = sim.telemetry_json or []
    return {
        "telemetry_points": len(telemetry),
        "duration_hours": max((t["hour"] for t in telemetry), default=0) + 1
        if telemetry
        else 0,
        "total_output_kg": sim.total_output_kg,
        "total_regolith_moved_kg": sim.total_regolith_moved_kg,
        "average_power_kw": sim.average_power_kw,
        "lowest_battery_margin_pct": sim.lowest_battery_margin_pct,
        "downtime_hours": sim.downtime_hours,
        "anomaly_count": sim.anomaly_count,
        "success_probability_pct": sim.success_probability_pct,
    }


def production_curve(sim: SimulationRun) -> List[Dict[str, Any]]:
    telemetry = sim.telemetry_json or []
    by_hour: Dict[int, float] = {}
    for t in telemetry:
        by_hour[t["hour"]] = max(by_hour.get(t["hour"], 0.0), t["cumulative_output_kg"])
    return [{"hour": h, "cumulative_output_kg": v} for h, v in sorted(by_hour.items())]


def battery_curve(sim: SimulationRun) -> List[Dict[str, Any]]:
    telemetry = sim.telemetry_json or []
    by_hour: Dict[int, List[float]] = {}
    for t in telemetry:
        if t["asset_name"] in ("Processor-1", "SolarArray-1"):
            continue
        by_hour.setdefault(t["hour"], []).append(t["battery_pct"])
    return [
        {
            "hour": h,
            "min_battery_pct": round(min(vs), 2) if vs else 0.0,
            "avg_battery_pct": round(sum(vs) / len(vs), 2) if vs else 0.0,
        }
        for h, vs in sorted(by_hour.items())
    ]


def power_curve(sim: SimulationRun) -> List[Dict[str, Any]]:
    telemetry = sim.telemetry_json or []
    by_hour: Dict[int, float] = {}
    for t in telemetry:
        by_hour[t["hour"]] = by_hour.get(t["hour"], 0.0) + t["power_kw"]
    return [{"hour": h, "total_power_kw": round(v, 2)} for h, v in sorted(by_hour.items())]
