import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  Copy,
  Edit3,
  FileText,
  KeyRound,
  PlayCircle,
  Plus,
  RefreshCw,
  Search,
  ShieldOff,
  X,
} from "lucide-react";

import {
  deleteLoadNode,
  disableLoadNode,
  enableLoadNode,
  getCsrfToken,
  getLoadNodeConnectivitySummary,
  getLoadNodeInitAttempt,
  initializeLoadNode,
  listLoadNodeInitAttempts,
  listLoadNodes,
  patchLoadNode,
  scanLoadNodeSshHostKey,
  trustLoadNodeSshHostKey,
  updateLoadNodeCredentials,
  type LoadNodeAuthType,
  type LoadNodePatchRequest,
  type LoadNodeScope,
  type LoadNodeSshHostKeyScanResponse,
  type LoadNodeStatus,
  type LoadNodeSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { cn } from "../../../utils/cn";
import { copyText } from "../../../utils/clipboard";
import { LoadNodeConnectivitySummaryCard } from "../components/load-node-connectivity-summary";
import { loadNodeErrorMessage, statusCopy } from "./load-node-copy";

const pageSize = 20;
const statuses: LoadNodeStatus[] = [
  "uninitialized",
  "initializing",
  "idle",
  "busy",
  "offline",
  "quarantined",
  "disabled",
];
const allowedEditStatuses = new Set<LoadNodeStatus>([
  "uninitialized",
  "idle",
  "offline",
]);

type EditState = Pick<
  LoadNodePatchRequest,
  "host" | "sshPort" | "sshUser" | "runnerHome" | "maintainer" | "remark"
>;
type CredentialState = {
  authType: LoadNodeAuthType;
  password: string;
  privateKey: string;
  privateKeyPassphrase: string;
};

type LogState = { node: LoadNodeSummary; attemptId: string | null };
const emptyCredentialForm: CredentialState = {
  authType: "password",
  password: "",
  privateKey: "",
  privateKeyPassphrase: "",
};

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(status: LoadNodeStatus) {
  return {
    uninitialized: "border-white/10 bg-white/5 text-text-muted",
    initializing: "border-primary/30 bg-primary/10 text-primary",
    idle: "border-success/30 bg-success/10 text-success",
    busy: "border-warning/30 bg-warning/10 text-warning",
    offline: "border-error/30 bg-error-container text-error",
    quarantined: "border-error/40 bg-error-container text-error",
    disabled: "border-white/10 bg-white/5 text-secondary",
  }[status];
}

function canManageNode(node: LoadNodeSummary, role?: string) {
  return node.scope === "workspace" || role === "admin";
}

function nodeToEdit(node: LoadNodeSummary): EditState {
  return {
    host: node.host,
    sshPort: node.sshPort,
    sshUser: node.sshUser,
    runnerHome: node.runnerHome,
    maintainer: node.maintainer ?? "",
    remark: node.remark ?? "",
  };
}

function credentialPayload(form: CredentialState) {
  if (form.authType === "password") {
    return {
      credential: { authType: "password" as const, password: form.password },
    };
  }
  if (form.authType === "private_key") {
    return {
      credential: {
        authType: "private_key" as const,
        privateKey: form.privateKey,
        privateKeyPassphrase: form.privateKeyPassphrase || undefined,
      },
    };
  }
  return { credential: { authType: "generated_key" as const } };
}

export function LoadNodesPage() {
  const queryClient = useQueryClient();
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const role = session?.user.role;
  const isAdmin = role === "admin";
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<LoadNodeScope | "">("");
  const [status, setStatus] = useState<LoadNodeStatus | "">("");
  const [page, setPage] = useState(0);
  const [editTarget, setEditTarget] = useState<LoadNodeSummary | null>(null);
  const [editForm, setEditForm] = useState<EditState | null>(null);
  const [editTrustedHostKey, setEditTrustedHostKey] =
    useState<LoadNodeSshHostKeyScanResponse | null>(null);
  const [credentialTarget, setCredentialTarget] =
    useState<LoadNodeSummary | null>(null);
  const [credentialForm, setCredentialForm] =
    useState<CredentialState>(emptyCredentialForm);
  const [generatedKeyNode, setGeneratedKeyNode] =
    useState<LoadNodeSummary | null>(null);
  const [archiveTarget, setArchiveTarget] = useState<LoadNodeSummary | null>(
    null,
  );
  const [initConfirmTarget, setInitConfirmTarget] =
    useState<LoadNodeSummary | null>(null);
  const [logState, setLogState] = useState<LogState | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  async function handleCopy(text: string) {
    setCopyFeedback(null);
    const result = await copyText(text);
    setCopyFeedback(result.ok ? "Copied." : result.reason);
  }

  const connectivityQuery = useQuery({
    enabled: session !== null,
    queryKey: ["load-node-connectivity-summary"],
    queryFn: getLoadNodeConnectivitySummary,
  });

  const listQuery = useQuery({
    enabled: session !== null,
    queryKey: ["load-nodes", workspaceId, q, scope, status, page],
    queryFn: () =>
      listLoadNodes({
        workspaceId,
        q,
        scope,
        status,
        limit: pageSize,
        offset: page * pageSize,
        sort: "-createdAt",
      }),
    refetchInterval: (query) =>
      query.state.data?.items.some((node) => node.status === "initializing")
        ? 2000
        : false,
  });

  const rows = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isFiltered = Boolean(q || scope || status);

  const logAttempts = useQuery({
    enabled: logState !== null,
    queryKey: ["load-node-init-attempts", workspaceId, logState?.node.id],
    queryFn: () =>
      listLoadNodeInitAttempts(logState?.node.id ?? "", workspaceId),
  });
  const selectedAttemptId =
    logState?.attemptId ?? logAttempts.data?.items[0]?.id;
  const logDetail = useQuery({
    enabled: logState !== null && Boolean(selectedAttemptId),
    queryKey: [
      "load-node-init-attempt",
      workspaceId,
      logState?.node.id,
      selectedAttemptId,
    ],
    queryFn: () =>
      getLoadNodeInitAttempt(
        logState?.node.id ?? "",
        selectedAttemptId ?? "",
        workspaceId,
      ),
  });

  const invalidate = async () =>
    queryClient.invalidateQueries({ queryKey: ["load-nodes", workspaceId] });

  const editEndpointChanged =
    editTarget !== null &&
    editForm !== null &&
    (editForm.host !== editTarget.host || editForm.sshPort !== editTarget.sshPort);

  const editScanMutation = useMutation({
    mutationFn: async () =>
      scanLoadNodeSshHostKey(
        {
          scope: editTarget?.scope ?? "workspace",
          host: editForm?.host ?? "",
          sshPort: editForm?.sshPort ?? 22,
        },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (result) => {
      setEditTrustedHostKey(result);
      setActionError(null);
    },
    onError: (error) => {
      setEditTrustedHostKey(null);
      setActionError(loadNodeErrorMessage(error));
    },
  });

  const editMutation = useMutation({
    mutationFn: async () => {
      if (editEndpointChanged && editTrustedHostKey === null) {
        throw new Error("Scan and confirm the SSH host key before saving host or port changes.");
      }
      const updated = await patchLoadNode(
        editTarget?.id ?? "",
        editForm ?? {},
        workspaceId,
        await getWriteToken(),
      );
      if (editEndpointChanged && editTrustedHostKey !== null) {
        return trustLoadNodeSshHostKey(
          updated.id,
          {
            algorithm: editTrustedHostKey.algorithm,
            publicKey: editTrustedHostKey.publicKey,
            fingerprintSha256: editTrustedHostKey.fingerprintSha256,
          },
          workspaceId,
          await getWriteToken(),
        );
      }
      return updated;
    },
    onSuccess: async () => {
      setEditTarget(null);
      setEditForm(null);
      setEditTrustedHostKey(null);
      setActionError(null);
      await invalidate();
    },
    onError: (error) =>
      setActionError(
        error instanceof Error && !("body" in error)
          ? error.message
          : loadNodeErrorMessage(error),
      ),
  });
  const credentialMutation = useMutation({
    mutationFn: async () =>
      updateLoadNodeCredentials(
        credentialTarget?.id ?? "",
        credentialPayload(credentialForm),
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: async (node) => {
      setCredentialTarget(null);
      setCredentialForm(emptyCredentialForm);
      setGeneratedKeyNode(node.generatedPublicKey ? node : null);
      setActionError(null);
      await invalidate();
    },
    onError: (error) => setActionError(loadNodeErrorMessage(error)),
  });
  const initializeMutation = useMutation({
    mutationFn: async ({
      node,
      force,
    }: {
      node: LoadNodeSummary;
      force: boolean;
    }) =>
      initializeLoadNode(node.id, workspaceId, await getWriteToken(), force),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
    },
    onError: (error) => setActionError(loadNodeErrorMessage(error)),
  });
  const toggleMutation = useMutation({
    mutationFn: async (node: LoadNodeSummary) =>
      node.status === "disabled"
        ? enableLoadNode(node.id, workspaceId, await getWriteToken())
        : disableLoadNode(
            node.id,
            workspaceId,
            await getWriteToken(),
            "Disabled from Load Nodes page",
          ),
    onSuccess: async () => {
      setActionError(null);
      await invalidate();
    },
    onError: (error) => setActionError(loadNodeErrorMessage(error)),
  });
  const archiveMutation = useMutation({
    mutationFn: async () =>
      deleteLoadNode(
        archiveTarget?.id ?? "",
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: async () => {
      setArchiveTarget(null);
      setActionError(null);
      await invalidate();
    },
    onError: (error) => setActionError(loadNodeErrorMessage(error)),
  });

  const attemptRows = logAttempts.data?.items ?? [];

  const emptyCopy = useMemo(() => {
    if (isFiltered)
      return "No load nodes match the current filters. Clear filters and try again.";
    if (role === "admin")
      return "No load nodes yet. Register a workspace node, or add a public node as an administrator.";
    return "No workspace load nodes yet. Register a node for this workspace to get started.";
  }, [isFiltered, role]);

  if (session === null) return null;

  function startEdit(node: LoadNodeSummary) {
    setActionError(null);
    setEditTarget(node);
    setEditForm(nodeToEdit(node));
    setEditTrustedHostKey(null);
  }

  function updateSearch(value: string) {
    setQ(value);
    setPage(0);
  }

  return (
    <section className="mx-auto flex max-w-container-max flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-[-0.03em] text-white">
            Load Nodes
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-text-muted">
            Manage workspace and public load nodes. Initialized idle nodes can
            be selected for manual single-node runs.
          </p>
        </div>
        <Link
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-on-primary shadow-[0_0_18px_rgba(34,211,238,0.22)]"
          to="/resources/load-nodes/new"
        >
          <Plus className="h-4 w-4" />
          Register Load Node
        </Link>
      </div>

      {actionError ? (
        <div className="rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
          {actionError}
        </div>
      ) : null}

      <div className="surgepilot-glass rounded-2xl p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <label className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-secondary" />
            <span className="sr-only">Search load nodes</span>
            <input
              className="w-full rounded-xl border border-white/10 bg-black/20 py-2 pl-10 pr-3 text-sm text-white outline-none transition focus:border-primary"
              placeholder="Search nodes..."
              value={q}
              onChange={(event) => updateSearch(event.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <select
              aria-label="Scope filter"
              className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-sm text-white"
              value={scope}
              onChange={(e) => {
                setScope(e.target.value as LoadNodeScope | "");
                setPage(0);
              }}
            >
              <option value="">All scopes</option>
              <option value="public">Public</option>
              <option value="workspace">Private</option>
            </select>
            <select
              aria-label="Status filter"
              className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-sm text-white"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as LoadNodeStatus | "");
                setPage(0);
              }}
            >
              <option value="">All statuses</option>
              {statuses.map((item) => (
                <option key={item} value={item}>
                  {statusCopy[item]}
                </option>
              ))}
            </select>
            <button
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm text-text-muted hover:text-white"
              onClick={() => void listQuery.refetch()}
              type="button"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]">
        {listQuery.isLoading ? (
          <div className="p-10 text-center text-text-muted">
            Loading Load Nodes…
          </div>
        ) : null}
        {listQuery.isError ? (
          <div className="p-10 text-center text-error">
            {loadNodeErrorMessage(listQuery.error)}
          </div>
        ) : null}
        {!listQuery.isLoading && !listQuery.isError && rows.length === 0 ? (
          <div className="p-12 text-center">
            <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl border border-primary/30 bg-primary/10 text-primary">
              <Plus className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-white">
              No Load Nodes yet
            </h2>
            <p className="mt-2 text-sm text-text-muted">{emptyCopy}</p>
            {isFiltered ? (
              <button
                className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-sm text-white"
                onClick={() => {
                  setQ("");
                  setScope("");
                  setStatus("");
                }}
                type="button"
              >
                Clear filters
              </button>
            ) : null}
          </div>
        ) : null}
        {rows.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/10 text-left text-sm">
              <thead className="bg-white/[0.04] text-xs uppercase tracking-[0.18em] text-secondary">
                <tr>
                  <th className="px-4 py-3">Host</th>
                  <th className="px-4 py-3">Scope</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Maintainer</th>
                  <th className="px-4 py-3">Last checked</th>
                  <th className="px-4 py-3">Agent</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {rows.map((node) => {
                  const manageable = canManageNode(node, role);
                  return (
                    <tr key={node.id} className="hover:bg-white/[0.03]">
                      <td className="px-4 py-4">
                        <div className="font-medium text-white">
                          {node.host}
                        </div>
                        <div className="font-mono text-xs text-secondary">
                          {node.sshUser}:{node.sshPort}
                        </div>
                      </td>
                      <td className="px-4 py-4 text-text-muted">
                        {node.scope === "public" ? "Public" : "Private"}
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className={cn(
                            "inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold",
                            statusTone(node.status),
                          )}
                        >
                          {statusCopy[node.status]}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-text-muted">
                        {node.maintainer ?? "—"}
                      </td>
                      <td className="px-4 py-4 text-text-muted">
                        {formatDate(node.lastCheckedAt)}
                      </td>
                      <td className="px-4 py-4">
                        <div className="text-text-muted">
                          {node.runnerVersion ?? "—"}
                        </div>
                        <div className="font-mono text-xs text-secondary">
                          Current Run: {node.currentRunId ?? "—"}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex justify-end gap-2">
                          <button
                            aria-label={`View logs ${node.host}`}
                            className="rounded-lg border border-white/10 p-2 text-text-muted hover:text-white"
                            onClick={() =>
                              setLogState({
                                node,
                                attemptId: node.lastInitAttemptId ?? null,
                              })
                            }
                            type="button"
                          >
                            <FileText className="h-4 w-4" />
                          </button>
                          {manageable ? (
                            <>
                              <button
                                aria-label={`Initialize ${node.host}`}
                                className="rounded-lg border border-white/10 p-2 text-primary disabled:opacity-40"
                                disabled={
                                  initializeMutation.isPending ||
                                  node.status === "busy" ||
                                  node.status === "disabled" ||
                                  node.status === "quarantined"
                                }
                                onClick={() =>
                                  setInitConfirmTarget(node)
                                }
                                type="button"
                              >
                                <PlayCircle className="h-4 w-4" />
                              </button>
                              <button
                                aria-label={`Edit ${node.host}`}
                                className="rounded-lg border border-white/10 p-2 text-text-muted hover:text-white disabled:opacity-40"
                                disabled={!allowedEditStatuses.has(node.status)}
                                onClick={() => startEdit(node)}
                                type="button"
                              >
                                <Edit3 className="h-4 w-4" />
                              </button>
                              <button
                                aria-label={`Update credentials ${node.host}`}
                                className="rounded-lg border border-white/10 p-2 text-text-muted hover:text-white disabled:opacity-40"
                                disabled={!allowedEditStatuses.has(node.status)}
                                onClick={() => {
                                  setActionError(null);
                                  setCredentialForm(emptyCredentialForm);
                                  setCredentialTarget(node);
                                }}
                                type="button"
                              >
                                <KeyRound className="h-4 w-4" />
                              </button>
                              <button
                                aria-label={`${node.status === "disabled" ? "Enable" : "Disable"} ${node.host}`}
                                className="rounded-lg border border-white/10 p-2 text-text-muted hover:text-white disabled:opacity-40"
                                disabled={node.status === "busy"}
                                onClick={() => toggleMutation.mutate(node)}
                                type="button"
                              >
                                <ShieldOff className="h-4 w-4" />
                              </button>
                              <button
                                aria-label={`Archive ${node.host}`}
                                className="rounded-lg border border-white/10 p-2 text-error disabled:opacity-40"
                                disabled={node.status === "busy"}
                                onClick={() => {
                                  setActionError(null);
                                  setArchiveTarget(node);
                                }}
                                type="button"
                              >
                                <Archive className="h-4 w-4" />
                              </button>
                            </>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
      <div className="flex items-center justify-between text-sm text-text-muted">
        <span>{total} node(s)</span>
        <div className="flex gap-2">
          <button
            className="rounded-lg border border-white/10 px-3 py-2 disabled:opacity-40"
            disabled={page === 0 || listQuery.isFetching}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
            type="button"
          >
            Previous
          </button>
          <button
            className="rounded-lg border border-white/10 px-3 py-2 disabled:opacity-40"
            disabled={page + 1 >= totalPages || listQuery.isFetching}
            onClick={() => setPage((current) => current + 1)}
            type="button"
          >
            Next
          </button>
        </div>
      </div>

      <Dialog.Root
        open={editTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditTarget(null);
            setEditTrustedHostKey(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(680px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#111827] p-6 text-white shadow-2xl">
            <div className="flex items-center justify-between">
              <Dialog.Title className="text-lg font-semibold">
                Edit Load Node
              </Dialog.Title>
              <Dialog.Close className="text-secondary">
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>
            {editForm ? (
              <form
                className="mt-5 grid gap-4 sm:grid-cols-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  editMutation.mutate();
                }}
              >
                <label className="grid gap-1 text-sm">
                  Host
                  <input
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    value={editForm.host ?? ""}
                    onChange={(e) => {
                      setEditTrustedHostKey(null);
                      setEditForm({ ...editForm, host: e.target.value });
                    }}
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  Port
                  <input
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    type="number"
                    value={editForm.sshPort ?? 22}
                    onChange={(e) => {
                      setEditTrustedHostKey(null);
                      setEditForm({
                        ...editForm,
                        sshPort: Number(e.target.value),
                      });
                    }}
                  />
                </label>
                {editEndpointChanged ? (
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm sm:col-span-2">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold text-white">
                          SSH host key trust required
                        </div>
                        <p className="mt-1 text-xs text-text-muted">
                          Host or port changes clear the previous trusted key.
                          Scan and confirm the new endpoint before saving.
                        </p>
                      </div>
                      <button
                        className="rounded-lg border border-primary/30 px-3 py-2 text-primary disabled:opacity-50"
                        disabled={editScanMutation.isPending}
                        onClick={() => void editScanMutation.mutateAsync()}
                        type="button"
                      >
                        {editScanMutation.isPending ? "Scanning..." : "Scan key"}
                      </button>
                    </div>
                    {editTrustedHostKey ? (
                      <div className="mt-3 rounded-lg border border-success/25 bg-success/10 p-3 text-xs">
                        <div className="font-mono text-success">
                          {editTrustedHostKey.fingerprintSha256}
                        </div>
                        <div className="mt-1 break-all font-mono text-text-muted">
                          {editTrustedHostKey.knownHostsLine}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <label className="grid gap-1 text-sm">
                  SSH user
                  <input
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    value={editForm.sshUser ?? ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, sshUser: e.target.value })
                    }
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  Runner home
                  <input
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    value={editForm.runnerHome ?? ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, runnerHome: e.target.value })
                    }
                  />
                </label>
                <label className="grid gap-1 text-sm sm:col-span-2">
                  Maintainer
                  <input
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    value={editForm.maintainer ?? ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, maintainer: e.target.value })
                    }
                  />
                </label>
                <label className="grid gap-1 text-sm sm:col-span-2">
                  Remark
                  <textarea
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    value={editForm.remark ?? ""}
                    onChange={(e) =>
                      setEditForm({ ...editForm, remark: e.target.value })
                    }
                  />
                </label>
                <div className="sm:col-span-2 flex justify-end gap-2">
                  <Dialog.Close
                    className="rounded-lg border border-white/10 px-4 py-2"
                    type="button"
                  >
                    Cancel
                  </Dialog.Close>
                  <button
                    className="rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary"
                    disabled={editMutation.isPending}
                    type="submit"
                  >
                    Save Changes
                  </button>
                </div>
              </form>
            ) : null}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={credentialTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCredentialTarget(null);
            setCredentialForm(emptyCredentialForm);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(640px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#111827] p-6 text-white shadow-2xl">
            <div className="flex items-center justify-between">
              <Dialog.Title className="text-lg font-semibold">
                Update connection credentials
              </Dialog.Title>
              <Dialog.Close className="text-secondary">
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>
            <p className="mt-2 text-sm text-text-muted">
              Existing SSH credentials are write-only. Replacing them resets the
              node and requires initialization again.
            </p>
            <form
              className="mt-5 grid gap-4"
              onSubmit={(e) => {
                e.preventDefault();
                credentialMutation.mutate();
              }}
            >
              <label className="grid gap-1 text-sm">
                Authentication method
                <select
                  className="rounded-lg border border-white/10 bg-surface-container-low px-3 py-2"
                  value={credentialForm.authType}
                  onChange={(e) =>
                    setCredentialForm({
                      ...credentialForm,
                      authType: e.target.value as LoadNodeAuthType,
                    })
                  }
                >
                  <option value="password">Password</option>
                  <option value="private_key">SSH private key</option>
                  <option value="generated_key">Generate keypair</option>
                </select>
              </label>
              {credentialForm.authType === "password" ? (
                <label className="grid gap-1 text-sm">
                  Password
                  <input
                    className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                    type="password"
                    value={credentialForm.password}
                    onChange={(e) =>
                      setCredentialForm({
                        ...credentialForm,
                        password: e.target.value,
                      })
                    }
                  />
                </label>
              ) : null}
              {credentialForm.authType === "private_key" ? (
                <>
                  <label className="grid gap-1 text-sm">
                    SSH private key
                    <textarea
                      className="min-h-32 rounded-lg border border-white/10 bg-black/20 px-3 py-2 font-mono text-xs"
                      value={credentialForm.privateKey}
                      onChange={(e) =>
                        setCredentialForm({
                          ...credentialForm,
                          privateKey: e.target.value,
                        })
                      }
                    />
                  </label>
                  <label className="grid gap-1 text-sm">
                    Private key passphrase (optional)
                    <input
                      className="rounded-lg border border-white/10 bg-black/20 px-3 py-2"
                      type="password"
                      value={credentialForm.privateKeyPassphrase}
                      onChange={(e) =>
                        setCredentialForm({
                          ...credentialForm,
                          privateKeyPassphrase: e.target.value,
                        })
                      }
                    />
                  </label>
                </>
              ) : null}
              {credentialForm.authType === "generated_key" ? (
                <div className="rounded-xl border border-primary/20 bg-primary/10 p-4 text-sm text-primary">
                  SurgePilot will generate a new key pair, encrypt the private
                  key, and return only the public key.
                </div>
              ) : null}
              <div className="flex justify-end gap-2">
                <Dialog.Close
                  className="rounded-lg border border-white/10 px-4 py-2"
                  type="button"
                >
                  Cancel
                </Dialog.Close>
                <button
                  className="rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary"
                  disabled={credentialMutation.isPending}
                  type="submit"
                >
                  Replace Credentials
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={initConfirmTarget !== null}
        onOpenChange={(open) => {
          if (!open) setInitConfirmTarget(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(480px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#111827] p-6 text-white">
            <Dialog.Title className="text-lg font-semibold">
              {initConfirmTarget?.status === "idle" ? "Reinitialize Load Node?" : "Initialize Load Node?"}
            </Dialog.Title>
            <p className="mt-3 text-sm text-text-muted">
              {initConfirmTarget?.status === "idle"
                ? `${initConfirmTarget.host} is currently idle. Reinitializing will replace runner files and re-check prerequisites before the node is used again.`
                : `${initConfirmTarget?.host ?? "This node"} will be initialized with the current runner bundle and prerequisite checks.`}
            </p>
            <div className="mt-4">
              <LoadNodeConnectivitySummaryCard
                isAdmin={isAdmin}
                loadFailed={connectivityQuery.isError}
                successContext
                summary={connectivityQuery.data}
              />
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <Dialog.Close
                className="rounded-lg border border-white/10 px-4 py-2"
                type="button"
              >
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary"
                onClick={() => {
                  if (initConfirmTarget) {
                    initializeMutation.mutate({
                      node: initConfirmTarget,
                      force: initConfirmTarget.status === "idle",
                    });
                  }
                  setInitConfirmTarget(null);
                }}
                type="button"
              >
                {initConfirmTarget?.status === "idle" ? "Reinitialize" : "Initialize"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={generatedKeyNode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setGeneratedKeyNode(null);
            setCopyFeedback(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(640px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#111827] p-6 text-white shadow-2xl">
            <Dialog.Title className="text-lg font-semibold">
              Generated public key
            </Dialog.Title>
            <p className="mt-2 text-sm text-text-muted">
              Add this public key to the target host before initializing the
              node. It is shown here after credential replacement so it can be
              copied.
            </p>
            <div className="mt-5 rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-xs uppercase tracking-[0.18em] text-primary">
                  Installation key
                </span>
                <button
                  className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!generatedKeyNode?.generatedPublicKey}
                  onClick={() =>
                    void handleCopy(generatedKeyNode?.generatedPublicKey ?? "")
                  }
                  type="button"
                >
                  <Copy className="h-3 w-3" />
                  Copy
                </button>
              </div>
              {copyFeedback ? (
                <p className="mb-2 text-xs text-text-muted">{copyFeedback}</p>
              ) : null}
              <pre className="whitespace-pre-wrap break-all font-mono text-xs text-text-main">
                {generatedKeyNode?.generatedPublicKey}
              </pre>
            </div>
            <div className="mt-5 flex justify-end">
              <Dialog.Close className="rounded-lg bg-primary px-4 py-2 font-semibold text-on-primary">
                Done
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={archiveTarget !== null}
        onOpenChange={(open) => {
          if (!open) setArchiveTarget(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(480px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-[#111827] p-6 text-white">
            <Dialog.Title className="text-lg font-semibold">
              Archive Load Node
            </Dialog.Title>
            <p className="mt-3 text-sm text-text-muted">
              Archive {archiveTarget?.host}? Archived nodes are hidden from the
              default list.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Dialog.Close
                className="rounded-lg border border-white/10 px-4 py-2"
                type="button"
              >
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-error px-4 py-2 font-semibold text-[#2b0705]"
                onClick={() => archiveMutation.mutate()}
                type="button"
              >
                Archive
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={logState !== null}
        onOpenChange={(open) => {
          if (!open) {
            setLogState(null);
            setCopyFeedback(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 grid max-h-[82vh] w-[min(920px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 gap-4 overflow-hidden rounded-2xl border border-white/10 bg-[#111827] p-6 text-white">
            <div className="flex items-center justify-between">
              <Dialog.Title className="text-lg font-semibold">
                Initialization Log
              </Dialog.Title>
              <Dialog.Close className="text-secondary">
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>
            <div className="grid gap-4 md:grid-cols-[260px_1fr]">
              <div className="space-y-2 overflow-auto">
                {attemptRows.length > 0 ? (
                  attemptRows.map((attempt) => (
                    <button
                      className={cn(
                        "w-full rounded-xl border px-3 py-2 text-left text-sm",
                        selectedAttemptId === attempt.id
                          ? "border-primary bg-primary/10"
                          : "border-white/10 bg-white/5",
                      )}
                      key={attempt.id}
                      onClick={() =>
                        setLogState((current) =>
                          current
                            ? { ...current, attemptId: attempt.id }
                            : current,
                        )
                      }
                      type="button"
                    >
                      <div className="font-mono text-xs text-secondary">
                        {attempt.id.slice(-6)}
                      </div>
                      <div>{attempt.status}</div>
                      <div className="text-xs text-text-muted">
                        {attempt.errorCode ?? attempt.message ?? "—"}
                      </div>
                    </button>
                  ))
                ) : (
                  <p className="text-sm text-text-muted">No attempts yet.</p>
                )}
              </div>
              <div className="min-h-80 overflow-auto rounded-xl border border-white/10 bg-black/30 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-sm text-text-muted">
                    {logDetail.data?.errorCode ??
                      logDetail.data?.message ??
                      "Sanitized setup output"}
                  </div>
                  <button
                    className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={!logDetail.data?.sanitizedLogTail}
                    onClick={() =>
                      void handleCopy(logDetail.data?.sanitizedLogTail ?? "")
                    }
                    type="button"
                  >
                    <Copy className="h-3 w-3" />
                    Copy
                  </button>
                </div>
                {copyFeedback ? (
                  <p className="mb-2 text-xs text-text-muted">{copyFeedback}</p>
                ) : null}
                <pre className="whitespace-pre-wrap font-mono text-xs leading-5 text-text-main">
                  {logDetail.isLoading
                    ? "Loading setup output…"
                    : (logDetail.data?.sanitizedLogTail ??
                      "No setup output recorded.")}
                </pre>
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
