"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type {
  AgentReadinessResult,
  AgentStatus,
  Anomaly,
  Asset,
  LunarSite,
  Mission,
  Plan,
  ReadinessJSON,
  SimulationRun,
  SourcesContext,
} from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { Section } from "@/components/ui/Section";
import { StatusPill } from "@/components/ui/StatusPill";
import { Button } from "@/components/ui/Button";
import { MissionBrief } from "@/components/mission/MissionBrief";
import { ReadinessCards } from "@/components/readiness/ReadinessCards";
import { ExecutiveRecommendation } from "@/components/readiness/ExecutiveRecommendation";
import { SourcesPanel } from "@/components/sources/SourcesPanel";
import { LunarMap } from "@/components/map/LunarMap";
import { PlanPanel } from "@/components/mission/PlanPanel";
import { SimulationEvidence } from "@/components/telemetry/SimulationEvidence";
import { AnomalyControl } from "@/components/agent/AnomalyControl";
import { ReportPanel } from "@/components/report/ReportPanel";
import { ToolCallTrace } from "@/components/agent/ToolCallTrace";

const LOADING_MESSAGES = [
  "Claude is fetching source context…",
  "Claude is grounding the mission in NASA/PDS facts…",
  "Claude is scoring site mineability…",
  "Claude is generating the balanced excavation plan…",
  "Claude is producing autonomy artifacts…",
  "Claude is running the deterministic simulation…",
  "Claude is producing the readiness verdict…",
];

export default function MissionPage() {
  const params = useParams<{ id: string }>();
  const missionId = params.id;

  const [mission, setMission] = useState<Mission | null>(null);
  const [site, setSite] = useState<LunarSite | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [simulation, setSimulation] = useState<SimulationRun | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [sourcesContext, setSourcesContext] = useState<SourcesContext | null>(
    null,
  );
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);

  const [agentResult, setAgentResult] = useState<AgentReadinessResult | null>(
    null,
  );
  const [loadingMissionFetch, setLoadingMissionFetch] = useState(true);
  const [loadingAgent, setLoadingAgent] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [loadingMessageIdx, setLoadingMessageIdx] = useState(0);
  const [scoring, setScoring] = useState<{
    top_dig_zones?: Array<{ x: number; y: number; mineability_score?: number }>;
    processor_placement?: { x?: number; y?: number };
    power_placement?: { x?: number; y?: number };
  }>({});

  const reloadMission = useCallback(async () => {
    const data = await api.mission(missionId);
    setMission(data.mission);
    setSite(data.site);
    setAssets(data.assets);
    setPlan(data.latest_plan);
    setSimulation(data.latest_simulation);
    setAnomalies(data.anomalies);
    if (data.latest_simulation?.readiness_json) {
      // populate scoring inference from simulation telemetry placements
    }
  }, [missionId]);

  const reloadSources = useCallback(async () => {
    const ctx = await api.sourceContext();
    setSourcesContext(ctx);
  }, []);

  const reloadAgentStatus = useCallback(async () => {
    try {
      const status = await api.agentStatus();
      setAgentStatus(status);
    } catch {
      setAgentStatus({
        anthropic_configured: false,
        model: "",
        available_agent_actions: [],
      });
    }
  }, []);

  useEffect(() => {
    setLoadingMissionFetch(true);
    Promise.all([
      reloadMission(),
      reloadSources(),
      reloadAgentStatus(),
    ]).finally(() => setLoadingMissionFetch(false));
  }, [reloadMission, reloadSources, reloadAgentStatus]);

  // Loading message rotation while agent runs
  useEffect(() => {
    if (!loadingAgent) return;
    setLoadingMessageIdx(0);
    const interval = setInterval(() => {
      setLoadingMessageIdx((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1500);
    return () => clearInterval(interval);
  }, [loadingAgent]);

  // Derive scoring from agent result for map overlays
  useEffect(() => {
    if (!agentResult) return;
    // The agent's tool_calls array stores summaries; for placements we leverage
    // whatever the simulation revealed. As a simple inference, fall back to
    // re-fetching mission state which now includes planner-driven placements.
    reloadMission();
  }, [agentResult, reloadMission]);

  // Backfill scoring from plan: derive dig zones from tasks of type 'excavate'
  useEffect(() => {
    if (!plan) return;
    const excavateTasks = plan.tasks_json.filter((t) => t.task_type === "excavate");
    const digMap: Record<string, { x: number; y: number; count: number }> = {};
    for (const t of excavateTasks) {
      const loc = t.from_location;
      if (!loc) continue;
      const k = `${loc.x},${loc.y}`;
      digMap[k] = digMap[k] || { x: loc.x, y: loc.y, count: 0 };
      digMap[k].count += 1;
    }
    const top = Object.values(digMap)
      .sort((a, b) => b.count - a.count)
      .slice(0, 2)
      .map((d) => ({ x: d.x, y: d.y }));

    const processTask = plan.tasks_json.find((t) => t.task_type === "process");
    const chargeTask = plan.tasks_json.find((t) => t.task_type === "charge");

    setScoring({
      top_dig_zones: top,
      processor_placement: processTask?.from_location ?? undefined,
      power_placement: chargeTask?.from_location ?? undefined,
    });
  }, [plan]);

  const runReadiness = useCallback(async () => {
    if (!mission) return;
    setLoadingAgent(true);
    setAgentError(null);
    try {
      const result = await api.runReadiness(mission.id);
      setAgentResult(result);
      await Promise.all([reloadMission(), reloadSources(), reloadAgentStatus()]);
    } catch (e) {
      setAgentError(
        e instanceof Error ? e.message : "Run mission readiness analysis failed",
      );
    } finally {
      setLoadingAgent(false);
    }
  }, [mission, reloadMission, reloadSources, reloadAgentStatus]);

  const readiness: ReadinessJSON | null =
    (agentResult?.readiness as ReadinessJSON) ||
    ((simulation?.readiness_json as ReadinessJSON) ?? null);

  if (loadingMissionFetch && !mission) {
    return (
      <Card>
        <p className="text-[13px] text-muted">Loading mission…</p>
      </Card>
    );
  }
  if (!mission) {
    return (
      <Card>
        <p className="text-[13px] text-status-fail">Mission not found.</p>
      </Card>
    );
  }

  return (
    <div className="grid gap-8">
      <Section step={1} title="Mission Brief">
        <MissionBrief
          mission={mission}
          agentStatus={agentStatus}
          sourcesContext={sourcesContext}
          loading={loadingAgent}
          loadingMessage={
            loadingAgent ? LOADING_MESSAGES[loadingMessageIdx] : null
          }
          error={agentError}
          onRun={runReadiness}
        />
      </Section>

      <Section step={2} title="Readiness Verdict">
        <ReadinessCards readiness={readiness} />
      </Section>

      <Section step={3} title="Executive Recommendation">
        <div className="grid gap-4">
          <ExecutiveRecommendation
            recommendation={
              agentResult?.executive_recommendation ||
              (readiness?.mission_readiness?.explanation ?? "")
            }
            sourceGroundingSummary={agentResult?.source_grounding_summary || ""}
            nextActions={agentResult?.next_actions ?? []}
            toolCallCount={agentResult?.tool_calls.length ?? 0}
            model={agentResult?.model || agentStatus?.model || ""}
          />
          {agentResult ? (
            <ToolCallTrace
              toolCalls={agentResult.tool_calls}
              model={agentResult.model}
            />
          ) : null}
        </div>
      </Section>

      <Section step={4} title="Source Context Evidence">
        <SourcesPanel context={sourcesContext} onRefreshed={setSourcesContext} />
      </Section>

      {site ? (
        <Section step={5} title="Lunar Site Evidence">
          <LunarMap
            site={site}
            mission={mission}
            assets={assets}
            scoring={scoring}
          />
        </Section>
      ) : null}

      <Section step={6} title="Generated Autonomy Plan">
        <PlanPanel plan={plan} />
      </Section>

      <Section step={7} title="Simulation Evidence">
        <SimulationEvidence mission={mission} simulation={simulation} />
      </Section>

      <Section step={8} title="Mission Control · Anomaly Response">
        <AnomalyControl
          simulation={simulation}
          anomalies={anomalies}
          agentEnabled={!!agentStatus?.anthropic_configured}
          onApprovalsChanged={reloadMission}
        />
      </Section>

      <Section step={9} title="Mission Readiness Report">
        <ReportPanel
          missionId={mission.id}
          simulationRunId={simulation?.id ?? null}
          agentEnabled={!!agentStatus?.anthropic_configured}
        />
      </Section>
    </div>
  );
}
