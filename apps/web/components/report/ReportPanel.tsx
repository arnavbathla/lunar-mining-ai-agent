"use client";

import { useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import { api } from "@/lib/api";

interface Props {
  missionId: string;
  simulationRunId: string | null;
  agentEnabled: boolean;
}

export function ReportPanel({ missionId, simulationRunId, agentEnabled }: Props) {
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState("");
  const [toolCount, setToolCount] = useState(0);

  const generate = async () => {
    if (!simulationRunId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.agentReport(missionId, simulationRunId);
      setMarkdown(result.markdown);
      setModel(result.model);
      setToolCount(result.tool_calls.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report generation failed");
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `lunar-mineops-${missionId.slice(0, 8)}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const fallbackUrl = simulationRunId ? api.reportMarkdownUrl(simulationRunId) : "";

  return (
    <Card>
      <CardHeader
        title="Mission Readiness Report"
        subtitle="Markdown · source-grounded · simulation only"
        right={
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              loading={loading}
              disabled={!simulationRunId || !agentEnabled}
              onClick={generate}
            >
              Generate Mission Readiness Report
            </Button>
            <Button
              disabled={!markdown}
              onClick={download}
            >
              Download .md
            </Button>
          </div>
        }
      />
      {error ? (
        <p className="text-[12px] text-status-fail mb-2">{error}</p>
      ) : null}
      {!agentEnabled ? (
        <p className="text-[12px] text-status-caution mb-3">
          Set ANTHROPIC_API_KEY to use Claude for report generation. The
          deterministic backend report is still available at the .md endpoint.
        </p>
      ) : null}
      {markdown ? (
        <div className="border border-line rounded-md bg-bone p-4 text-[12px] leading-relaxed max-h-[480px] overflow-auto">
          <div className="flex items-center gap-2 mb-2">
            <StatusPill label={`${toolCount} tools`} tone="info" />
            <StatusPill label={model || "Claude"} tone="neutral" />
          </div>
          <pre className="whitespace-pre-wrap font-mono text-[11.5px]">
            {markdown}
          </pre>
        </div>
      ) : (
        <div className="text-[12px] text-muted">
          {fallbackUrl ? (
            <span>
              Backend deterministic preview at{" "}
              <a
                className="underline"
                target="_blank"
                rel="noreferrer"
                href={fallbackUrl}
              >
                {fallbackUrl}
              </a>
            </span>
          ) : (
            "Run the readiness analysis first to enable report generation."
          )}
        </div>
      )}
    </Card>
  );
}
