"use client";

import { useMemo, useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import type { Asset, Cell, LunarSite, Mission } from "@/lib/types";

type Layer =
  | "mineability"
  | "resource"
  | "hazard"
  | "illumination"
  | "slope"
  | "comms";

interface Props {
  site: LunarSite;
  mission: Mission;
  assets: Asset[];
  scoring?: {
    top_dig_zones?: Array<{ x: number; y: number; mineability_score?: number }>;
    processor_placement?: { x?: number; y?: number };
    power_placement?: { x?: number; y?: number };
  };
}

export function LunarMap({ site, mission, assets, scoring }: Props) {
  const [layer, setLayer] = useState<Layer>("mineability");
  const [selected, setSelected] = useState<Cell | null>(null);

  const cells = site.cells_json;
  const w = site.grid_width;
  const h = site.grid_height;

  const placements = useMemo(() => {
    const dig = (scoring?.top_dig_zones ?? []).slice(0, 2);
    const processor = scoring?.processor_placement;
    const power = scoring?.power_placement;
    return { dig, processor, power };
  }, [scoring]);

  const cellSize = 22;

  const getColor = (c: Cell): string => {
    let value = 0;
    switch (layer) {
      case "mineability":
        value = c.mineability_score;
        return shade("#5b5bd6", value);
      case "resource":
        value = c.resource_score;
        return shade("#3aa3ff", value);
      case "hazard":
        value = c.hazard_score;
        return shade("#a32020", value);
      case "illumination":
        value = c.illumination_pct / 100;
        return shade("#f4c542", value);
      case "slope":
        value = Math.min(1, c.slope_deg / 25);
        return shade("#a06a00", value);
      case "comms":
        value = c.comms_quality;
        return shade("#1f7a4d", value);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Lunar Site Evidence"
        subtitle={`${w}×${h} synthetic polar grid · seed-deterministic · max slope ${mission.max_slope_deg}°`}
        right={
          <div className="flex flex-wrap gap-1.5">
            {(
              [
                "mineability",
                "resource",
                "hazard",
                "illumination",
                "slope",
                "comms",
              ] as Layer[]
            ).map((l) => (
              <button
                key={l}
                onClick={() => setLayer(l)}
                className={`px-2 py-1 rounded-md text-[11px] uppercase tracking-wider border transition-colors ${
                  layer === l
                    ? "bg-ink text-paper border-ink"
                    : "bg-paper text-ink border-line hover:border-ink"
                }`}
              >
                {l}
              </button>
            ))}
          </div>
        }
      />
      <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-6 items-start">
        <div className="overflow-auto">
          <svg
            width={w * cellSize}
            height={h * cellSize}
            className="block border border-line"
          >
            {cells.map((c) => {
              const isSelected =
                selected && selected.x === c.x && selected.y === c.y;
              return (
                <rect
                  key={`${c.x}-${c.y}`}
                  x={c.x * cellSize}
                  y={c.y * cellSize}
                  width={cellSize}
                  height={cellSize}
                  fill={getColor(c)}
                  stroke={isSelected ? "#0b0c0d" : "rgba(0,0,0,0.04)"}
                  strokeWidth={isSelected ? 2 : 0.5}
                  onClick={() => setSelected(c)}
                  style={{ cursor: "pointer" }}
                />
              );
            })}

            {/* Hazard outlines for cells exceeding max slope */}
            {cells
              .filter((c) => c.slope_deg > mission.max_slope_deg)
              .map((c) => (
                <rect
                  key={`slope-${c.x}-${c.y}`}
                  x={c.x * cellSize + 1}
                  y={c.y * cellSize + 1}
                  width={cellSize - 2}
                  height={cellSize - 2}
                  fill="none"
                  stroke="rgba(163,32,32,0.45)"
                  strokeWidth={0.8}
                  strokeDasharray="2 2"
                  pointerEvents="none"
                />
              ))}

            {/* Dig zones */}
            {placements.dig.map((d, i) => (
              <g key={`dig-${i}`} pointerEvents="none">
                <circle
                  cx={d.x * cellSize + cellSize / 2}
                  cy={d.y * cellSize + cellSize / 2}
                  r={cellSize / 2}
                  fill="none"
                  stroke="#0b0c0d"
                  strokeWidth={2}
                />
                <text
                  x={d.x * cellSize + cellSize / 2}
                  y={d.y * cellSize + cellSize / 2 + 3}
                  fontSize={9}
                  textAnchor="middle"
                  fill="#0b0c0d"
                  fontWeight={700}
                >
                  D{i + 1}
                </text>
              </g>
            ))}

            {/* Processor placement */}
            {placements.processor?.x !== undefined &&
            placements.processor?.y !== undefined ? (
              <g pointerEvents="none">
                <rect
                  x={(placements.processor.x as number) * cellSize}
                  y={(placements.processor.y as number) * cellSize}
                  width={cellSize}
                  height={cellSize}
                  fill="none"
                  stroke="#5b5bd6"
                  strokeWidth={2.5}
                />
                <text
                  x={(placements.processor.x as number) * cellSize + cellSize / 2}
                  y={(placements.processor.y as number) * cellSize + cellSize / 2 + 3}
                  fontSize={9}
                  textAnchor="middle"
                  fill="#5b5bd6"
                  fontWeight={700}
                >
                  P
                </text>
              </g>
            ) : null}

            {/* Power placement */}
            {placements.power?.x !== undefined &&
            placements.power?.y !== undefined ? (
              <g pointerEvents="none">
                <rect
                  x={(placements.power.x as number) * cellSize}
                  y={(placements.power.y as number) * cellSize}
                  width={cellSize}
                  height={cellSize}
                  fill="none"
                  stroke="#a06a00"
                  strokeWidth={2.5}
                />
                <text
                  x={(placements.power.x as number) * cellSize + cellSize / 2}
                  y={(placements.power.y as number) * cellSize + cellSize / 2 + 3}
                  fontSize={9}
                  textAnchor="middle"
                  fill="#a06a00"
                  fontWeight={700}
                >
                  S
                </text>
              </g>
            ) : null}

            {/* Asset markers */}
            {assets.map((a) => (
              <g key={a.id} pointerEvents="none">
                <circle
                  cx={a.location_x * cellSize + cellSize / 2}
                  cy={a.location_y * cellSize + cellSize / 2}
                  r={3.5}
                  fill="#0b0c0d"
                  stroke="#fff"
                  strokeWidth={1}
                />
              </g>
            ))}
          </svg>
        </div>
        <div className="grid gap-3">
          <Legend layer={layer} />
          <Card padded className="bg-bone border-line">
            {selected ? (
              <CellPanel cell={selected} mission={mission} />
            ) : (
              <p className="text-[12px] text-muted">
                Click any cell to inspect mineability, resource, hazard, slope,
                comms quality, illumination, and recommendation.
              </p>
            )}
          </Card>
        </div>
      </div>
    </Card>
  );
}

function shade(hex: string, intensity: number) {
  // intensity in [0..1]
  const v = Math.max(0, Math.min(1, intensity));
  const alpha = 0.05 + v * 0.85;
  return hexToRgba(hex, alpha);
}

function hexToRgba(hex: string, alpha: number) {
  const h = hex.replace("#", "");
  const bigint = parseInt(h, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

function Legend({ layer }: { layer: Layer }) {
  const stops = ["0%", "25%", "50%", "75%", "100%"];
  const labels: Record<Layer, [string, string]> = {
    mineability: ["Low", "High"],
    resource: ["Low", "High"],
    hazard: ["Safe", "Hazard"],
    illumination: ["Shadow", "Sunlit"],
    slope: ["Flat", "Steep"],
    comms: ["Shadow", "Strong"],
  };
  return (
    <div className="rounded-md border border-line p-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">
        {layer} legend
      </div>
      <div className="flex items-center gap-2 mt-2">
        <span className="text-[11px] text-muted w-12">{labels[layer][0]}</span>
        <div className="flex h-3 flex-1 rounded overflow-hidden border border-line">
          {stops.map((s, i) => (
            <div
              key={i}
              className="flex-1"
              style={{
                background: legendColor(layer, i / (stops.length - 1)),
              }}
            />
          ))}
        </div>
        <span className="text-[11px] text-muted w-10 text-right">
          {labels[layer][1]}
        </span>
      </div>
      <div className="flex flex-wrap gap-2 mt-3 text-[11px] text-muted">
        <Badge label="D1/D2 dig zones" color="#0b0c0d" />
        <Badge label="P processor" color="#5b5bd6" />
        <Badge label="S solar/power" color="#a06a00" />
        <Badge label="● assets" color="#0b0c0d" filled />
      </div>
    </div>
  );
}

function Badge({
  label,
  color,
  filled,
}: {
  label: string;
  color: string;
  filled?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full border"
        style={{
          background: filled ? color : "transparent",
          borderColor: color,
        }}
      />
      {label}
    </span>
  );
}

function legendColor(layer: Layer, t: number) {
  const map: Record<Layer, string> = {
    mineability: "#5b5bd6",
    resource: "#3aa3ff",
    hazard: "#a32020",
    illumination: "#f4c542",
    slope: "#a06a00",
    comms: "#1f7a4d",
  };
  return shade(map[layer], t);
}

function CellPanel({ cell, mission }: { cell: Cell; mission: Mission }) {
  const overSlope = cell.slope_deg > mission.max_slope_deg;
  const lowComms = cell.comms_quality < 0.25;
  const highHazard = cell.hazard_score > 0.65;

  const recommendation = overSlope
    ? "Avoid traverse - slope exceeds mission constraint."
    : highHazard
      ? "Treat as hazard zone - reroute around if possible."
      : lowComms
        ? "Comms-shadow risk - queue messages or use relay."
        : cell.mineability_score >= 0.6
          ? "Strong dig candidate."
          : "Marginal cell - prefer top dig zones.";

  return (
    <div>
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-[0.14em] text-muted">
          Cell ({cell.x}, {cell.y})
        </div>
        <StatusPill
          label={`Mineability ${cell.mineability_score.toFixed(2)}`}
          tone={
            cell.mineability_score >= 0.7
              ? "pass"
              : cell.mineability_score >= 0.5
                ? "caution"
                : "fail"
          }
        />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
        <Field label="Resource" value={cell.resource_score.toFixed(2)} />
        <Field label="Hazard" value={cell.hazard_score.toFixed(2)} />
        <Field label="Slope" value={`${cell.slope_deg.toFixed(1)} °`} />
        <Field label="Illumination" value={`${cell.illumination_pct.toFixed(0)} %`} />
        <Field label="Comms" value={cell.comms_quality.toFixed(2)} />
        <Field label="Elevation" value={`${cell.elevation_m.toFixed(0)} m`} />
        <Field label="Temp" value={`${cell.temperature_c.toFixed(0)} °C`} />
      </dl>
      <p className="text-[12px] text-ink mt-3">
        <span className="text-muted mr-2">Recommendation:</span>
        {recommendation}
      </p>
    </div>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="text-ink text-right tabular-nums">{value}</dd>
    </>
  );
}
