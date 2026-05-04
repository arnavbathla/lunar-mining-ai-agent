"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";

export default function LandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [anthropicConfigured, setAnthropicConfigured] = useState<boolean | null>(
    null,
  );
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealthy(h.status === "ok");
        setAnthropicConfigured(h.anthropic_configured);
      })
      .catch(() => setHealthy(false));
  }, []);

  const launch = async () => {
    setLoading(true);
    setError(null);
    try {
      const seed = await api.seedDemo();
      router.push(`/missions/${seed.mission.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to seed demo mission");
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-[1.1fr_1fr] items-stretch">
      <Card className="flex flex-col gap-6 justify-between">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <StatusPill label="Mission Readiness" tone="info" />
            <StatusPill label="Source Grounded" tone="neutral" />
            <StatusPill label="Simulation Only" tone="neutral" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">
            Validate the mine before you launch the hardware.
          </h1>
          <p className="text-sm text-muted mt-3 max-w-prose">
            Lunar MineOps AI OS is a mission readiness agent for lunar ISRU
            teams. It validates whether an autonomous lunar
            excavation-to-processing concept closes operationally before launch:
            terrain, power, mobility, processing, autonomy, and anomaly
            constraints, end-to-end.
          </p>
          <ul className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-y-1.5 gap-x-6 text-[12px] text-ink">
            <li>· Synthetic 30×30 polar site, deterministic by seed</li>
            <li>· 168 h hourly simulation with anomaly cadence</li>
            <li>· Claude-generated balanced excavation plan</li>
            <li>· Five-dimension Go / Conditional Go / No-Go verdict</li>
            <li>· Source-grounded NASA / PDS public context</li>
            <li>· Markdown mission readiness report</li>
          </ul>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            size="md"
            loading={loading}
            onClick={launch}
          >
            Launch Demo Mission
          </Button>
          {error ? (
            <span className="text-[12px] text-status-fail">{error}</span>
          ) : null}
        </div>
      </Card>
      <Card>
        <CardHeader title="System status" />
        <dl className="grid grid-cols-1 gap-3 text-[13px]">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <dt className="text-muted">Backend</dt>
            <dd>
              {healthy === null ? (
                <StatusPill label="Checking" tone="neutral" />
              ) : healthy ? (
                <StatusPill label="Online" tone="pass" />
              ) : (
                <StatusPill label="Offline" tone="fail" />
              )}
            </dd>
          </div>
          <div className="flex items-center justify-between border-b border-line pb-2">
            <dt className="text-muted">Anthropic Claude</dt>
            <dd>
              {anthropicConfigured === null ? (
                <StatusPill label="Checking" tone="neutral" />
              ) : anthropicConfigured ? (
                <StatusPill label="Configured" tone="pass" />
              ) : (
                <StatusPill label="Missing key" tone="caution" />
              )}
            </dd>
          </div>
          <div className="flex items-center justify-between border-b border-line pb-2">
            <dt className="text-muted">Mission seed</dt>
            <dd className="font-mono text-[12px]">42</dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-muted">Demo mission</dt>
            <dd className="font-mono text-[12px]">Shackleton Ridge ISRU</dd>
          </div>
        </dl>
        {anthropicConfigured === false ? (
          <p className="text-[12px] text-status-caution mt-4 leading-relaxed">
            Backend boots and seeds deterministic data without an API key.
            Claude agent endpoints (Run Mission Readiness Analysis, Anomaly
            Response, Generate Report) require <code>ANTHROPIC_API_KEY</code> in{" "}
            <code className="font-mono">apps/api/.env</code>.
          </p>
        ) : null}
      </Card>
    </div>
  );
}
