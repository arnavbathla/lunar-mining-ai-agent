"""Mission readiness scoring."""
from __future__ import annotations

from typing import Any, Dict, List

from app.db.models import Mission, SimulationRun


def _site_mineability_dim(scoring: Dict[str, Any]) -> Dict[str, str]:
    zones = scoring.get("top_dig_zones", []) or []
    high = sum(1 for z in zones if z["mineability_score"] >= 0.70)
    medium = sum(1 for z in zones if z["mineability_score"] >= 0.60)
    if high >= 2:
        return {
            "status": "pass",
            "explanation": (
                f"{high} dig zones meet the 0.70 mineability threshold; "
                "site is suitable for sustained excavation."
            ),
        }
    if medium >= 1:
        return {
            "status": "caution",
            "explanation": (
                f"Only {medium} dig zone(s) meet the 0.60 mineability threshold; "
                "expect lower yields and tighter routing."
            ),
        }
    return {
        "status": "fail",
        "explanation": (
            "No dig zone meets the 0.60 mineability threshold; "
            "site mineability is insufficient for the target."
        ),
    }


def _production_dim(
    sim: SimulationRun, mission: Mission
) -> Dict[str, str]:
    target = float(mission.target_amount_kg)
    output = float(sim.total_output_kg)
    if output >= target:
        return {
            "status": "pass",
            "explanation": (
                f"Simulated output {output:.1f} kg meets target {target:.0f} kg."
            ),
        }
    if output >= 0.80 * target:
        return {
            "status": "caution",
            "explanation": (
                f"Simulated output {output:.1f} kg falls below target ({target:.0f} kg) "
                "but exceeds 80% threshold."
            ),
        }
    return {
        "status": "fail",
        "explanation": (
            f"Simulated output {output:.1f} kg falls below 80% of target "
            f"({0.8 * target:.1f} kg)."
        ),
    }


def _power_dim(
    sim: SimulationRun, mission: Mission
) -> Dict[str, str]:
    margin = float(sim.lowest_battery_margin_pct)
    safe = float(mission.safety_battery_margin_pct)
    if margin >= safe:
        return {
            "status": "pass",
            "explanation": (
                f"Lowest battery margin {margin:.1f}% holds above the {safe:.0f}% safety floor."
            ),
        }
    if margin >= safe - 5.0:
        return {
            "status": "caution",
            "explanation": (
                f"Lowest battery margin {margin:.1f}% is within 5 points of the "
                f"{safe:.0f}% safety floor; recommend increased charge cadence."
            ),
        }
    return {
        "status": "fail",
        "explanation": (
            f"Lowest battery margin {margin:.1f}% breached the {safe:.0f}% safety floor."
        ),
    }


def _autonomy_dim(
    sim: SimulationRun, anomalies: List[Dict[str, Any]] | None = None
) -> Dict[str, str]:
    crit = 0
    if anomalies:
        crit = sum(1 for a in anomalies if a.get("severity") == "critical")
    if sim.anomaly_count <= 3 and crit == 0:
        return {
            "status": "pass",
            "explanation": (
                f"{sim.anomaly_count} anomalies, no critical events. Autonomy risk acceptable."
            ),
        }
    if crit <= 1 and sim.anomaly_count <= 6:
        return {
            "status": "caution",
            "explanation": (
                f"{sim.anomaly_count} anomalies (crit={crit}); operator review of approvals required."
            ),
        }
    return {
        "status": "fail",
        "explanation": (
            f"{sim.anomaly_count} anomalies (crit={crit}); autonomy risk exceeds mission tolerance."
        ),
    }


def _mission_dim(
    site: Dict[str, str],
    prod: Dict[str, str],
    power: Dict[str, str],
    autonomy: Dict[str, str],
) -> Dict[str, str]:
    statuses = [site["status"], prod["status"], power["status"], autonomy["status"]]
    if all(s == "pass" for s in statuses):
        return {
            "status": "go",
            "explanation": "All four readiness dimensions pass.",
        }
    if any(s == "fail" for s in statuses):
        fails = [n for n, s in zip(("site", "production", "power", "autonomy"), statuses) if s == "fail"]
        return {
            "status": "no_go",
            "explanation": (
                f"Readiness fails on: {', '.join(fails)}. "
                "Resolve failures before proceeding."
            ),
        }
    cautions = [n for n, s in zip(("site", "production", "power", "autonomy"), statuses) if s == "caution"]
    return {
        "status": "conditional_go",
        "explanation": (
            f"Conditional go: caution on {', '.join(cautions)}. "
            "Mitigations required before launch."
        ),
    }


def score_readiness(
    *,
    mission: Mission,
    sim: SimulationRun,
    site_scoring: Dict[str, Any],
    anomalies_serialized: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    site_dim = _site_mineability_dim(site_scoring)
    prod_dim = _production_dim(sim, mission)
    power_dim = _power_dim(sim, mission)
    auton_dim = _autonomy_dim(sim, anomalies_serialized or [])
    mission_dim = _mission_dim(site_dim, prod_dim, power_dim, auton_dim)
    return {
        "site_mineability": site_dim,
        "production_target": prod_dim,
        "power_budget": power_dim,
        "autonomy_risk": auton_dim,
        "mission_readiness": mission_dim,
    }
