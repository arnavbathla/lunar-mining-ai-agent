import { ReactNode } from "react";
import { cx } from "@/lib/utils";

interface MetricStatProps {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "pass" | "caution" | "fail" | "neutral";
  className?: string;
}

const toneClass: Record<NonNullable<MetricStatProps["tone"]>, string> = {
  pass: "text-status-pass",
  caution: "text-status-caution",
  fail: "text-status-fail",
  neutral: "text-ink",
};

export function MetricStat({
  label,
  value,
  hint,
  tone = "neutral",
  className,
}: MetricStatProps) {
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <span className="text-[10px] uppercase tracking-[0.14em] text-muted">
        {label}
      </span>
      <span
        className={cx(
          "text-[22px] font-semibold tracking-tight tabular-nums",
          toneClass[tone],
        )}
      >
        {value}
      </span>
      {hint ? <span className="text-[11px] text-muted">{hint}</span> : null}
    </div>
  );
}
