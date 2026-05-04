export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function formatPct(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function formatKg(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)} kg`;
}

export function formatHours(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)} h`;
}

export function formatKw(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${value.toFixed(digits)} kW`;
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "never";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

export function readinessLabel(
  status: string | undefined | null,
): { label: string; tone: "pass" | "caution" | "fail" | "neutral" } {
  if (!status) return { label: "PENDING", tone: "neutral" };
  const norm = status.toString().trim().toLowerCase().replace(/[\s-]+/g, "_");
  switch (norm) {
    case "pass":
      return { label: "PASS", tone: "pass" };
    case "caution":
    case "warn":
    case "warning":
      return { label: "CAUTION", tone: "caution" };
    case "fail":
      return { label: "FAIL", tone: "fail" };
    case "go":
      return { label: "GO", tone: "pass" };
    case "conditional_go":
      return { label: "CONDITIONAL GO", tone: "caution" };
    case "no_go":
    case "nogo":
      return { label: "NO-GO", tone: "fail" };
    default:
      return { label: "PENDING", tone: "neutral" };
  }
}

export function severityTone(
  severity: string,
): "pass" | "caution" | "fail" | "neutral" {
  switch (severity) {
    case "low":
      return "pass";
    case "medium":
      return "caution";
    case "high":
    case "critical":
      return "fail";
    default:
      return "neutral";
  }
}
