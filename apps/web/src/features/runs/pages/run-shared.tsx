import type { RunState } from "../../../app/api-client";

export const activeRunStates = new Set<RunState>([
  "initializing",
  "running",
  "stopping",
]);

export function formatEnum(value: string | null | undefined) {
  if (!value) return "N/A";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "N/A";
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDuration(ms: number | null | undefined) {
  if (ms == null) return "N/A";
  const seconds = Math.max(Math.round(ms / 1000), 0);
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes === 0) return `${remaining}s`;
  return `${minutes}m ${remaining}s`;
}

export function formatNumber(value: number | null | undefined) {
  if (value == null) return "N/A";
  return new Intl.NumberFormat("en").format(value);
}

export function formatPercent(value: number | null | undefined) {
  if (value == null) return "N/A";
  return `${(value * 100).toFixed(2)}%`;
}

export function formatMs(value: number | null | undefined) {
  if (value == null) return "N/A";
  return `${value.toFixed(value >= 100 ? 0 : 1)} ms`;
}

export function StatusPill({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "success" | "warning" | "error" | "primary";
  children: React.ReactNode;
}) {
  const tones = {
    error: "border-error/35 bg-error-container text-on-error-container",
    neutral: "border-white/10 bg-white/5 text-text-main",
    primary: "border-primary/30 bg-primary/10 text-primary",
    success: "border-success/30 bg-success/10 text-success",
    warning: "border-warning/35 bg-warning/10 text-warning",
  };
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 font-mono text-[11px] leading-4 ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function SectionCard({
  title,
  children,
  testId,
}: {
  title: string;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section
      className="rounded-3xl border border-white/10 bg-white/[0.045] p-5 shadow-[0_24px_70px_rgba(0,0,0,0.22)]"
      data-testid={testId}
    >
      <h2 className="font-display text-xl font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}
