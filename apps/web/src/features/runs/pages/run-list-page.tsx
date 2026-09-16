import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { Eye, Square } from "lucide-react";

import {
  getCsrfToken,
  listRuns,
  stopRun,
  type RunListItem,
  type RunSourceType,
  type RunState,
  type RunType,
  type RunValidity,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { IconActionButton, IconActionLink } from "../../../components/icon-action";
import {
  activeRunStates,
  formatDate,
  formatDuration,
  formatEnum,
  StatusPill,
} from "./run-shared";

function useWriteToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function stateTone(state: string) {
  if (state === "finished") return "success" as const;
  if (state === "failed") return "error" as const;
  if (state === "aborted") return "warning" as const;
  return "primary" as const;
}

function RunRow({
  item,
  onStop,
}: {
  item: RunListItem;
  onStop: (item: RunListItem) => void;
}) {
  const nodeLabel =
    item.allocatedNodeCount > 1
      ? `${item.allocatedNodeCount} nodes`
      : "1 node";
  return (
    <div className="grid grid-cols-[minmax(0,1.3fr)_0.75fr_0.7fr_minmax(0,0.85fr)_0.65fr_0.65fr_minmax(0,1.05fr)_0.65fr] items-center gap-4 border-b border-white/5 px-5 py-4 text-sm last:border-b-0">
      <div className="min-w-0">
        <Link
          className="block truncate whitespace-nowrap font-semibold text-white hover:text-primary"
          to={`/runs/${item.id}`}
        >
          {item.sourceName ?? item.id}
        </Link>
        <p className="mt-1 truncate font-mono text-[11px] text-secondary">
          {item.id} · {nodeLabel}
        </p>
      </div>
      <div className="min-w-0">
        <StatusPill tone={stateTone(item.state)}>
          {formatEnum(item.state)}
        </StatusPill>
      </div>
      <span className="capitalize text-text-main">{item.validity}</span>
      <div className="min-w-0">
        {item.tags && item.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {item.tags.map((tag) => (
              <StatusPill key={tag}>{tag}</StatusPill>
            ))}
          </div>
        ) : (
          <span className="text-xs text-text-muted">No tags</span>
        )}
      </div>
      <span className="text-text-muted">{formatEnum(item.runType)}</span>
      <span className="text-text-muted">{formatDuration(item.durationMs)}</span>
      <span className="font-mono text-[11px] text-secondary">
        {formatDate(item.startedAt ?? item.createdAt)}
      </span>
      <div className="flex items-center justify-start gap-2">
        <IconActionLink
          Icon={Eye}
          label="View Report"
          to={`/runs/${item.id}`}
        />
        {activeRunStates.has(item.state) ? (
          <IconActionButton
            Icon={Square}
            label="Stop"
            onClick={() => onStop(item)}
            tone="danger"
          />
        ) : null}
      </div>
    </div>
  );
}

export function RunListPage() {
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const queryClient = useQueryClient();
  const getWriteToken = useWriteToken();
  const [state, setState] = useState<RunState | "">("");
  const [validity, setValidity] = useState<RunValidity | "">("");
  const [runType, setRunType] = useState<RunType | "">("");
  const [sourceType, setSourceType] = useState<RunSourceType | "">("");
  const [q, setQ] = useState("");
  const [recentOnly, setRecentOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = useInfiniteQuery({
    enabled: Boolean(workspaceId),
    initialPageParam: null as string | null,
    queryKey: [
      "runs",
      workspaceId,
      state,
      validity,
      runType,
      sourceType,
      q,
      recentOnly,
    ],
    queryFn: ({ pageParam }) =>
      listRuns({
        workspaceId,
        cursor: pageParam,
        state,
        validity,
        runType,
        sourceType,
        q,
        recentHours: recentOnly ? 24 : undefined,
      }),
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  });
  const stopMutation = useMutation({
    mutationFn: async (item: RunListItem) =>
      stopRun(item.id, workspaceId, await getWriteToken()),
    onSuccess: async () =>
      queryClient.invalidateQueries({ queryKey: ["runs", workspaceId] }),
    onError: () => setError("Unable to stop this run. Refresh and try again."),
  });
  const rows = query.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <section className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-white">
            Runs
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-text-muted">
            Review recent Debug and Standard Runs, then open a report for
            verdicts, final stats, snapshots, and artifacts.
          </p>
        </div>
      </div>
      {error ? (
        <div className="mb-4 rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
          {error}
        </div>
      ) : null}
      <div className="mb-4 grid gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3 md:grid-cols-6">
        <label className="grid gap-1 text-sm text-text-muted">
          Search
          <input
            aria-label="Search"
            className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
            placeholder="Run ID or source"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm text-text-muted">
          State
          <select
            aria-label="State"
            className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
            value={state}
            onChange={(event) => setState(event.target.value as RunState | "")}
          >
            <option value="">All states</option>
            <option value="initializing">Initializing</option>
            <option value="running">Running</option>
            <option value="stopping">Stopping</option>
            <option value="finished">Finished</option>
            <option value="failed">Failed</option>
            <option value="aborted">Aborted</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-text-muted">
          Validity
          <select
            aria-label="Validity"
            className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
            value={validity}
            onChange={(event) =>
              setValidity(event.target.value as RunValidity | "")
            }
          >
            <option value="">All validity</option>
            <option value="valid">Valid</option>
            <option value="invalid">Invalid</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-text-muted">
          Run Type
          <select
            aria-label="Run Type"
            className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
            value={runType}
            onChange={(event) => setRunType(event.target.value as RunType | "")}
          >
            <option value="">All types</option>
            <option value="debug">Debug</option>
            <option value="standard">Standard</option>
          </select>
        </label>
        <label className="grid gap-1 text-sm text-text-muted">
          Source Type
          <select
            aria-label="Source Type"
            className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
            value={sourceType}
            onChange={(event) =>
              setSourceType(event.target.value as RunSourceType | "")
            }
          >
            <option value="">All sources</option>
            <option value="debug_scenario">Debug Scenario</option>
            <option value="test_plan">Test Plan</option>
          </select>
        </label>
        <label className="flex items-end gap-2 pb-2 text-sm text-text-muted">
          <input
            checked={recentOnly}
            onChange={(event) => setRecentOnly(event.target.checked)}
            type="checkbox"
          />{" "}
          Recent 24 hours
        </label>
      </div>
      <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.045]">
        <div className="grid grid-cols-[minmax(0,1.3fr)_0.75fr_0.7fr_minmax(0,0.85fr)_0.65fr_0.65fr_minmax(0,1.05fr)_0.65fr] gap-4 border-b border-white/10 px-5 py-3 font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
          <span>Source</span>
          <span>State</span>
          <span>Validity</span>
          <span>Tags</span>
          <span>Type</span>
          <span>Duration</span>
          <span>Started</span>
          <span>Actions</span>
        </div>
        {query.isLoading ? (
          <div className="p-8 text-text-muted">Loading runs…</div>
        ) : null}
        {query.isError ? (
          <div className="p-8 text-error">Runs could not be loaded.</div>
        ) : null}
        {!query.isLoading && !query.isError && rows.length === 0 ? (
          <div className="p-10 text-center">
            <h2 className="text-xl font-semibold text-white">No runs yet</h2>
            <p className="mt-2 text-sm text-text-muted">
              Run a Test Plan or Debug Scenario to create the first report.
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
                to="/scenarios"
              >
                Open Scenarios
              </Link>
            </div>
          </div>
        ) : null}
        {rows.map((item) => (
          <RunRow
            item={item}
            key={item.id}
            onStop={(target) => stopMutation.mutate(target)}
          />
        ))}
      </div>
      {query.hasNextPage ? (
        <div className="mt-4 flex justify-center">
          <button
            className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={query.isFetchingNextPage}
            onClick={() => query.fetchNextPage()}
            type="button"
          >
            {query.isFetchingNextPage ? "Loading more…" : "Load more runs"}
          </button>
        </div>
      ) : null}
      <p className="mt-3 text-xs text-text-muted">
        Times are shown in your browser timezone. Use each report for immutable
        snapshot details.
      </p>
    </section>
  );
}
