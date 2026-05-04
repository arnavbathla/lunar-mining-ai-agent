"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import { api } from "@/lib/api";
import type {
  AgentAnomalyResult,
  Anomaly,
  Approval,
  SimulationRun,
} from "@/lib/types";
import { severityTone } from "@/lib/utils";

interface Props {
  simulation: SimulationRun | null;
  anomalies: Anomaly[];
  agentEnabled: boolean;
  onApprovalsChanged?: () => void;
}

export function AnomalyControl({
  simulation,
  anomalies,
  agentEnabled,
  onApprovalsChanged,
}: Props) {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [recommendations, setRecommendations] = useState<
    Record<string, AgentAnomalyResult>
  >({});
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState<Record<string, string>>({});

  const loadApprovals = async () => {
    if (!simulation) return;
    try {
      const list = await api.runApprovals(simulation.id);
      setApprovals(list);
    } catch {
      setApprovals([]);
    }
  };

  useEffect(() => {
    setApprovals([]);
    setRecommendations({});
    if (simulation) loadApprovals();
  }, [simulation?.id]);

  const askClaude = async (anomaly: Anomaly) => {
    if (!simulation) return;
    setLoadingId(anomaly.id);
    setErrorId(null);
    setErrorMessage(null);
    try {
      const result = await api.anomalyResponse(simulation.id, anomaly.id);
      setRecommendations((prev) => ({ ...prev, [anomaly.id]: result }));
      await loadApprovals();
      onApprovalsChanged?.();
    } catch (e) {
      setErrorId(anomaly.id);
      setErrorMessage(
        e instanceof Error ? e.message : "Anomaly response failed",
      );
    } finally {
      setLoadingId(null);
    }
  };

  const decide = async (
    approvalId: string,
    decision: "approve" | "reject",
  ) => {
    const note = noteDraft[approvalId] ?? "";
    try {
      if (decision === "approve") {
        await api.approve(approvalId, note);
      } else {
        await api.reject(approvalId, note);
      }
      await loadApprovals();
      onApprovalsChanged?.();
    } catch (e) {
      setErrorMessage(
        e instanceof Error ? e.message : "Approval action failed",
      );
    }
  };

  return (
    <Card>
      <CardHeader
        title="Mission Control · Anomaly Response"
        subtitle="Anomalies, Claude recommendations, and operator approvals"
        right={
          !agentEnabled ? (
            <StatusPill label="Anthropic key required" tone="caution" />
          ) : null
        }
      />
      {errorMessage ? (
        <p className="text-[12px] text-status-fail mb-2">{errorMessage}</p>
      ) : null}
      {anomalies.length === 0 ? (
        <p className="text-[13px] text-muted">
          No anomalies recorded yet. Run the readiness analysis to populate
          this list.
        </p>
      ) : (
        <ul className="grid gap-3">
          {anomalies.map((a) => {
            const rec = recommendations[a.id];
            const matchedApproval = approvals.find(
              (ap) => ap.anomaly_id === a.id,
            );
            return (
              <li
                key={a.id}
                className="border border-line rounded-md p-3 grid gap-2"
              >
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusPill
                      label={a.severity.toUpperCase()}
                      tone={severityTone(a.severity)}
                    />
                    <span className="font-medium text-ink text-[13px]">
                      {a.type.replace(/_/g, " ")}
                    </span>
                    <span className="font-mono text-[11px] text-muted">
                      h{a.hour}
                    </span>
                    {a.requires_human_approval ? (
                      <StatusPill label="Approval Required" tone="fail" />
                    ) : null}
                  </div>
                  <Button
                    onClick={() => askClaude(a)}
                    loading={loadingId === a.id}
                    disabled={!agentEnabled}
                    size="sm"
                  >
                    Ask Claude for Response
                  </Button>
                </div>
                <p className="text-[12px] text-ink leading-snug">
                  <span className="text-muted mr-2">Likely cause:</span>
                  {a.root_cause_hypothesis}
                </p>
                <p className="text-[12px] text-ink leading-snug">
                  <span className="text-muted mr-2">Recommended action:</span>
                  {a.recommended_action}
                </p>
                <p className="text-[12px] text-muted">
                  Production impact: {a.production_impact_kg.toFixed(2)} kg
                </p>
                {errorId === a.id ? (
                  <p className="text-[12px] text-status-fail">
                    {errorMessage}
                  </p>
                ) : null}
                {rec ? (
                  <div className="mt-1 rounded-md bg-bone border border-line p-2 text-[12px] grid gap-1">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-muted">
                      Claude recommendation ({rec.tool_calls.length} tool calls)
                    </div>
                    <p>
                      {rec.recommendation?.recommended_action ||
                        rec.operator_message}
                    </p>
                    {rec.recommendation?.alternative_actions ? (
                      <ul className="list-disc pl-5 text-muted">
                        {rec.recommendation.alternative_actions.map((alt, i) => (
                          <li key={i}>{alt}</li>
                        ))}
                      </ul>
                    ) : null}
                    {rec.recommendation?.confidence_pct ? (
                      <p className="text-muted">
                        Confidence:{" "}
                        {rec.recommendation.confidence_pct.toFixed(0)} %
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {matchedApproval ? (
                  <div className="mt-1 rounded-md border border-line p-2 grid gap-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <StatusPill
                          label={`Approval · ${matchedApproval.status}`}
                          tone={
                            matchedApproval.status === "approved"
                              ? "pass"
                              : matchedApproval.status === "rejected"
                                ? "fail"
                                : "caution"
                          }
                        />
                        <span className="font-mono text-[11px] text-muted">
                          {matchedApproval.id.slice(0, 8)}
                        </span>
                      </div>
                    </div>
                    <p className="text-[12px] text-ink">
                      {matchedApproval.recommended_action}
                    </p>
                    {matchedApproval.status === "pending" ? (
                      <div className="grid gap-2">
                        <textarea
                          className="text-[12px] border border-line rounded-md p-2 w-full min-h-[48px]"
                          placeholder="Operator note (optional)"
                          value={noteDraft[matchedApproval.id] ?? ""}
                          onChange={(e) =>
                            setNoteDraft((p) => ({
                              ...p,
                              [matchedApproval.id]: e.target.value,
                            }))
                          }
                        />
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() =>
                              decide(matchedApproval.id, "approve")
                            }
                          >
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() =>
                              decide(matchedApproval.id, "reject")
                            }
                          >
                            Reject
                          </Button>
                        </div>
                      </div>
                    ) : (
                      matchedApproval.operator_note && (
                        <p className="text-[12px] text-muted">
                          Note: {matchedApproval.operator_note}
                        </p>
                      )
                    )}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
