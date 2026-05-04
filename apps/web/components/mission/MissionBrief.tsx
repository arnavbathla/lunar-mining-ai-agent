"use client";

import { Mission, AgentStatus, SourcesContext } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import { Button } from "@/components/ui/Button";
import { formatRelativeTime } from "@/lib/utils";

interface Props {
  mission: Mission;
  agentStatus: AgentStatus | null;
  sourcesContext: SourcesContext | null;
  loading: boolean;
  loadingMessage?: string | null;
  error?: string | null;
  onRun: () => void;
}

export function MissionBrief({
  mission,
  agentStatus,
  sourcesContext,
  loading,
  loadingMessage,
  error,
  onRun,
}: Props) {
  const fetched = sourcesContext?.last_refreshed_at;
  const usedFallback = sourcesContext?.used_fallback ?? false;

  return (
    <Card>
      <div className="flex items-start justify-between gap-6 flex-wrap">
        <div className="max-w-2xl">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <StatusPill label="Mission Brief" tone="info" />
            <StatusPill
              label={
                agentStatus?.anthropic_configured
                  ? `Anthropic ${agentStatus.model}`
                  : "Anthropic Missing"
              }
              tone={agentStatus?.anthropic_configured ? "pass" : "caution"}
            />
            <StatusPill
              label={
                fetched
                  ? `Sources ${formatRelativeTime(fetched)}${
                      usedFallback ? " · Fallback" : ""
                    }`
                  : "Sources Pending"
              }
              tone={
                fetched
                  ? usedFallback
                    ? "caution"
                    : "pass"
                  : "neutral"
              }
            />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            {mission.name}
          </h1>
          <p className="text-[13px] text-muted mt-2 leading-relaxed">
            {mission.objective}
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <Button
            variant="primary"
            size="md"
            loading={loading}
            onClick={onRun}
          >
            Run Mission Readiness Analysis
          </Button>
          {loading && loadingMessage ? (
            <span className="text-[12px] text-muted text-right max-w-xs">
              {loadingMessage}
            </span>
          ) : null}
          {error ? (
            <span className="text-[12px] text-status-fail max-w-xs text-right">
              {error}
            </span>
          ) : null}
        </div>
      </div>
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-6 gap-y-3 border-t border-line pt-4">
        <Spec label="Duration" value={`${mission.duration_hours} h`} />
        <Spec label="Target resource" value={mission.target_resource} />
        <Spec label="Target amount" value={`${mission.target_amount_kg} kg`} />
        <Spec
          label="Battery margin"
          value={`${mission.safety_battery_margin_pct.toFixed(0)} %`}
        />
        <Spec
          label="Max slope"
          value={`${mission.max_slope_deg.toFixed(1)} °`}
        />
        <Spec
          label="Mission ID"
          value={
            <code className="font-mono text-[11px] truncate block max-w-[140px]">
              {mission.id}
            </code>
          }
        />
      </div>
    </Card>
  );
}

function Spec({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">
        {label}
      </div>
      <div className="text-[13px] font-medium text-ink mt-0.5">{value}</div>
    </div>
  );
}
