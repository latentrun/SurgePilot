import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  cloneScenario,
  createScenario,
  deleteScenario,
  getCsrfToken,
  listScenarios,
  type ScenarioSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { scenarioCopy } from "../copy";
import { blankScenarioPayload } from "../model";

const pageSize = 20;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "RESOURCE_IN_USE") {
      return scenarioCopy.resourceInUse;
    }
    if (error.body.code === "WORKSPACE_ACCESS_DENIED") {
      return "You do not have access to this workspace.";
    }
    return "Action failed. Refresh and try again.";
  }
  return "Action failed. Refresh and try again.";
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function navigateTo(path: string) {
  window.history.replaceState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function cn(...inputs: (string | boolean | null | undefined)[]) {
  return inputs.filter(Boolean).join(" ");
}

function Search({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function Eye({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function Copy({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <rect height="14" rx="2" ry="2" width="14" x="8" y="8" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

function Archive({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <rect height="5" rx="1" width="20" x="2" y="3" />
      <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
      <path d="M10 12h4" />
    </svg>
  );
}

function RefreshCw({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  );
}

function ChevronLeft({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

function Plus({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M5 12h14M12 5v14" />
    </svg>
  );
}

export function ScenarioListPage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";

  const [q, setQ] = useState("");
  const [sort, setSort] = useState<
    "-updatedAt" | "updatedAt" | "name" | "-name"
  >("-updatedAt");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ScenarioSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [listError, setListError] = useState<unknown | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createBaseUrl, setCreateBaseUrl] = useState("${base_url}");
  const [createTags, setCreateTags] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const [archiveTarget, setArchiveTarget] = useState<ScenarioSummary | null>(
    null,
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [isArchiving, setIsArchiving] = useState(false);
  const [cloningId, setCloningId] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    if (!workspaceId) return;
    setIsFetching(true);
    try {
      const data = await listScenarios({
        workspaceId,
        page,
        pageSize,
        search: q.trim() || undefined,
        sort,
      });
      setItems(data.items);
      setTotal(data.total);
      setListError(null);
    } catch (err) {
      setListError(err);
    } finally {
      setIsLoading(false);
      setIsFetching(false);
    }
  }, [workspaceId, page, q, sort]);

  useEffect(() => {
    if (session !== null) {
      void fetchList();
    }
  }, [session, fetchList]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const canPageBackward = page > 1 && !isFetching;
  const canPageForward = page < totalPages && !isFetching;
  const isEmpty = !isLoading && !listError && items.length === 0;

  function updateSearch(value: string) {
    setQ(value);
    setPage(1);
  }

  function openCreate() {
    setCreateName("");
    setCreateBaseUrl("${base_url}");
    setCreateTags("");
    setCreateError(null);
    setCreateOpen(true);
  }

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = createName.trim();
    if (!name) {
      setCreateError("Scenario name is required.");
      return;
    }
    setIsCreating(true);
    setCreateError(null);
    try {
      const token = await getWriteToken();
      const scenario = await createScenario(
        {
          ...blankScenarioPayload(
            name,
            createBaseUrl.trim() || "${base_url}",
          ),
          tags: createTags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
        },
        workspaceId,
        token,
      );
      navigateTo(`/scenarios/${scenario.id}`);
    } catch (error) {
      setCreateError(errorMessage(error));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleClone(scenario: ScenarioSummary) {
    setCloningId(scenario.id);
    setActionError(null);
    try {
      const token = await getWriteToken();
      const cloned = await cloneScenario(
        scenario.id,
        {},
        workspaceId,
        token,
      );
      navigateTo(`/scenarios/${cloned.id}`);
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setCloningId(null);
    }
  }

  async function handleArchive() {
    if (!archiveTarget) return;
    setIsArchiving(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      await deleteScenario(archiveTarget.id, workspaceId, token);
      if (items.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      }
      setArchiveTarget(null);
      await fetchList();
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setIsArchiving(false);
    }
  }

  if (session === null) {
    return null;
  }

  return (
    <div className="mx-auto flex max-w-container-max flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-[34px] font-semibold leading-10 text-white">
            {scenarioCopy.title}
          </h1>
          <p className="mt-2 max-w-3xl text-base leading-6 text-text-muted">
            Define the request flows you want to test and run low-risk Debug
            Runs against them.
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={openCreate}
          type="button"
        >
          <Plus className="h-4 w-4" />
          {scenarioCopy.createButton}
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block w-full max-w-md">
          <span className="sr-only">Search Scenarios</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary" />
          <input
            className="h-11 w-full rounded-lg border border-white/10 bg-surface-container-low px-10 text-sm text-text-main outline-none transition placeholder:text-secondary focus:border-primary/50"
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="Search by name..."
            value={q}
          />
        </label>
        <label className="flex items-center gap-2 font-mono text-[12px] uppercase tracking-wide text-secondary">
          Sort
          <select
            aria-label="Sort scenarios"
            className="h-10 rounded-lg border border-white/10 bg-surface-container-low px-3 font-mono text-[12px] normal-case tracking-normal text-text-main outline-none"
            onChange={(event) => {
              setSort(event.target.value as typeof sort);
              setPage(1);
            }}
            value={sort}
          >
            <option value="-updatedAt">Recently updated</option>
            <option value="updatedAt">Oldest updated</option>
            <option value="name">Name A-Z</option>
            <option value="-name">Name Z-A</option>
          </select>
        </label>
      </div>

      {listError ? (
        <div className="flex items-center justify-between gap-4 rounded-xl border border-error/30 bg-error-container p-4">
          <p className="text-sm text-on-error-container">
            {errorMessage(listError)}
          </p>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main"
            onClick={() => void fetchList()}
            type="button"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      ) : null}

      {actionError && !archiveTarget ? (
        <div className="rounded-xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
          {actionError}
        </div>
      ) : null}

      <section className="surgepilot-glass overflow-hidden rounded-xl">
        {isLoading ? (
          <div className="p-8 text-sm text-text-muted">
            Loading Scenarios...
          </div>
        ) : null}
        {isEmpty ? (
          <div className="mx-auto flex max-w-md flex-col items-center p-10 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-lg border border-primary/20 bg-primary-container/10 font-mono text-sm font-bold text-primary">
              RUN
            </div>
            <h2 className="mt-5 text-lg font-semibold leading-7 text-white">
              {scenarioCopy.emptyTitle}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              {scenarioCopy.emptyDescription}
            </p>
            <button
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110"
              onClick={openCreate}
              type="button"
            >
              <Plus className="h-4 w-4" />
              {scenarioCopy.createButton}
            </button>
          </div>
        ) : null}
        {!isLoading && items.length > 0 ? (
          <>
            <table className="w-full border-collapse text-left">
              <thead className="border-b border-white/10 bg-white/5">
                <tr>
                  {[
                    "Name",
                    "Tags",
                    "Steps",
                    "Data files",
                    "Revision",
                    "Updated at",
                    "Actions",
                  ].map((heading) => (
                    <th
                      className="px-5 py-4 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-secondary"
                      key={heading}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {items.map((scenario) => (
                  <tr
                    className="transition hover:bg-white/[0.03]"
                    key={scenario.id}
                  >
                    <td className="px-5 py-4">
                      <a
                        className="font-semibold text-white transition hover:text-primary"
                        href={`/scenarios/${scenario.id}`}
                      >
                        {scenario.name}
                      </a>
                    </td>
                    <td className="px-5 py-4">
                      {scenario.tags.length > 0 ? (
                        <div className="flex max-w-xs flex-wrap gap-1">
                          {scenario.tags.map((tag) => (
                            <span
                              className="rounded-full border border-primary/20 bg-primary-container/10 px-2 py-0.5 font-mono text-xs text-primary"
                              key={tag}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-text-muted">
                          {scenarioCopy.noTags}
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-text-main">
                      {scenario.enabledStepCount}/{scenario.stepCount}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-text-main">
                      {scenario.dependencyFileCount}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-text-muted">
                      {scenario.revision}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-text-muted">
                      {formatDate(scenario.updatedAt)}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <a
                          aria-label={`Open ${scenario.name}`}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white"
                          href={`/scenarios/${scenario.id}`}
                          title="Open"
                        >
                          <Eye className="h-4 w-4" />
                        </a>
                        <button
                          aria-label={`${scenarioCopy.clone} ${scenario.name}`}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                          disabled={cloningId === scenario.id}
                          onClick={() => void handleClone(scenario)}
                          title={scenarioCopy.clone}
                          type="button"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                        <button
                          aria-label={`${scenarioCopy.archive} ${scenario.name}`}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-error/30 hover:bg-white/5 hover:text-error"
                          onClick={() => setArchiveTarget(scenario)}
                          title={scenarioCopy.archive}
                          type="button"
                        >
                          <Archive className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
              <div className="font-mono text-[12px] uppercase tracking-wide text-secondary">
                Page <span className="text-text-main">{page}</span> of{" "}
                <span className="text-text-main">{totalPages}</span>
              </div>
              <div className="flex gap-2">
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!canPageBackward}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  type="button"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous page
                </button>
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!canPageForward}
                  onClick={() => setPage((current) => current + 1)}
                  type="button"
                >
                  Next page
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      {createOpen ? (
        <div
          aria-label={scenarioCopy.createTitle}
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          role="dialog"
        >
          <form
            className="w-full max-w-lg rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
            onSubmit={(event) => void handleCreate(event)}
          >
            <h2 className="text-xl font-semibold text-white">
              {scenarioCopy.createTitle}
            </h2>
            {createError ? (
              <p className="mt-4 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                {createError}
              </p>
            ) : null}
            <label className="mt-5 grid gap-1 text-sm text-text-muted">
              Scenario name
              <input
                autoFocus
                className="h-10 w-full rounded-lg border border-white/10 bg-surface-container px-3 text-sm text-text-main outline-none transition focus:border-primary/50"
                onChange={(event) => setCreateName(event.target.value)}
                value={createName}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Base URL expression
              <input
                className="h-10 w-full rounded-lg border border-white/10 bg-surface-container px-3 font-mono text-sm text-text-main outline-none transition focus:border-primary/50"
                onChange={(event) => setCreateBaseUrl(event.target.value)}
                placeholder="${base_url}"
                value={createBaseUrl}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Tags
              <input
                className="h-10 w-full rounded-lg border border-white/10 bg-surface-container px-3 font-mono text-sm text-text-main outline-none transition focus:border-primary/50"
                onChange={(event) => setCreateTags(event.target.value)}
                placeholder="checkout, smoke"
                value={createTags}
              />
            </label>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
                onClick={() => setCreateOpen(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!createName.trim() || isCreating}
                type="submit"
              >
                {isCreating ? "Creating..." : "Create"}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {archiveTarget ? (
        <div
          aria-label={scenarioCopy.archiveTitle}
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          role="dialog"
        >
          <div className="w-[min(440px,calc(100vw-32px))] rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <h2 className="text-lg font-semibold text-white">
              {scenarioCopy.archiveTitle}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Archive {archiveTarget.name}? {scenarioCopy.archiveBody}
            </p>
            {actionError ? (
              <p className="mt-4 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                {actionError}
              </p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <button
                className={cn(
                  "rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5",
                )}
                onClick={() => {
                  setArchiveTarget(null);
                  setActionError(null);
                }}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-lg bg-error-container px-4 py-2 text-sm font-semibold text-on-error-container transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isArchiving}
                onClick={() => void handleArchive()}
                type="button"
              >
                {isArchiving ? "Archiving..." : scenarioCopy.archive}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
