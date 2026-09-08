import type { RunState } from "../../../app/api-client";

export const activeRunStates = new Set<RunState>(["initializing", "running", "stopping"]);
export function formatEnum(value: string | null | undefined) {
  return value ? value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ") : "N/A";
}
export function formatDate(value: string | null | undefined) {
  return value ? new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "N/A";
}
export function formatDuration(ms: number | null | undefined) {
  if (ms == null) return "N/A";
  const seconds = Math.max(Math.round(ms / 1000), 0);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
export function formatNumber(value: number | null | undefined) {
  return value == null ? "N/A" : new Intl.NumberFormat("en").format(value);
}
export function formatPercent(value: number | null | undefined) { return value == null ? "N/A" : `${(value * 100).toFixed(2)}%`; }
export function formatMs(value: number | null | undefined) { return value == null ? "N/A" : `${value.toFixed(value >= 100 ? 0 : 1)} ms`; }

export function StatusPill({ tone = "neutral", children }: { tone?: "neutral" | "success" | "warning" | "error" | "primary"; children: React.ReactNode }) {
  const colors = { neutral: "#bbc9cd", success: "#8aebff", warning: "#d3bbff", error: "#ffb4ab", primary: "#8aebff" };
  return <span style={{ border: `1px solid ${colors[tone]}55`, borderRadius: 999, color: colors[tone], padding: "4px 10px", fontFamily: "monospace", fontSize: 11 }}>{children}</span>;
}
export function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <section style={{ background: "#1b1f2c", border: "1px solid #ffffff1a", borderRadius: 16, marginTop: 20, padding: 20 }}><h2 style={{ color: "#fff", fontSize: 20, margin: 0 }}>{title}</h2><div style={{ marginTop: 16 }}>{children}</div></section>;
}
