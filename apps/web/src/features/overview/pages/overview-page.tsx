import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Activity,
  FileArchive,
  PlayCircle,
  RefreshCw,
  Server,
  Workflow,
} from "lucide-react";

import {
  ApiError,
  getOverview,
  type OverviewRecentRun,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { formatEnum, StatusPill } from "../../runs/pages/run-shared";

function numberText(value: number | null | undefined) {
  if (value == null) return "Unavailable";
  return new Intl.NumberFormat("en").format(value);
}

function formatDuration(value: number | null | undefined) {
  if (value == null) return "Unavailable";
  const seconds = Math.max(Math.round(value / 1000), 0);
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  if (minutes === 0) return `${remaining}s`;
  return `${minutes}m ${remaining}s`;
}

function stateTone(state: string) {
  if (state === "finished") return "success" as const;
  if (state === "failed") return "error" as const;
  if (state === "aborted") return "warning" as const;
  return "primary" as const;
}

function slaTone(value: string | null | undefined) {
  if (value === "passed") return "success" as const;
  if (value === "failed") return "warning" as const;
  return "neutral" as const;
}

function Card({
  children,
  title,
}: Readonly<{ children: React.ReactNode; title: string }>) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.045] p-5 shadow-[0_24px_70px_rgba(0,0,0,0.22)]">
      <h2 className="font-display text-xl font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Metric({
  label,
  value,
  note,
}: Readonly<{ label: string; value: number | string; note?: string }>) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/15 p-4">
      <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
        {label}
      </div>
      <div className="mt-2 font-display text-3xl font-semibold text-white">
        {typeof value === "number" ? numberText(value) : value}
      </div>
      {note ? (
        <div className="mt-1 text-xs leading-5 text-text-muted">{note}</div>
      ) : null}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div
      aria-label="Loading overview"
      className="grid gap-5 md:grid-cols-3"
      role="status"
    >
      {["summary", "activity", "resources"].map((key) => (
        <div
          className="h-36 animate-pulse rounded-3xl border border-white/10 bg-white/[0.045]"
          key={key}
        />
      ))}
    </div>
  );
}

function errorCopy(error: unknown) {
  if (error instanceof ApiError) {
    return `Overview could not be loaded. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Overview could not be loaded. Refresh and try again.";
}

function RecentRunRow({ run }: Readonly<{ run: OverviewRecentRun }>) {
  return (
    <Link
      className="grid gap-3 border-b border-white/5 px-4 py-4 text-sm transition last:border-b-0 hover:bg-white/[0.035] md:grid-cols-[1.3fr_0.7fr_0.8fr_0.8fr_0.7fr] md:items-center"
      to={`/runs/${run.id}`}
    >
      <div className="min-w-0">
        <div className="truncate font-semibold text-white">
          {run.sourceName ?? run.id}
        </div>
        <div className="mt-1 truncate font-mono text-[11px] text-secondary">
          {run.id}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <StatusPill tone={run.runType === "debug" ? "warning" : "primary"}>
          {formatEnum(run.runType)}
        </StatusPill>
      </div>
      <div className="flex flex-wrap gap-2">
        <StatusPill tone={stateTone(run.state)}>
          {formatEnum(run.state)}
        </StatusPill>
      </div>
      <div className="flex flex-wrap gap-2">
        {run.validity ? (
          <StatusPill tone={run.validity === "invalid" ? "warning" : "success"}>
            {formatEnum(run.validity)}
          </StatusPill>
        ) : (
          <StatusPill>Unavailable</StatusPill>
        )}
        {run.slaResult ? (
          <StatusPill tone={slaTone(run.slaResult)}>
            SLA {formatEnum(run.slaResult)}
          </StatusPill>
        ) : (
          <StatusPill>Unavailable</StatusPill>
        )}
      </div>
      <div className="text-text-muted">
        <div>{formatDuration(run.durationMs)}</div>
        <div className="mt-1 inline-flex items-center gap-1 font-mono text-[11px] text-secondary">
          <FileArchive className="h-3.5 w-3.5" /> {run.artifactCount}
          {run.hasArtifactsZip ? " + ZIP" : ""}
        </div>
      </div>
    </Link>
  );
}

const quickActions = [
  {
    label: "Create Scenario",
    description: "Design request flow steps.",
    to: "/scenarios",
    Icon: Workflow,
  },
  {
    label: "Create Test Plan",
    description: "Configure load and SLA rules.",
    to: "/test-plans",
    Icon: PlayCircle,
  },
  {
    label: "View Runs",
    description: "Open recent reports and artifacts.",
    to: "/runs",
    Icon: Activity,
  },
  {
    label: "Manage Load Nodes",
    description: "Register or check runner nodes.",
    to: "/resources/load-nodes",
    Icon: Server,
  },
];

export function OverviewPage() {
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const query = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["overview", workspaceId],
    queryFn: () => getOverview({ workspaceId, recentLimit: 5 }),
    retry: false,
  });
  const overview = query.data;

  if (session === null) {
    return null;
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="surgepilot-glass overflow-hidden rounded-3xl p-7">
        <div className="mb-5 h-px w-full surgepilot-hairline" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase leading-3 tracking-[0.22em] text-secondary">
              Default Workspace · Last {overview?.statsScope.windowDays ?? 30}{" "}
              days
            </p>
            <h1 className="mt-3 font-display text-3xl font-semibold text-white">
              Overview
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
              Current execution activity, Valid Standard Run results, and
              visible Load Node status for{" "}
              {overview?.workspace.name ?? session.defaultWorkspace.name}.
            </p>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Signed in as{" "}
              <span className="font-semibold text-white">
                {session.user.displayName}
              </span>
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-right">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-secondary">
              Workspace
            </div>
            <div className="mt-1 text-sm font-semibold text-white">
              {overview?.workspace.name ?? session.defaultWorkspace.name}
            </div>
          </div>
        </div>
        {query.isFetching && !query.isLoading ? (
          <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 font-mono text-[11px] text-primary">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Refreshing
          </div>
        ) : null}
      </div>

      {query.isLoading ? <LoadingSkeleton /> : null}
      {query.isError ? (
        <div className="rounded-3xl border border-error/30 bg-error-container p-5 text-sm text-on-error-container">
          <div className="font-semibold">Unable to load Overview</div>
          <p className="mt-1">{errorCopy(query.error)}</p>
          <button
            className="mt-4 rounded-xl border border-error/30 px-4 py-2 font-semibold"
            onClick={() => query.refetch()}
            type="button"
          >
            Try again
          </button>
        </div>
      ) : null}

      {overview ? (
        <>
          <Card title="Run Summary">
            <p className="mb-4 text-sm text-text-muted">
              Result statistics include Valid Standard terminal Runs only.
              Active activity is counted separately.
            </p>
            <div className="grid gap-4 md:grid-cols-4">
              <Metric
                label="Valid Standard Runs"
                value={overview.runStats.resultRuns.total}
                note="Terminal runs in this window"
              />
              <Metric
                label="Finished"
                value={overview.runStats.resultRuns.byState.finished}
              />
              <Metric
                label="Failed State"
                value={overview.runStats.resultRuns.byState.failed}
                note="Process failed, not SLA failed"
              />
              <Metric
                label="Aborted"
                value={overview.runStats.resultRuns.byState.aborted}
              />
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-4">
              <Metric
                label="SLA Passed"
                value={overview.runStats.resultRuns.bySlaResult.passed}
              />
              <Metric
                label="SLA Failed"
                value={overview.runStats.resultRuns.bySlaResult.failed}
                note="SLA result only"
              />
              <Metric
                label="Not Evaluated"
                value={overview.runStats.resultRuns.bySlaResult.notEvaluated}
              />
              <Metric
                label="Active Runs"
                value={overview.runStats.activeRuns.total}
                note={`${overview.runStats.activeRuns.initializing} initializing · ${overview.runStats.activeRuns.running} running · ${overview.runStats.activeRuns.stopping} stopping`}
              />
            </div>
          </Card>

          <Card title="Recent Runs">
            {overview.recentRuns.length === 0 ? (
              <div className="p-8 text-center">
                <h3 className="text-lg font-semibold text-white">
                  No runs yet
                </h3>
                <p className="mt-2 text-sm text-text-muted">
                  Create a Test Plan or start a Debug Run from a Scenario to
                  generate the first report.
                </p>
                <div className="mt-5 flex justify-center gap-3">
                  <Link
                    className="rounded-xl border border-white/10 px-4 py-2 text-white"
                    to="/test-plans"
                  >
                    Open Test Plans
                  </Link>
                  <Link
                    className="rounded-xl border border-white/10 px-4 py-2 text-white"
                    to="/runs"
                  >
                    View Runs
                  </Link>
                </div>
              </div>
            ) : (
              <div className="overflow-hidden rounded-2xl border border-white/10">
                <div className="hidden grid-cols-[1.3fr_0.7fr_0.8fr_0.8fr_0.7fr] gap-3 border-b border-white/10 px-4 py-3 font-mono text-[11px] uppercase tracking-[0.16em] text-secondary md:grid">
                  <span>Source</span>
                  <span>Type</span>
                  <span>State</span>
                  <span>Validity / SLA</span>
                  <span>Duration</span>
                </div>
                {overview.recentRuns.map((run) => (
                  <RecentRunRow key={run.id} run={run} />
                ))}
              </div>
            )}
          </Card>

          <Card title="Resource Summary">
            <div className="grid gap-4 md:grid-cols-4">
              <Metric
                label="Visible Nodes"
                value={overview.resourceSummary.totalVisibleNodes}
              />
              <Metric
                label="Idle"
                value={overview.resourceSummary.byStatus.idle}
              />
              <Metric
                label="Busy"
                value={overview.resourceSummary.byStatus.busy}
              />
              <Metric
                label="Offline"
                value={overview.resourceSummary.byStatus.offline}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {Object.entries(overview.resourceSummary.byStatus).map(
                ([status, count]) => (
                  <StatusPill
                    key={status}
                    tone={
                      status === "idle"
                        ? "success"
                        : status === "busy"
                          ? "warning"
                          : status === "offline" || status === "quarantined"
                            ? "error"
                            : "neutral"
                    }
                  >
                    {formatEnum(status)} {numberText(count)}
                  </StatusPill>
                ),
              )}
            </div>
            {overview.resourceSummary.totalVisibleNodes === 0 ? (
              <div className="mt-5 rounded-2xl border border-white/10 bg-black/15 p-5 text-sm text-text-muted">
                No visible Load Nodes yet.{" "}
                <Link
                  className="font-semibold text-primary"
                  to="/resources/load-nodes/new"
                >
                  Register Load Node
                </Link>
              </div>
            ) : (
              <Link
                className="mt-5 inline-flex rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-white"
                to="/resources/load-nodes"
              >
                Manage Load Nodes
              </Link>
            )}
          </Card>

          <Card title="Quick Actions">
            <div className="grid gap-4 md:grid-cols-4">
              {quickActions.map(({ Icon, description, label, to }) => (
                <Link
                  className="rounded-2xl border border-white/10 bg-black/15 p-4 transition hover:border-primary/30 hover:bg-white/[0.06]"
                  key={label}
                  to={to}
                >
                  <Icon aria-hidden className="h-5 w-5 text-primary" />
                  <div className="mt-3 font-semibold text-white">{label}</div>
                  <p className="mt-1 text-xs leading-5 text-text-muted">
                    {description}
                  </p>
                </Link>
              ))}
            </div>
          </Card>
        </>
      ) : null}
    </div>
  );
}
