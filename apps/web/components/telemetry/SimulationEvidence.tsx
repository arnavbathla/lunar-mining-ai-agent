"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { MetricStat } from "@/components/ui/MetricStat";
import { StatusPill } from "@/components/ui/StatusPill";
import { api } from "@/lib/api";
import type { Mission, SimulationRun } from "@/lib/types";
import {
  BatteryChart,
  PowerChart,
  ProductionChart,
} from "@/components/charts/SimulationCharts";
import { formatHours, formatKg, formatKw, formatPct } from "@/lib/utils";

interface Props {
  mission: Mission;
  simulation: SimulationRun | null;
}

export function SimulationEvidence({ mission, simulation }: Props) {
  const [curves, setCurves] = useState<{
    production_curve: any[];
    battery_curve: any[];
    power_curve: any[];
  } | null>(null);

  useEffect(() => {
    if (!simulation) return;
    api
      .simulationTelemetry(simulation.id)
      .then((c) =>
        setCurves({
          production_curve: c.production_curve,
          battery_curve: c.battery_curve,
          power_curve: c.power_curve,
        }),
      )
      .catch(() => setCurves(null));
  }, [simulation?.id]);

  if (!simulation) {
    return (
      <Card>
        <CardHeader title="Simulation Evidence" />
        <p className="text-[13px] text-muted">
          Simulation results appear after Run Mission Readiness Analysis.
        </p>
      </Card>
    );
  }

  const outputTone =
    simulation.total_output_kg >= mission.target_amount_kg
      ? "pass"
      : simulation.total_output_kg >= 0.8 * mission.target_amount_kg
        ? "caution"
        : "fail";

  const batteryTone =
    simulation.lowest_battery_margin_pct >= mission.safety_battery_margin_pct
      ? "pass"
      : simulation.lowest_battery_margin_pct >=
          mission.safety_battery_margin_pct - 5
        ? "caution"
        : "fail";

  return (
    <Card>
      <CardHeader
        title="Simulation Evidence"
        subtitle={`Seed ${simulation.seed} · ${mission.duration_hours} h hourly determinism`}
        right={
          <StatusPill
            label={`Success ${formatPct(simulation.success_probability_pct)}`}
            tone={
              simulation.success_probability_pct >= 70
                ? "pass"
                : simulation.success_probability_pct >= 50
                  ? "caution"
                  : "fail"
            }
          />
        }
      />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-4 border-b border-line pb-5">
        <MetricStat
          label="Target output"
          value={formatKg(mission.target_amount_kg, 0)}
        />
        <MetricStat
          label="Simulated output"
          tone={outputTone as any}
          value={formatKg(simulation.total_output_kg)}
        />
        <MetricStat
          label="Regolith moved"
          value={formatKg(simulation.total_regolith_moved_kg)}
        />
        <MetricStat
          label="Avg power"
          value={formatKw(simulation.average_power_kw)}
        />
        <MetricStat
          label="Lowest battery margin"
          tone={batteryTone as any}
          value={formatPct(simulation.lowest_battery_margin_pct)}
        />
        <MetricStat label="Downtime" value={formatHours(simulation.downtime_hours)} />
        <MetricStat label="Anomalies" value={simulation.anomaly_count} />
        <MetricStat
          label="Success probability"
          value={formatPct(simulation.success_probability_pct)}
        />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted mb-2">
            Production over time
          </div>
          {curves ? (
            <ProductionChart
              data={curves.production_curve}
              target={mission.target_amount_kg}
            />
          ) : (
            <div className="h-44 grid place-items-center text-[12px] text-muted">
              Loading…
            </div>
          )}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted mb-2">
            Battery margin over time
          </div>
          {curves ? (
            <BatteryChart
              data={curves.battery_curve}
              safetyMargin={mission.safety_battery_margin_pct}
            />
          ) : (
            <div className="h-44 grid place-items-center text-[12px] text-muted">
              Loading…
            </div>
          )}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted mb-2">
            Power over time
          </div>
          {curves ? (
            <PowerChart data={curves.power_curve} />
          ) : (
            <div className="h-44 grid place-items-center text-[12px] text-muted">
              Loading…
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
