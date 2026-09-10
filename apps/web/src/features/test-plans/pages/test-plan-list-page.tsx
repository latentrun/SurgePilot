import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  cloneTestPlan,
  createRun,
  createTestPlan,
  deleteTestPlan,
  getCsrfToken,
  listTestPlans,
  type TestPlanSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { testPlanCopy } from "../copy";
import { blankTestPlanPayload, tagsFromText } from "../model";

const pageSize = 100;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function apiMessage(error: unknown) {
  const code = (error as ApiError | undefined)?.body?.code;
  if (code === "RESOURCE_IN_USE") return testPlanCopy.resourceInUse;
  if (code === "LOAD_NODE_BUSY") return testPlanCopy.nodeBusy;
  if (code === "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED")
    return testPlanCopy.highConcurrencyFromList;
  return testPlanCopy.actionFailed;
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

function PlayCircle({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" />
      <path d="m10 8 6 4-6 4Z" />
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

function X({ className }: { className?: string }) {
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
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

export function TestPlanListPage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";

  const [q, setQ] = useState("");
  const [sort, setSort] = useState<
    "-updatedAt" | "updatedAt" | "name" | "-name"
  >("-updatedAt");
  const [items, setItems] = useState<TestPlanSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [listError, setListError] = useState<unknown | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createTags, setCreateTags] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const [archiveTarget, setArchiveTarget] = useState<TestPlanSummary | null>(
    null,
  );
  const [isArchiving, setIsArchiving] = useState(false);
  const [cloningId, setCloningId] = useState<string | null>(null);

  const [quickRunId, setQuickRunId] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    if (!workspaceId) return;
    setIsFetching(true);
    try {
      const data = await listTestPlans({
        workspaceId,
        page: 1,
        pageSize,
        search: q.trim() || undefined,
        sort,
      });
      setItems(data.items);
      setListError(null);
    } catch (err) {
      setListError(err);
    } finally {
      setIsLoading(false);
      setIsFetching(false);
    }
  }, [workspaceId, q, sort]);

  useEffect(() => {
    if (session !== null) {
      void fetchList();
    }
  }, [session, fetchList]);

  const isEmpty = !isLoading && !listError && items.length === 0;

  function updateSearch(value: string) {
    setQ(value);
  }

  function openCreate() {
    setCreateName("");
    setCreateDescription("");
    setCreateTags("");
    setError(null);
    setCreateOpen(true);
  }

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = createName.trim();
    if (!name) {
      setError("Test Plan name is required.");
      return;
    }
    setIsCreating(true);
    setError(null);
    try {
      const token = await getWriteToken();
      const plan = await createTestPlan(
        blankTestPlanPayload(
          name,
          createDescription.trim() || null,
          tagsFromText(createTags),
        ),
        workspaceId,
        token,
      );
      navigateTo(`/test-plans/${plan.id}`);
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleClone(plan: TestPlanSummary) {
    setCloningId(plan.id);
    setError(null);
    try {
      const token = await getWriteToken();
      const cloned = await cloneTestPlan(plan.id, {}, workspaceId, token);
      navigateTo(`/test-plans/${cloned.id}`);
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setCloningId(null);
    }
  }

  async function handleArchive() {
    if (!archiveTarget) return;
    setIsArchiving(true);
    setError(null);
    try {
      const token = await getWriteToken();
      await deleteTestPlan(archiveTarget.id, workspaceId, token);
      setArchiveTarget(null);
      await fetchList();
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setIsArchiving(false);
    }
  }

  async function handleQuickRun(plan: TestPlanSummary) {
    if (!plan.runnable || plan.requiresHighConcurrencyConfirmation) {
      navigateTo(`/test-plans/${plan.id}`);
      return;
    }
    setQuickRunId(plan.id);
    setError(null);
    try {
      const token = await getWriteToken();
      const run = await createRun(
        {
          runType: "standard",
          sourceType: "test_plan",
          sourceId: plan.id,
          expectedSourceRevision: plan.revision,
          confirmHighConcurrency: false,
        },
        workspaceId,
        token,
      );
      navigateTo(`/runs/${run.id}`);
    } catch (err) {
      setError(apiMessage(err));
    } finally {
      setQuickRunId(null);
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
            {testPlanCopy.title}
          </h1>
          <p className="mt-2 max-w-3xl text-base leading-6 text-text-muted">
            {testPlanCopy.subtitle}
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={openCreate}
          type="button"
        >
          <Plus className="h-4 w-4" />
          {testPlanCopy.createButton}
        </button>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative block w-full max-w-md">
          <span className="sr-only">{testPlanCopy.searchLabel}</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary" />
          <input
            aria-label={testPlanCopy.searchLabel}
            className="h-11 w-full rounded-lg border border-white/10 bg-surface-container-low px-10 text-sm text-text-main outline-none transition placeholder:text-secondary focus:border-primary/50"
            onChange={(event) => updateSearch(event.target.value)}
            placeholder={testPlanCopy.searchPlaceholder}
            value={q}
          />
        </label>
        <label className="flex items-center gap-2 font-mono text-[12px] uppercase tracking-wide text-secondary">
          {testPlanCopy.sortLabel}
          <select
            aria-label={testPlanCopy.sortLabel}
            className="h-10 rounded-lg border border-white/10 bg-surface-container-low px-3 font-mono text-[12px] normal-case tracking-normal text-text-main outline-none"
            onChange={(event) => setSort(event.target.value as typeof sort)}
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
            {apiMessage(listError)}
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
      {error && !listError && !createOpen && !archiveTarget ? (
        <div className="rounded-xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
          {error}
        </div>
      ) : null}

      <section className="surgepilot-glass overflow-hidden rounded-xl">
        {isLoading ? (
          <div className="p-8 text-sm text-text-muted">
            {testPlanCopy.loadingList}
          </div>
        ) : null}
        {isEmpty ? (
          <div className="mx-auto flex max-w-md flex-col items-center p-10 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-lg border border-primary/20 bg-primary-container/10 font-mono text-sm font-bold text-primary">
              TP
            </div>
            <h2 className="mt-5 text-lg font-semibold leading-7 text-white">
              {testPlanCopy.emptyTitle}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              {testPlanCopy.emptyDescription}
            </p>
            <button
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110"
              onClick={openCreate}
              type="button"
            >
              <Plus className="h-4 w-4" />
              {testPlanCopy.createButton}
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
                    "Mode",
                    "Scenarios",
                    "Concurrency",
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
                {items.map((item) => {
                  const quickRunDisabled =
                    !item.runnable || item.requiresHighConcurrencyConfirmation;
                  return (
                    <tr
                      className="transition hover:bg-white/[0.03]"
                      key={item.id}
                    >
                      <td className="px-5 py-4">
                        <a
                          className="font-semibold text-white transition hover:text-primary"
                          href={`/test-plans/${item.id}`}
                        >
                          {item.name}
                        </a>
                        {item.tags.length > 0 ? (
                          <div className="mt-1 flex max-w-xs flex-wrap gap-1">
                            {item.tags.map((tag) => (
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
                            {testPlanCopy.noTags}
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-sm capitalize text-text-main">
                        {item.runMode}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-text-main">
                        {item.enabledScenarioItemCount}/{item.scenarioItemCount}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-text-main">
                        {item.expectedConcurrencyPerNode}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-text-muted">
                        {formatDate(item.updatedAt)}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-2">
                          <a
                            aria-label={`Open ${item.name}`}
                            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white"
                            href={`/test-plans/${item.id}`}
                            title={testPlanCopy.open}
                          >
                            <Eye className="h-4 w-4" />
                          </a>
                          <button
                            aria-label={`${testPlanCopy.quickRun} ${item.name}`}
                            className={cn(
                              "inline-flex h-9 items-center justify-center gap-1 rounded-lg border border-white/10 px-2 text-xs text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-40",
                            )}
                            disabled={quickRunDisabled || isFetching}
                            onClick={() => void handleQuickRun(item)}
                            title={
                              quickRunDisabled
                                ? item.requiresHighConcurrencyConfirmation
                                  ? testPlanCopy.highConcurrencyFromList
                                  : testPlanCopy.notRunnable
                                : testPlanCopy.quickRun
                            }
                            type="button"
                          >
                            {quickRunId === item.id ? (
                              <RefreshCw className="h-4 w-4 animate-spin" />
                            ) : (
                              <PlayCircle className="h-4 w-4" />
                            )}
                          </button>
                          <button
                            aria-label={`${testPlanCopy.clone} ${item.name}`}
                            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                            disabled={cloningId === item.id}
                            onClick={() => void handleClone(item)}
                            title={testPlanCopy.clone}
                            type="button"
                          >
                            <Copy className="h-4 w-4" />
                          </button>
                          <button
                            aria-label={`${testPlanCopy.archive} ${item.name}`}
                            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-error/30 hover:bg-white/5 hover:text-error"
                            onClick={() => setArchiveTarget(item)}
                            title={testPlanCopy.archive}
                            type="button"
                          >
                            <Archive className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        ) : null}
      </section>

      {createOpen ? (
        <div
          aria-label={testPlanCopy.createTitle}
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          role="dialog"
        >
          <form
            className="w-full max-w-lg rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
            onSubmit={(event) => void handleCreate(event)}
          >
            <h2 className="text-xl font-semibold text-white">
              {testPlanCopy.createTitle}
            </h2>
            {error && createOpen ? (
              <p className="mt-4 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                {error}
              </p>
            ) : null}
            <label className="mt-5 grid gap-1 text-sm text-text-muted">
              Test Plan name
              <input
                autoFocus
                className="h-10 w-full rounded-lg border border-white/10 bg-surface-container px-3 text-sm text-text-main outline-none transition focus:border-primary/50"
                onChange={(event) => setCreateName(event.target.value)}
                value={createName}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Description
              <textarea
                className="min-h-20 w-full resize-y rounded-lg border border-white/10 bg-surface-container px-3 py-2 text-sm text-text-main outline-none transition focus:border-primary/50"
                onChange={(event) => setCreateDescription(event.target.value)}
                value={createDescription}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Tags
              <input
                className="h-10 w-full rounded-lg border border-white/10 bg-surface-container px-3 font-mono text-sm text-text-main outline-none transition focus:border-primary/50"
                onChange={(event) => setCreateTags(event.target.value)}
                placeholder={testPlanCopy.tagsPlaceholder}
                value={createTags}
              />
            </label>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
                onClick={() => {
                  setCreateOpen(false);
                  setError(null);
                }}
                type="button"
              >
                {testPlanCopy.cancel}
              </button>
              <button
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={!createName.trim() || isCreating}
                type="submit"
              >
                {isCreating ? "Creating..." : testPlanCopy.create}
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {archiveTarget ? (
        <div
          aria-label={testPlanCopy.archiveTitle}
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          role="dialog"
        >
          <div className="w-[min(440px,calc(100vw-32px))] rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold text-white">
                {testPlanCopy.archiveTitle}
              </h2>
              <button
                className="rounded-lg p-2 text-text-muted transition hover:bg-white/5 hover:text-white"
                onClick={() => setArchiveTarget(null)}
                type="button"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Archive {archiveTarget.name}? {testPlanCopy.archiveBody}
            </p>
            {error && archiveTarget ? (
              <p className="mt-4 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                {error}
              </p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
                onClick={() => {
                  setArchiveTarget(null);
                  setError(null);
                }}
                type="button"
              >
                {testPlanCopy.cancel}
              </button>
              <button
                className="rounded-lg bg-error-container px-4 py-2 text-sm font-semibold text-on-error-container transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isArchiving}
                onClick={() => void handleArchive()}
                type="button"
              >
                {isArchiving ? "Archiving..." : testPlanCopy.archive}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
