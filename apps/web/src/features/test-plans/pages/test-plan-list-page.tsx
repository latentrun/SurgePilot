import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Archive, Copy, Eye, PlayCircle } from "lucide-react";
import {
  cloneTestPlan,
  createRun,
  createTestPlan,
  deleteTestPlan,
  getCsrfToken,
  listTestPlans,
  type ApiError,
  type TestPlanSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { IconActionButton, IconActionLink } from "../../../components/icon-action";
import { blankTestPlanPayload, tagsFromText } from "../model";
import { testPlanCopy } from "../copy";

function useWriteToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function apiMessage(error: unknown) {
  const code = (error as ApiError | undefined)?.body?.code;
  if (code === "RESOURCE_IN_USE") return testPlanCopy.resourceInUse;
  if (code === "LOAD_NODE_BUSY") return testPlanCopy.nodeBusy;
  if (code === "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED")
    return testPlanCopy.highConcurrencyFromList;
  return testPlanCopy.actionFailed;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function StatusPill({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-primary/20 px-2 py-0.5 font-mono text-[11px] text-primary">
      {children}
    </span>
  );
}

export function TestPlanListPage() {
  const { session } = useAuthSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const getWriteToken = useWriteToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<
    "-updatedAt" | "updatedAt" | "name" | "-name"
  >("-updatedAt");
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createTags, setCreateTags] = useState("");
  const [archiveTarget, setArchiveTarget] = useState<TestPlanSummary | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const query = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["test-plans", workspaceId, search, sort],
    queryFn: () => listTestPlans({ workspaceId, search, sort }),
  });
  const createMutation = useMutation({
    mutationFn: async () =>
      createTestPlan(
        blankTestPlanPayload(
          createName.trim(),
          createDescription.trim() || null,
          tagsFromText(createTags),
        ),
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (plan) => navigate(`/test-plans/${plan.id}`),
    onError: (err) => setError(apiMessage(err)),
  });
  const cloneMutation = useMutation({
    mutationFn: async (plan: TestPlanSummary) =>
      cloneTestPlan(plan.id, {}, workspaceId, await getWriteToken()),
    onSuccess: (plan) => navigate(`/test-plans/${plan.id}`),
    onError: (err) => setError(apiMessage(err)),
  });
  const archiveMutation = useMutation({
    mutationFn: async (plan: TestPlanSummary) =>
      deleteTestPlan(plan.id, workspaceId, await getWriteToken()),
    onSuccess: async () => {
      setArchiveTarget(null);
      await queryClient.invalidateQueries({
        queryKey: ["test-plans", workspaceId],
      });
    },
    onError: (err) => setError(apiMessage(err)),
  });
  const quickRunMutation = useMutation({
    mutationFn: async (plan: TestPlanSummary) =>
      createRun(
        {
          runType: "standard",
          sourceType: "test_plan",
          sourceId: plan.id,
          expectedSourceRevision: plan.revision,
          confirmHighConcurrency: false,
        },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (run) => navigate(`/runs/${run.id}`),
    onError: (err) => setError(apiMessage(err)),
  });
  const rows = query.data?.items ?? [];
  return (
    <section className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-white">
            {testPlanCopy.title}
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-text-muted">
            {testPlanCopy.subtitle}
          </p>
        </div>
        <button
          className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary disabled:opacity-50"
          onClick={() => setShowCreate(true)}
          type="button"
        >
          {testPlanCopy.createButton}
        </button>
      </div>
      {error ? (
        <div className="mb-4 rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
          {error}
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3">
        <input
          aria-label={testPlanCopy.searchLabel}
          className="min-w-[220px] flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
          placeholder={testPlanCopy.searchPlaceholder}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          aria-label={testPlanCopy.sortLabel}
          className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
          value={sort}
          onChange={(event) => setSort(event.target.value as typeof sort)}
        >
          <option value="-updatedAt">Recently updated</option>
          <option value="updatedAt">Oldest updated</option>
          <option value="name">Name A-Z</option>
          <option value="-name">Name Z-A</option>
        </select>
      </div>
      <div
        className="overflow-x-auto rounded-3xl border border-white/10 bg-white/[0.045]"
        data-testid="test-plan-list-grid"
      >
        <div className="grid min-w-[900px] grid-cols-[1.4fr_0.7fr_0.8fr_0.8fr_1.1fr_1fr] gap-4 border-b border-white/10 px-5 py-3 font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
          <span>Name</span>
          <span>Mode</span>
          <span>Scenarios</span>
          <span>Concurrency</span>
          <span>Updated</span>
          <span>Actions</span>
        </div>
        {query.isLoading ? (
          <div className="p-8 text-text-muted">{testPlanCopy.loadingList}</div>
        ) : null}
        {query.isError ? (
          <div className="p-8 text-error">{testPlanCopy.listLoadError}</div>
        ) : null}
        {!query.isLoading && !query.isError && rows.length === 0 ? (
          <div className="p-10 text-center">
            <h2 className="text-xl font-semibold text-white">
              {testPlanCopy.emptyTitle}
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              {testPlanCopy.emptyDescription}
            </p>
            <button
              className="mt-5 rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary"
              onClick={() => setShowCreate(true)}
              type="button"
            >
              {testPlanCopy.createButton}
            </button>
          </div>
        ) : null}
        {rows.map((item) => (
          <div
            className="grid min-w-[900px] grid-cols-[1.4fr_0.7fr_0.8fr_0.8fr_1.1fr_1fr] items-center gap-4 border-b border-white/5 px-5 py-4 text-sm last:border-b-0"
            key={item.id}
          >
            <div className="min-w-0">
              <Link
                className="font-semibold text-white hover:text-primary"
                to={`/test-plans/${item.id}`}
              >
                {item.name}
              </Link>
              <div className="mt-1 flex flex-wrap gap-1">
                {item.tags.length > 0 ? (
                  item.tags.map((tag) => <StatusPill key={tag}>{tag}</StatusPill>)
                ) : (
                  <span className="text-xs text-text-muted">
                    {testPlanCopy.noTags}
                  </span>
                )}
              </div>
            </div>
            <span className="capitalize">{item.runMode}</span>
            <span>
              {item.enabledScenarioItemCount}/{item.scenarioItemCount}
            </span>
            <span className="font-mono text-xs">
              {item.expectedConcurrencyPerNode}
            </span>
            <span className="text-text-muted">{formatDate(item.updatedAt)}</span>
            <div className="flex flex-wrap gap-2">
              <IconActionLink
                Icon={Eye}
                label={testPlanCopy.open}
                to={`/test-plans/${item.id}`}
              />
              <IconActionButton
                Icon={PlayCircle}
                disabled={
                  !item.runnable || item.requiresHighConcurrencyConfirmation
                }
                label={testPlanCopy.quickRun}
                onClick={() => quickRunMutation.mutate(item)}
              />
              <IconActionButton
                Icon={Copy}
                label={testPlanCopy.clone}
                onClick={() => cloneMutation.mutate(item)}
              />
              <IconActionButton
                Icon={Archive}
                label={testPlanCopy.archive}
                onClick={() => setArchiveTarget(item)}
                tone="danger"
              />
            </div>
          </div>
        ))}
      </div>
      {showCreate ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <form
            className="w-full max-w-lg rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
            onSubmit={(event) => {
              event.preventDefault();
              createMutation.mutate();
            }}
          >
            <h2 className="text-xl font-semibold text-white">
              {testPlanCopy.createTitle}
            </h2>
            <label className="mt-5 grid gap-1 text-sm text-text-muted">
              Test Plan name
              <input
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Description
              <textarea
                className="min-h-20 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                value={createDescription}
                onChange={(event) => setCreateDescription(event.target.value)}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Tags
              <input
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                placeholder={testPlanCopy.tagsPlaceholder}
                value={createTags}
                onChange={(event) => setCreateTags(event.target.value)}
              />
            </label>
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-white"
                onClick={() => setShowCreate(false)}
                type="button"
              >
                {testPlanCopy.cancel}
              </button>
              <button
                className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary disabled:opacity-50"
                disabled={!createName.trim() || createMutation.isPending}
                type="submit"
              >
                {testPlanCopy.create}
              </button>
            </div>
          </form>
        </div>
      ) : null}
      {archiveTarget ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div
            role="dialog"
            aria-label={testPlanCopy.archiveTitle}
            className="w-full max-w-md rounded-3xl border border-error/30 bg-surface-container-low p-6 shadow-2xl"
          >
            <h2 className="text-xl font-semibold text-white">
              {testPlanCopy.archiveTitle}
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              {testPlanCopy.archiveBody}
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-white"
                onClick={() => setArchiveTarget(null)}
                type="button"
              >
                {testPlanCopy.cancel}
              </button>
              <button
                className="rounded-xl bg-error px-4 py-2 font-semibold text-on-error"
                onClick={() => archiveMutation.mutate(archiveTarget)}
                type="button"
              >
                {testPlanCopy.archive}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
