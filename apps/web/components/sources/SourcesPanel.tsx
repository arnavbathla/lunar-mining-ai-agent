"use client";

import { useState } from "react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import type { SourcesContext } from "@/lib/types";
import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

interface Props {
  context: SourcesContext | null;
  onRefreshed: (ctx: SourcesContext) => void;
}

export function SourcesPanel({ context, onRefreshed }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.refreshSources();
      const ctx = await api.sourceContext();
      onRefreshed(ctx);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setLoading(false);
    }
  };

  const sources = context?.sources ?? [];
  const facts = context?.facts ?? [];

  return (
    <Card>
      <CardHeader
        title="Source Context Evidence"
        subtitle="Public NASA & PDS pages used as planning context"
        right={
          <Button onClick={refresh} loading={loading}>
            Refresh Sources
          </Button>
        }
      />
      {error ? (
        <p className="text-[12px] text-status-fail mb-3">{error}</p>
      ) : null}
      <div className="grid gap-2">
        {sources.length === 0 ? (
          <p className="text-[13px] text-muted">
            No source documents yet. Click Refresh Sources to fetch live or
            fall back.
          </p>
        ) : (
          sources.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between gap-3 border border-line rounded-md px-3 py-2"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[13px] font-medium text-ink hover:underline truncate"
                  >
                    {s.title}
                  </a>
                  {s.is_fallback ? (
                    <StatusPill label="Fallback" tone="caution" />
                  ) : (
                    <StatusPill label="Live" tone="pass" />
                  )}
                </div>
                <div className="text-[11px] text-muted mt-0.5 truncate">
                  {s.url}
                </div>
              </div>
              <div className="text-[11px] text-muted shrink-0 text-right">
                fetched_at
                <div className="font-mono text-[11px] text-ink">
                  {formatRelativeTime(s.fetched_at)}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
      {facts.length > 0 ? (
        <details className="mt-4">
          <summary className="text-[11px] uppercase tracking-[0.14em] text-muted cursor-pointer hover:text-ink">
            Show {facts.length} extracted facts
          </summary>
          <ul className="mt-3 grid gap-1.5 max-h-72 overflow-auto pr-2">
            {facts.slice(0, 60).map((f, i) => (
              <li
                key={i}
                className="text-[12px] text-ink border-l-2 border-line pl-3"
              >
                <span className="text-[10px] uppercase tracking-wider text-muted mr-2">
                  {f.category}
                </span>
                {f.fact}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Card>
  );
}
