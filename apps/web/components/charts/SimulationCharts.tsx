"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";

interface CurvePoint {
  hour: number;
  cumulative_output_kg?: number;
  min_battery_pct?: number;
  avg_battery_pct?: number;
  total_power_kw?: number;
}

export function ProductionChart({
  data,
  target,
}: {
  data: CurvePoint[];
  target: number;
}) {
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="#e5e5e2" />
          <XAxis dataKey="hour" tick={{ fontSize: 10 }} stroke="#6b6b6b" />
          <YAxis tick={{ fontSize: 10 }} stroke="#6b6b6b" />
          <Tooltip wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine
            y={target}
            stroke="#a06a00"
            strokeDasharray="3 3"
            label={{ value: "target", fontSize: 10, fill: "#a06a00" }}
          />
          <Line
            type="monotone"
            dataKey="cumulative_output_kg"
            stroke="#5b5bd6"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            name="Output (kg)"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BatteryChart({
  data,
  safetyMargin,
}: {
  data: CurvePoint[];
  safetyMargin: number;
}) {
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="#e5e5e2" />
          <XAxis dataKey="hour" tick={{ fontSize: 10 }} stroke="#6b6b6b" />
          <YAxis tick={{ fontSize: 10 }} stroke="#6b6b6b" domain={[0, 100]} />
          <Tooltip wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine
            y={safetyMargin}
            stroke="#a32020"
            strokeDasharray="3 3"
            label={{
              value: `safety ${safetyMargin}%`,
              fontSize: 10,
              fill: "#a32020",
            }}
          />
          <Line
            type="monotone"
            dataKey="min_battery_pct"
            stroke="#a32020"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            name="Min battery %"
          />
          <Line
            type="monotone"
            dataKey="avg_battery_pct"
            stroke="#1f7a4d"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
            name="Avg battery %"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PowerChart({ data }: { data: CurvePoint[] }) {
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="2 2" stroke="#e5e5e2" />
          <XAxis dataKey="hour" tick={{ fontSize: 10 }} stroke="#6b6b6b" />
          <YAxis tick={{ fontSize: 10 }} stroke="#6b6b6b" />
          <Tooltip wrapperStyle={{ fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="total_power_kw"
            stroke="#0b0c0d"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            name="Total power (kW)"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
