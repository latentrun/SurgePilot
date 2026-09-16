import { Link } from "react-router-dom";

import type { LoadNodeConnectivitySummary } from "../../../app/api-client";
import { cn } from "../../../utils/cn";

type Props = Readonly<{
  summary?: LoadNodeConnectivitySummary;
  isAdmin: boolean;
  loadFailed?: boolean;
  successContext?: boolean;
}>;

function badgeTone(readiness?: LoadNodeConnectivitySummary["readiness"]) {
  if (readiness === "ready") {
    return "border-success/30 bg-success/10 text-success";
  }
  if (readiness === "invalid") {
    return "border-warning/30 bg-warning/10 text-warning";
  }
  return "border-white/10 bg-white/5 text-text-muted";
}

function sourceLabel(source?: LoadNodeConnectivitySummary["source"]) {
  if (source === "env_fallback") return "env fallback";
  if (source === "configured") return "configured";
  return "missing";
}

export function LoadNodeConnectivitySummaryCard({
  isAdmin,
  loadFailed = false,
  successContext = false,
  summary,
}: Props) {
  const readiness = loadFailed ? "missing" : summary?.readiness;
  const showWarning =
    loadFailed || readiness === "missing" || readiness === "invalid";
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-4 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white">Load Node API</h2>
          <p className="mt-1 text-xs leading-5 text-text-muted">
            Used by future remote runs when the runner calls SurgePilot API.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs font-semibold text-secondary">
            {sourceLabel(summary?.source)}
          </span>
          <span
            className={cn(
              "rounded-full border px-2.5 py-1 text-xs font-semibold",
              badgeTone(readiness),
            )}
          >
            {readiness ?? "missing"}
          </span>
        </div>
      </div>
      <div className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3 font-mono text-xs text-text-main">
        {loadFailed
          ? "Connectivity summary could not be loaded."
          : (summary?.effectiveUrl ?? "Not configured")}
      </div>
      <p className="mt-3 text-xs leading-5 text-text-muted">
        {loadFailed
          ? "Initialization can continue; run start will still validate the current server setting."
          : (summary?.message ?? "Load Node API Base URL is not configured.")}
      </p>
      {successContext ? (
        <p className="mt-2 text-xs leading-5 text-text-muted">
          Initialization does not use this URL. Fixing this URL later does not
          require reinitializing the node.
        </p>
      ) : null}
      {showWarning ? (
        <div className="mt-3 rounded-xl border border-warning/30 bg-warning/10 p-3 text-xs leading-5 text-warning">
          Initialization can continue, but future remote runs will be blocked
          until the Load Node API Base URL is fixed.
          <div className="mt-2">
            {isAdmin ? (
              <Link
                className="font-semibold underline underline-offset-4"
                to="/admin/system-settings"
              >
                Open System Settings
              </Link>
            ) : (
              <span>Contact an administrator to update System Settings.</span>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
