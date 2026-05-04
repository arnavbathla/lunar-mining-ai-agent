import { cx } from "@/lib/utils";

type Tone = "pass" | "caution" | "fail" | "neutral" | "info";

const toneClass: Record<Tone, string> = {
  pass: "bg-emerald-50 text-status-pass border-emerald-200",
  caution: "bg-amber-50 text-status-caution border-amber-200",
  fail: "bg-rose-50 text-status-fail border-rose-200",
  neutral: "bg-bone text-muted border-line",
  info: "bg-accent-soft text-accent-dark border-accent/30",
};

export function StatusPill({
  label,
  tone = "neutral",
  className,
}: {
  label: string;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span className={cx("status-pill", toneClass[tone], className)}>
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{
          background:
            tone === "pass"
              ? "#1f7a4d"
              : tone === "caution"
                ? "#a06a00"
                : tone === "fail"
                  ? "#a32020"
                  : tone === "info"
                    ? "#5b5bd6"
                    : "#9aa0a6",
        }}
      />
      {label}
    </span>
  );
}
