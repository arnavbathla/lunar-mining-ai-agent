"use client";

import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import type { ReadinessJSON, ReadinessDimension } from "@/lib/types";
import { readinessLabel } from "@/lib/utils";

interface Props {
  readiness: ReadinessJSON | null | Record<string, never>;
}

export function ReadinessCards({ readiness }: Props) {
  const r = readiness as ReadinessJSON | null;
  return (
    <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-5">
      <ReadinessCardLarge
        title="Mission Readiness"
        dim={r?.mission_readiness}
      />
      <ReadinessCard title="Site Mineability" dim={r?.site_mineability} />
      <ReadinessCard title="Production Target" dim={r?.production_target} />
      <ReadinessCard title="Power Budget" dim={r?.power_budget} />
      <ReadinessCard title="Autonomy Risk" dim={r?.autonomy_risk} />
    </div>
  );
}

function ReadinessCard({
  title,
  dim,
}: {
  title: string;
  dim?: ReadinessDimension;
}) {
  const { label, tone } = readinessLabel(dim?.status);
  return (
    <Card padded>
      <div className="text-[11px] uppercase tracking-[0.14em] text-muted mb-2">
        {title}
      </div>
      <StatusPill label={label} tone={tone} />
      <p className="text-[12px] text-ink mt-3 leading-snug">
        {dim?.explanation || "Run the analysis to populate this verdict."}
      </p>
    </Card>
  );
}

function ReadinessCardLarge({
  title,
  dim,
}: {
  title: string;
  dim?: ReadinessDimension;
}) {
  const { label, tone } = readinessLabel(dim?.status);
  const accent =
    tone === "pass"
      ? "bg-emerald-50 border-emerald-200"
      : tone === "caution"
        ? "bg-amber-50 border-amber-200"
        : tone === "fail"
          ? "bg-rose-50 border-rose-200"
          : "bg-bone";
  return (
    <Card
      padded
      className={`md:col-span-2 lg:col-span-1 lg:row-span-1 ring-1 ring-line/60 ${accent}`}
    >
      <div className="text-[11px] uppercase tracking-[0.14em] text-muted mb-2">
        {title}
      </div>
      <div className="text-2xl font-semibold tracking-tight text-ink mb-2">
        {label}
      </div>
      <p className="text-[12px] text-ink leading-snug">
        {dim?.explanation || "Awaiting readiness analysis."}
      </p>
    </Card>
  );
}
