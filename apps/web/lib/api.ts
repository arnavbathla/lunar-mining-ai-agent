import type {
  AgentAnomalyResult,
  AgentReadinessResult,
  AgentReportResult,
  AgentStatus,
  Anomaly,
  Approval,
  DefaultDashboard,
  DemoSeedOut,
  MissionBundle,
  SourcesContext,
  SourceDocument,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  const isJson = res.headers
    .get("content-type")
    ?.toLowerCase()
    .includes("application/json");
  const body = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const message =
      (body && typeof body === "object" && (body as any).detail) ||
      (typeof body === "string" ? body : "Request failed");
    const error = new Error(String(message));
    (error as any).status = res.status;
    (error as any).body = body;
    throw error;
  }
  return body as T;
}

export const api = {
  baseUrl: BASE_URL,

  health() {
    return request<{ status: string; anthropic_configured: boolean }>(
      "/health",
    );
  },

  // Demo
  seedDemo() {
    return request<DemoSeedOut>("/demo/seed", { method: "POST" });
  },
  resetDemo() {
    return request<{ status: string }>("/demo/reset", { method: "POST" });
  },
  defaultDashboard() {
    return request<DefaultDashboard>("/demo/default-dashboard");
  },

  // Mission
  mission(missionId: string) {
    return request<MissionBundle>(`/missions/${missionId}`);
  },

  // Sources
  sources() {
    return request<SourceDocument[]>("/sources");
  },
  refreshSources() {
    return request<{
      refreshed: number;
      failed: number;
      used_fallback: boolean;
      sources: SourceDocument[];
    }>("/sources/refresh", { method: "POST" });
  },
  sourceContext() {
    return request<SourcesContext>("/sources/context");
  },

  // Simulation
  simulationTelemetry(runId: string) {
    return request<{
      telemetry: any[];
      production_curve: { hour: number; cumulative_output_kg: number }[];
      battery_curve: { hour: number; min_battery_pct: number; avg_battery_pct: number }[];
      power_curve: { hour: number; total_power_kw: number }[];
    }>(`/simulation-runs/${runId}/telemetry`);
  },
  runAnomalies(runId: string) {
    return request<Anomaly[]>(`/simulation-runs/${runId}/anomalies`);
  },
  runApprovals(runId: string) {
    return request<Approval[]>(`/simulation-runs/${runId}/approvals`);
  },
  approve(approvalId: string, note?: string) {
    return request<Approval>(`/approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify({ operator_note: note ?? "" }),
    });
  },
  reject(approvalId: string, note?: string) {
    return request<Approval>(`/approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify({ operator_note: note ?? "" }),
    });
  },

  reportMarkdownUrl(runId: string) {
    return `${BASE_URL}/simulation-runs/${runId}/report.md`;
  },
  fetchReportMarkdown(runId: string) {
    return fetch(`${BASE_URL}/simulation-runs/${runId}/report.md`).then((r) =>
      r.text(),
    );
  },

  // Agent
  agentStatus() {
    return request<AgentStatus>("/agent/status");
  },
  runReadiness(missionId: string, seed = 42) {
    return request<AgentReadinessResult>("/agent/run-readiness-analysis", {
      method: "POST",
      body: JSON.stringify({ mission_id: missionId, seed }),
    });
  },
  anomalyResponse(simulationRunId: string, anomalyId: string) {
    return request<AgentAnomalyResult>("/agent/anomaly-response", {
      method: "POST",
      body: JSON.stringify({
        simulation_run_id: simulationRunId,
        anomaly_id: anomalyId,
      }),
    });
  },
  agentReport(missionId: string, simulationRunId: string) {
    return request<AgentReportResult>("/agent/report", {
      method: "POST",
      body: JSON.stringify({
        mission_id: missionId,
        simulation_run_id: simulationRunId,
      }),
    });
  },
  agentRefreshSources() {
    return request<{ tool_calls: any[]; summary: any; agent_run_id: string }>(
      "/agent/refresh-sources",
      { method: "POST" },
    );
  },
};
