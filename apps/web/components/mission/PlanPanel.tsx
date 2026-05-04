"use client";

import { useMemo, useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import { MetricStat } from "@/components/ui/MetricStat";
import type { Plan } from "@/lib/types";

export function PlanPanel({ plan }: { plan: Plan | null }) {
  const [tab, setTab] = useState<"tasks" | "tree" | "ros" | "sm" | "runbook">(
    "tasks",
  );
  if (!plan) {
    return (
      <Card>
        <CardHeader title="Generated Autonomy Plan" />
        <p className="text-[13px] text-muted">
          The plan appears here after Run Mission Readiness Analysis.
        </p>
      </Card>
    );
  }

  const tasks = plan.tasks_json ?? [];
  const risks = plan.risk_register_json ?? [];
  const artifacts = plan.autonomy_artifacts_json ?? {
    behavior_tree: "",
    state_machine: "",
    operator_runbook: "",
    ros_task_messages: [],
  };

  return (
    <Card>
      <CardHeader
        title="Generated Autonomy Plan"
        subtitle={plan.summary}
        right={<StatusPill label="Autonomy Draft" tone="neutral" />}
      />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 border-b border-line pb-4">
        <MetricStat
          label="Expected output"
          value={`${plan.expected_output_kg.toFixed(1)} kg`}
        />
        <MetricStat
          label="Confidence"
          value={`${plan.confidence_pct.toFixed(0)} %`}
        />
        <MetricStat label="Tasks" value={tasks.length} />
        <MetricStat label="Risks" value={risks.length} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-6 mt-4">
        <div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted mb-2">
            Risk register
          </div>
          <ul className="grid gap-2">
            {risks.map((r, i) => (
              <li
                key={i}
                className="border border-line rounded-md p-2 text-[12px]"
              >
                <div className="flex items-center gap-2">
                  <StatusPill
                    label={r.severity.toUpperCase()}
                    tone={
                      r.severity === "high"
                        ? "fail"
                        : r.severity === "medium"
                          ? "caution"
                          : "pass"
                    }
                  />
                  <span className="font-medium text-ink">{r.risk}</span>
                </div>
                <p className="text-muted mt-1">
                  Likelihood: {r.likelihood}. {r.mitigation}
                </p>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            {(
              [
                ["tasks", "Tasks"],
                ["tree", "Behavior tree"],
                ["sm", "State machine"],
                ["ros", "ROS messages"],
                ["runbook", "Runbook"],
              ] as Array<[typeof tab, string]>
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`px-2 py-1 rounded-md text-[11px] uppercase tracking-wider border ${
                  tab === key
                    ? "bg-ink text-paper border-ink"
                    : "bg-paper text-ink border-line hover:border-ink"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="border border-line rounded-md p-2 max-h-72 overflow-auto">
            {tab === "tasks" ? (
              <TaskTable tasks={tasks} />
            ) : (
              <pre className="text-[11.5px] text-ink whitespace-pre-wrap font-mono">
                {tab === "tree"
                  ? artifacts.behavior_tree
                  : tab === "sm"
                    ? artifacts.state_machine
                    : tab === "runbook"
                      ? artifacts.operator_runbook
                      : JSON.stringify(artifacts.ros_task_messages, null, 2)}
              </pre>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function TaskTable({ tasks }: { tasks: Plan["tasks_json"] }) {
  const sorted = useMemo(
    () => tasks.slice().sort((a, b) => a.start_hour - b.start_hour).slice(0, 80),
    [tasks],
  );
  return (
    <table className="w-full text-[12px]">
      <thead className="text-[10px] uppercase tracking-[0.14em] text-muted text-left border-b border-line">
        <tr>
          <th className="py-1.5 pr-2">Hour</th>
          <th className="pr-2">Asset</th>
          <th className="pr-2">Task</th>
          <th className="pr-2">From</th>
          <th className="pr-2">To</th>
          <th className="pr-2 text-right">Output</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((t) => (
          <tr key={t.id} className="border-b border-line/60 hover:bg-bone">
            <td className="py-1 pr-2 font-mono text-[11px]">
              {t.start_hour}–{t.end_hour}
            </td>
            <td className="pr-2">{t.asset_name}</td>
            <td className="pr-2">
              <span className="inline-block rounded-sm bg-bone border border-line px-1.5 py-0.5 text-[10px] uppercase tracking-wider">
                {t.task_type}
              </span>
            </td>
            <td className="pr-2 font-mono text-[11px] text-muted">
              {t.from_location
                ? `(${t.from_location.x},${t.from_location.y})`
                : "—"}
            </td>
            <td className="pr-2 font-mono text-[11px] text-muted">
              {t.to_location ? `(${t.to_location.x},${t.to_location.y})` : "—"}
            </td>
            <td className="pr-2 text-right font-mono">
              {t.expected_output_kg ? t.expected_output_kg.toFixed(1) : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
