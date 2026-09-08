import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getOverview,
  type OverviewRecentRun,
  type OverviewResponse,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import {
  formatDuration,
  formatEnum,
  formatNumber,
  SectionCard,
  StatusPill,
} from "../../runs/pages/run-shared";

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return `Overview could not be loaded. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Overview could not be loaded. Refresh and try again.";
}

function runStateTone(state: string) {
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

function loadNodeStatusTone(status: string) {
  if (status === "idle") return "success" as const;
  if (status === "busy") return "warning" as const;
  if (status === "offline" || status === "quarantined") return "error" as const;
  return "neutral" as const;
}

function Metric({
  label,
  note,
  value,
}: Readonly<{ label: string; note?: string; value: number | string }>) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {typeof value === "number" ? formatNumber(value) : value}
        {note ? <small>{note}</small> : null}
      </dd>
    </div>
  );
}

function RecentRunRow({ run }: Readonly<{ run: OverviewRecentRun }>) {
  return (
    <li>
      <a href={`/runs/${run.id}`}>
        <span>
          <strong>{run.sourceName ?? run.id}</strong>
          <small>{run.id}</small>
        </span>
        <StatusPill tone={run.runType === "debug" ? "warning" : "primary"}>
          {formatEnum(run.runType)}
        </StatusPill>
        <StatusPill tone={runStateTone(run.state)}>
          {formatEnum(run.state)}
        </StatusPill>
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
        <span>{formatDuration(run.durationMs)}</span>
      </a>
    </li>
  );
}

const quickActions = [
  {
    description: "Design request flow steps.",
    href: "/scenarios",
    label: "Create Scenario",
  },
  {
    description: "Configure load and SLA rules.",
    href: "/test-plans",
    label: "Create Test Plan",
  },
  {
    description: "Open recent reports and artifacts.",
    href: "/runs",
    label: "View Runs",
  },
  {
    description: "Register or check runner nodes.",
    href: "/resources/load-nodes",
    label: "Manage Load Nodes",
  },
];

export function OverviewPage() {
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(
    async (refreshing: boolean) => {
      if (!workspaceId) return;
      if (refreshing) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }
      setLoadError(null);
      try {
        const data = await getOverview({ recentLimit: 5, workspaceId });
        setOverview(data);
      } catch (error) {
        setLoadError(errorMessage(error));
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    if (workspaceId) {
      void load(false);
    }
  }, [load, workspaceId]);

  if (session === null) {
    return null;
  }

  const windowDays = overview?.statsScope.windowDays ?? 30;
  const activeRuns = overview?.runStats.activeRuns;

  return (
    <main>
      <section>
        <p>
          Default Workspace · Last {formatNumber(windowDays)} days
        </p>
        <h1>Overview</h1>
        <p>
          Current execution activity, Valid Standard Run results, and visible
          Load Node status for{" "}
          {overview?.workspace.name ?? session.defaultWorkspace.name}.
        </p>
        <p>
          Signed in as <strong>{session.user.displayName}</strong>
        </p>
        {isRefreshing && overview ? <p role="status">Refreshing…</p> : null}
      </section>

      {isLoading ? (
        <section aria-label="Loading overview" role="status">
          Loading overview…
        </section>
      ) : null}

      {loadError ? (
        <section role="alert">
          <h2>Unable to load Overview</h2>
          <p>{loadError}</p>
          <button onClick={() => void load(overview !== null)} type="button">
            Try again
          </button>
        </section>
      ) : null}

      {overview ? (
        <>
          <SectionCard title="Run Summary">
            <p>
              Result statistics include Valid Standard terminal Runs only.
              Active activity is counted separately.
            </p>
            <dl>
              <Metric
                label="Valid Standard Runs"
                note="Terminal runs in this window"
                value={overview.runStats.resultRuns.total}
              />
              <Metric
                label="Finished"
                value={overview.runStats.resultRuns.byState.finished}
              />
              <Metric
                label="Failed State"
                note="Process failed, not SLA failed"
                value={overview.runStats.resultRuns.byState.failed}
              />
              <Metric
                label="Aborted"
                value={overview.runStats.resultRuns.byState.aborted}
              />
              <Metric
                label="SLA Passed"
                value={overview.runStats.resultRuns.bySlaResult.passed}
              />
              <Metric
                label="SLA Failed"
                note="SLA result only"
                value={overview.runStats.resultRuns.bySlaResult.failed}
              />
              <Metric
                label="Not Evaluated"
                value={overview.runStats.resultRuns.bySlaResult.notEvaluated}
              />
              <Metric
                label="Active Runs"
                note={
                  activeRuns
                    ? `${formatNumber(activeRuns.initializing)} initializing · ${formatNumber(activeRuns.running)} running · ${formatNumber(activeRuns.stopping)} stopping`
                    : undefined
                }
                value={formatNumber(activeRuns?.total)}
              />
            </dl>
          </SectionCard>

          <SectionCard title="Recent Runs">
            {overview.recentRuns.length === 0 ? (
              <div>
                <h3>No runs yet</h3>
                <p>
                  Create a Test Plan or start a Debug Run from a Scenario to
                  generate the first report.
                </p>
                <div>
                  <a href="/test-plans">Open Test Plans</a>
                  <a href="/runs">View Runs</a>
                </div>
              </div>
            ) : (
              <>
                <div>
                  {["Source", "Type", "State", "Validity / SLA", "Duration"].map(
                    (heading) => (
                      <span key={heading}>{heading}</span>
                    ),
                  )}
                </div>
                <ul>
                  {overview.recentRuns.map((run) => (
                    <RecentRunRow key={run.id} run={run} />
                  ))}
                </ul>
              </>
            )}
          </SectionCard>

          <SectionCard title="Resource Summary">
            <dl>
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
            </dl>
            <div>
              {Object.entries(overview.resourceSummary.byStatus).map(
                ([status, count]) => (
                  <StatusPill
                    key={status}
                    tone={loadNodeStatusTone(status)}
                  >
                    {formatEnum(status)} {formatNumber(count)}
                  </StatusPill>
                ),
              )}
            </div>
            {overview.resourceSummary.totalVisibleNodes === 0 ? (
              <div>
                <p>
                  No visible Load Nodes yet.{" "}
                  <a href="/resources/load-nodes/new">Register Load Node</a>
                </p>
              </div>
            ) : (
              <a href="/resources/load-nodes">Manage Load Nodes</a>
            )}
          </SectionCard>

          <SectionCard title="Quick Actions">
            <ul>
              {quickActions.map(({ description, href, label }) => (
                <li key={label}>
                  <a href={href}>
                    <strong>{label}</strong>
                    <small>{description}</small>
                  </a>
                </li>
              ))}
            </ul>
          </SectionCard>
        </>
      ) : null}
    </main>
  );
}
