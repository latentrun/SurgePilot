import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Archive, Copy, Eye } from "lucide-react";
import {
  cloneScenario,
  createScenario,
  deleteScenario,
  getCsrfToken,
  listScenarios,
  type ApiError,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { IconActionButton, IconActionLink } from "../../../components/icon-action";
import { scenarioCopy } from "../copy";
import { blankScenarioPayload } from "../model";

function useWriteToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}
function apiMessage(error: unknown) {
  return (error as ApiError | undefined)?.body?.code === "RESOURCE_IN_USE"
    ? scenarioCopy.resourceInUse
    : "Action failed. Refresh and try again.";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ScenarioListPage() {
  const { session } = useAuthSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const getWriteToken = useWriteToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<
    "-updatedAt" | "updatedAt" | "name" | "-name"
  >("-updatedAt");
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createBaseUrl, setCreateBaseUrl] = useState("${base_url}");
  const [createTags, setCreateTags] = useState("");
  const [archiveTarget, setArchiveTarget] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const query = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["scenarios", workspaceId, q, sort],
    queryFn: () => listScenarios({ workspaceId, search: q, sort }),
  });
  const createMutation = useMutation({
    mutationFn: async () =>
      createScenario(
        {
          ...blankScenarioPayload(
            createName.trim(),
            createBaseUrl.trim() || "${base_url}",
          ),
          tags: createTags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
        },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (scenario) => navigate(`/scenarios/${scenario.id}`),
    onError: (err) => setError(apiMessage(err)),
  });
  const cloneMutation = useMutation({
    mutationFn: async (id: string) =>
      cloneScenario(id, {}, workspaceId, await getWriteToken()),
    onSuccess: (scenario) => navigate(`/scenarios/${scenario.id}`),
    onError: (err) => setError(apiMessage(err)),
  });
  const archiveMutation = useMutation({
    mutationFn: async (id: string) =>
      deleteScenario(id, workspaceId, await getWriteToken()),
    onSuccess: async () => {
      setArchiveTarget(null);
      await queryClient.invalidateQueries({
        queryKey: ["scenarios", workspaceId],
      });
    },
    onError: (err) => setError(apiMessage(err)),
  });
  const rows = query.data?.items ?? [];
  return (
    <section className="mx-auto max-w-7xl">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-white">
            {scenarioCopy.title}
          </h1>
          <p className="mt-2 text-sm text-text-muted">
            Design request flows, save revisions, and start low-risk Debug Runs.
          </p>
        </div>
        <button
          className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary"
          onClick={() => setShowCreate(true)}
          type="button"
        >
          {scenarioCopy.createButton}
        </button>
      </div>
      {error ? (
        <div className="mb-4 rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
          {error}
        </div>
      ) : null}
      <div className="mb-4 flex gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3">
        <input
          aria-label="Search scenarios"
          className="flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
          placeholder="Search by name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select
          aria-label="Sort scenarios"
          className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
          value={sort}
          onChange={(e) => setSort(e.target.value as typeof sort)}
        >
          <option value="-updatedAt">Recently updated</option>
          <option value="updatedAt">Oldest updated</option>
          <option value="name">Name A-Z</option>
          <option value="-name">Name Z-A</option>
        </select>
      </div>
      <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.045]">
        <div className="grid grid-cols-[1.5fr_1fr_0.7fr_0.7fr_1fr_0.8fr] gap-4 border-b border-white/10 px-5 py-3 font-mono text-[11px] uppercase tracking-[0.16em] text-secondary">
          <span>Name</span>
          <span>Tags</span>
          <span>Steps</span>
          <span>Data Files</span>
          <span>Updated</span>
          <span>Actions</span>
        </div>
        {query.isLoading ? (
          <div className="p-8 text-text-muted">Loading scenarios…</div>
        ) : null}
        {!query.isLoading && rows.length === 0 ? (
          <div className="p-10 text-center">
            <h2 className="text-xl font-semibold text-white">
              {scenarioCopy.emptyTitle}
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              {scenarioCopy.emptyDescription}
            </p>
            <button
              className="mt-5 rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary"
              onClick={() => setShowCreate(true)}
              type="button"
            >
              {scenarioCopy.createButton}
            </button>
          </div>
        ) : null}
        {rows.map((item) => (
          <div
            className="grid grid-cols-[1.5fr_1fr_0.7fr_0.7fr_1fr_0.8fr] items-center gap-4 border-b border-white/5 px-5 py-4 text-sm last:border-b-0"
            key={item.id}
          >
            <Link
              className="font-semibold text-white hover:text-primary"
              to={`/scenarios/${item.id}`}
            >
              {item.name}
            </Link>
            <div className="flex flex-wrap gap-1">
              {item.tags.length > 0 ? (
                item.tags.map((tag) => (
                  <span
                    className="rounded-full border border-primary/20 px-2 py-0.5 text-xs text-primary"
                    key={tag}
                  >
                    {tag}
                  </span>
                ))
              ) : (
                <span className="text-xs text-text-muted">
                  {scenarioCopy.noTags}
                </span>
              )}
            </div>
            <span>
              {item.enabledStepCount}/{item.stepCount}
            </span>
            <span>{item.dependencyFileCount}</span>
            <span className="font-mono text-xs text-text-muted">
              {formatDate(item.updatedAt)}
            </span>
            <div className="flex gap-2">
              <IconActionLink
                Icon={Eye}
                label="Open"
                to={`/scenarios/${item.id}`}
              />
              <IconActionButton
                Icon={Copy}
                label={scenarioCopy.clone}
                onClick={() => cloneMutation.mutate(item.id)}
              />
              <IconActionButton
                Icon={Archive}
                label={scenarioCopy.archive}
                onClick={() => setArchiveTarget(item.id)}
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
              void createMutation.mutateAsync();
            }}
          >
            <h2 className="text-xl font-semibold text-white">
              {scenarioCopy.createTitle}
            </h2>
            <label className="mt-5 grid gap-1 text-sm text-text-muted">
              Scenario name
              <input
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Base URL expression
              <input
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-white"
                value={createBaseUrl}
                onChange={(e) => setCreateBaseUrl(e.target.value)}
              />
            </label>
            <label className="mt-4 grid gap-1 text-sm text-text-muted">
              Tags
              <input
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                placeholder="checkout, smoke"
                value={createTags}
                onChange={(e) => setCreateTags(e.target.value)}
              />
            </label>
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-white"
                onClick={() => setShowCreate(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary"
                disabled={!createName.trim() || createMutation.isPending}
                type="submit"
              >
                Create
              </button>
            </div>
          </form>
        </div>
      ) : null}
      {archiveTarget ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div
            aria-label={scenarioCopy.archiveTitle}
            className="max-w-lg rounded-3xl border border-white/10 bg-surface-container-low p-6"
            role="dialog"
          >
            <h2 className="text-xl font-semibold text-white">
              {scenarioCopy.archiveTitle}
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              {scenarioCopy.archiveBody}
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-white"
                onClick={() => setArchiveTarget(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-xl bg-error px-4 py-2 font-semibold text-background"
                onClick={() => void archiveMutation.mutateAsync(archiveTarget)}
                type="button"
              >
                {scenarioCopy.archive}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
