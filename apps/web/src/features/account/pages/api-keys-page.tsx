import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, RefreshCw, Trash2, X } from "lucide-react";

import {
  ApiError,
  createAccountApiToken,
  deleteAccountApiToken,
  getCsrfToken,
  listAccountApiTokens,
  type ApiTokenMetadata,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { copyText } from "../../../utils/clipboard";

type Scope = "read" | "config:write" | "run" | "dependency:write";

const scopeOptions: Array<{ label: string; value: Scope; description: string }> = [
  { label: "Read", value: "read", description: "Read Scenarios, Test Plans, Runs, reports, and Load Nodes." },
  { label: "Config write", value: "config:write", description: "Create and update Env Groups, Scenarios, and Test Plans." },
  { label: "Run", value: "run", description: "Create and stop Runs, and inspect Run lifecycle data." },
  { label: "Dependency write", value: "dependency:write", description: "Upload and delete Dependency Files used by Scenario scripts." },
];

function formatDate(value: string | null | undefined) {
  if (!value) return "Never";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function defaultExpiry() {
  const value = new Date();
  value.setDate(value.getDate() + 90);
  return value.toISOString().slice(0, 10);
}

function expiryToIso(value: string) {
  return new Date(`${value}T23:59:59.000Z`).toISOString();
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "WORKSPACE_ACCESS_DENIED") return "You do not have access to one of the selected Workspaces.";
    if (error.body.code === "VALIDATION_ERROR") return "Check the key details and try again.";
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong. Try again.";
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

export function ApiKeysPage() {
  const queryClient = useQueryClient();
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [expiresOn, setExpiresOn] = useState(defaultExpiry());
  const [formError, setFormError] = useState<string | null>(null);
  const [createdPlaintext, setCreatedPlaintext] = useState<string | null>(null);
  const [copySucceeded, setCopySucceeded] = useState(false);
  const [workspaceCopySucceeded, setWorkspaceCopySucceeded] = useState(false);
  const [workspaceCopyError, setWorkspaceCopyError] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiTokenMetadata | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);

  const listQuery = useQuery({ queryKey: ["account-api-tokens"], queryFn: listAccountApiTokens });
  const workspaceId = session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const workspaceName = session?.currentWorkspace.name ?? "Current Workspace";
  const rows = listQuery.data?.items ?? [];

  const activeCount = useMemo(() => rows.filter((row) => row.revokedAt === null).length, [rows]);

  useEffect(() => {
    if (!copySucceeded) return undefined;
    const timeoutId = window.setTimeout(() => setCopySucceeded(false), 2000);
    return () => window.clearTimeout(timeoutId);
  }, [copySucceeded]);

  useEffect(() => {
    if (!workspaceCopySucceeded) return undefined;
    const timeoutId = window.setTimeout(() => setWorkspaceCopySucceeded(false), 2000);
    return () => window.clearTimeout(timeoutId);
  }, [workspaceCopySucceeded]);

  async function copyCreatedToken() {
    if (!createdPlaintext) return;
    const result = await copyText(createdPlaintext);
    if (result.ok) {
      setCopySucceeded(true);
      setFormError(null);
      return;
    }
    setFormError(result.reason);
  }

  async function copyWorkspaceId() {
    if (!workspaceId) return;
    const result = await copyText(workspaceId);
    if (result.ok) {
      setWorkspaceCopySucceeded(true);
      setWorkspaceCopyError(null);
      return;
    }
    setWorkspaceCopySucceeded(false);
    setWorkspaceCopyError(result.reason);
  }

  const createMutation = useMutation({
    mutationFn: async () => {
      const trimmedName = name.trim();
      if (!trimmedName) throw new Error("Name is required.");
      if (scopes.length === 0) throw new Error("Select at least one scope.");
      return createAccountApiToken(
        {
          name: trimmedName,
          scopes,
          workspaceAllowlist: [workspaceId],
          expiresAt: expiryToIso(expiresOn),
        },
        await getWriteToken(),
      );
    },
    onSuccess: async (response) => {
      setCreatedPlaintext(response.token.plaintext);
      setName("");
      setScopes([]);
      setExpiresOn(defaultExpiry());
      setFormError(null);
      setCopySucceeded(false);
      await queryClient.invalidateQueries({ queryKey: ["account-api-tokens"] });
    },
    onError: (error) => {
      setFormError(errorMessage(error));
    },
  });

  const revokeMutation = useMutation({
    mutationFn: async (tokenId: string) => deleteAccountApiToken(tokenId, await getWriteToken()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["account-api-tokens"] });
      setRevokeTarget(null);
      setRevokeError(null);
    },
    onError: (error) => setRevokeError(errorMessage(error)),
  });

  function toggleScope(scope: Scope) {
    setScopes((current) =>
      current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope],
    );
  }

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-secondary">Account</p>
            <h1 className="mt-2 font-display text-3xl font-semibold text-white">API Keys</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-muted">
              Create personal access tokens for programmatic SurgePilot access. Tokens are self-service credentials for your user account and are shown only once.
            </p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-[0_0_24px_rgba(34,211,238,0.25)]"
            onClick={() => setCreateOpen(true)}
            type="button"
          >
            <Plus aria-hidden className="h-4 w-4" />
            Create API Key
          </button>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-secondary">Active keys</p>
            <p className="mt-2 text-2xl font-semibold text-white">{activeCount}</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-secondary">Workspace</p>
            <p className="mt-2 truncate text-sm font-semibold text-white">{workspaceName}</p>
            {workspaceId ? (
              <div className="mt-3 border-t border-white/10 pt-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">Workspace ID (x-workspace-id)</p>
                <div className="mt-2 flex items-start gap-2">
                  <code className="min-w-0 flex-1 break-all font-mono text-xs leading-5 text-secondary">{workspaceId}</code>
                  <button
                    aria-label={workspaceCopySucceeded ? "Workspace ID copied" : "Copy Workspace ID"}
                    className="inline-flex flex-none items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-text-main transition hover:border-primary/30 hover:bg-white/10"
                    onClick={() => void copyWorkspaceId()}
                    type="button"
                  >
                    {workspaceCopySucceeded ? <Check aria-hidden className="h-3.5 w-3.5" /> : <Copy aria-hidden className="h-3.5 w-3.5" />}
                    {workspaceCopySucceeded ? "Copied" : "Copy"}
                  </button>
                </div>
                {workspaceCopyError ? <p className="mt-2 text-xs leading-5 text-danger" role="alert">{workspaceCopyError}</p> : null}
              </div>
            ) : null}
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.18em] text-secondary">Available scopes</p>
            <p className="mt-2 text-sm font-semibold text-white">read · config:write · run · dependency:write</p>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">Your keys</h2>
          <button
            aria-label="Refresh API keys"
            className="rounded-xl border border-white/10 p-2 text-text-muted hover:text-white"
            onClick={() => void listQuery.refetch()}
            type="button"
          >
            <RefreshCw aria-hidden className="h-4 w-4" />
          </button>
        </div>
        {listQuery.isLoading ? (
          <div aria-label="Loading API keys" className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-text-muted" role="status">Loading API keys...</div>
        ) : rows.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/10 p-8 text-center text-sm text-text-muted">No API keys yet. Create one when you need programmatic access.</div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-white/10">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-white/5 text-xs uppercase tracking-[0.16em] text-secondary">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Scopes</th>
                  <th className="px-4 py-3">Expires</th>
                  <th className="px-4 py-3">Last used</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {rows.map((token) => (
                  <tr key={token.id}>
                    <td className="px-4 py-3 text-white">
                      <div className="font-semibold">{token.name}</div>
                      <div className="font-mono text-xs text-secondary">{token.publicId}</div>
                    </td>
                    <td className="px-4 py-3 text-text-muted">{token.scopes.join(", ")}</td>
                    <td className="px-4 py-3 text-text-muted">{formatDate(token.expiresAt)}</td>
                    <td className="px-4 py-3 text-text-muted">{formatDate(token.lastUsedAt)}</td>
                    <td className="px-4 py-3"><span className="rounded-full border border-white/10 px-2 py-1 text-xs text-text-muted">{token.revokedAt ? "Revoked" : "Active"}</span></td>
                    <td className="px-4 py-3 text-right">
                      <button
                        aria-label={`Revoke ${token.name}`}
                        className="inline-flex items-center gap-2 rounded-xl border border-danger/30 px-3 py-1.5 text-xs font-semibold text-danger disabled:opacity-50"
                        disabled={token.revokedAt !== null}
                        onClick={() => setRevokeTarget(token)}
                        type="button"
                      >
                        <Trash2 aria-hidden className="h-3.5 w-3.5" />
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog.Root open={createOpen} onOpenChange={(open) => { setCreateOpen(open); if (!open) setCreatedPlaintext(null); }}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-white/10 bg-surface-container-low p-6 text-text-main shadow-2xl" aria-describedby="api-key-create-description">
            <div className="flex items-start justify-between gap-4">
              <div>
                <Dialog.Title className="font-display text-2xl font-semibold text-white">Create API Key</Dialog.Title>
                <Dialog.Description id="api-key-create-description" className="mt-2 text-sm leading-6 text-text-muted">Choose the minimum scopes required for this automation.</Dialog.Description>
              </div>
              <Dialog.Close className="rounded-xl border border-white/10 p-2 text-text-muted hover:text-white"><X aria-hidden className="h-4 w-4" /></Dialog.Close>
            </div>

            {createdPlaintext ? (
              <div className="mt-6 rounded-2xl border border-success/30 bg-success/10 p-4">
                <p className="text-sm font-semibold text-success">Copy this token now. It will not be shown again.</p>
                <div className="mt-3 flex flex-col gap-3 rounded-xl border border-white/10 bg-black/30 p-3 sm:flex-row sm:items-start">
                  <code className="block min-w-0 flex-1 break-all font-mono text-xs text-white">{createdPlaintext}</code>
                  <button
                    className="inline-flex flex-none items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-text-main transition hover:border-primary/30 hover:bg-white/10"
                    onClick={() => void copyCreatedToken()}
                    type="button"
                  >
                    {copySucceeded ? <Check aria-hidden className="h-3.5 w-3.5" /> : <Copy aria-hidden className="h-3.5 w-3.5" />}
                    {copySucceeded ? "Copied" : "Copy"}
                  </button>
                </div>
                {formError ? <p className="mt-3 text-sm text-danger">{formError}</p> : null}
                <div className="mt-4 flex justify-end">
                  <button
                    className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
                    onClick={() => setCreateOpen(false)}
                    type="button"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form
                className="mt-6 space-y-5"
                onSubmit={(event) => {
                  event.preventDefault();
                  setFormError(null);
                  createMutation.mutate();
                }}
              >
                <label className="block text-sm font-medium text-text-muted">
                  Name
                  <input className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white outline-none focus:border-primary" maxLength={120} onChange={(event) => setName(event.target.value)} value={name} />
                </label>
                <div>
                  <p className="text-sm font-medium text-text-muted">Scopes</p>
                  <div className="mt-2 grid gap-3 sm:grid-cols-3">
                    {scopeOptions.map((option) => (
                      <label className="rounded-2xl border border-white/10 bg-white/5 p-3 text-sm" key={option.value}>
                        <span className="flex items-center gap-2 font-semibold text-white">
                          <input aria-label={option.label} checked={scopes.includes(option.value)} onChange={() => toggleScope(option.value)} type="checkbox" />
                          {option.label}
                        </span>
                        <span className="mt-2 block text-xs leading-5 text-text-muted">{option.description}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <label className="block text-sm font-medium text-text-muted">
                  Expires on
                  <input className="mt-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-white outline-none focus:border-primary" min={new Date().toISOString().slice(0, 10)} onChange={(event) => setExpiresOn(event.target.value)} type="date" value={expiresOn} />
                </label>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-sm text-text-muted">
                  This key will be allowlisted for <span className="font-semibold text-white">{workspaceName}</span>. Public API callers must send <span className="font-mono">x-workspace-id</span> when a token has more than one Workspace.
                </div>
                {formError ? <p className="text-sm text-danger">{formError}</p> : null}
                <div className="flex justify-end gap-3">
                  <Dialog.Close className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main" type="button">Cancel</Dialog.Close>
                  <button className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60" disabled={createMutation.isPending} type="submit">Create key</button>
                </div>
              </form>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root open={revokeTarget !== null} onOpenChange={(open) => !open && setRevokeTarget(null)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content aria-describedby="api-key-revoke-description" className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-white/10 bg-surface-container-low p-6 text-text-main shadow-2xl">
            <Dialog.Title className="font-display text-2xl font-semibold text-white">Revoke {revokeTarget?.name}?</Dialog.Title>
            <Dialog.Description id="api-key-revoke-description" className="mt-3 text-sm leading-6 text-text-muted">Existing automation using this key will stop authenticating immediately.</Dialog.Description>
            {revokeError ? <p className="mt-3 text-sm text-danger">{revokeError}</p> : null}
            <div className="mt-6 flex justify-end gap-3">
              <Dialog.Close className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main" type="button">Cancel</Dialog.Close>
              <button className="rounded-xl bg-danger px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={revokeMutation.isPending} onClick={() => revokeTarget && revokeMutation.mutate(revokeTarget.id)} type="button">Revoke key</button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
