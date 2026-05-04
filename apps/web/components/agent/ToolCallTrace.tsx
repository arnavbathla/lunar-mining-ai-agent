"use client";

import { useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import type { AgentToolCall } from "@/lib/types";

interface Props {
  toolCalls: AgentToolCall[];
  model: string;
}

export function ToolCallTrace({ toolCalls, model }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  if (toolCalls.length === 0) return null;
  return (
    <Card>
      <CardHeader
        title="Claude Tool-use Trace"
        subtitle={`${toolCalls.length} server-side tool calls`}
        right={<StatusPill label={model || "Claude"} tone="info" />}
      />
      <ol className="grid gap-1.5">
        {toolCalls.map((c, i) => {
          const isOpen = expanded === i;
          return (
            <li
              key={i}
              className={`border border-line rounded-md text-[12px] ${
                c.is_error ? "bg-rose-50" : "bg-paper"
              }`}
            >
              <button
                className="w-full text-left px-3 py-2 flex items-center justify-between gap-3"
                onClick={() => setExpanded(isOpen ? null : i)}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] text-muted">
                    {String(c.iteration).padStart(2, "0")}
                  </span>
                  <span className="font-medium text-ink">{c.tool}</span>
                  {c.is_error ? (
                    <StatusPill label="error" tone="fail" />
                  ) : (
                    <StatusPill label="ok" tone="pass" />
                  )}
                </div>
                <span className="text-muted text-[11px]">
                  {isOpen ? "Hide" : "Inspect"}
                </span>
              </button>
              {isOpen ? (
                <div className="border-t border-line p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.14em] text-muted mb-1">
                      Input
                    </div>
                    <pre className="font-mono text-[11px] whitespace-pre-wrap text-ink">
                      {JSON.stringify(c.input, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.14em] text-muted mb-1">
                      Output summary
                    </div>
                    <pre className="font-mono text-[11px] whitespace-pre-wrap text-ink">
                      {JSON.stringify(c.output_summary, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
