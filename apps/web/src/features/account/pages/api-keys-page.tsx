import { useEffect, useMemo, useState } from "react";

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
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const [tokens, setTokens] = useState<ApiTokenMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [expiresOn, setExpiresOn] = useState(defaultExpiry());
  const [formError, setFormError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createdPlaintext, setCreatedPlaintext] = useState<string | null>(null);
  const [copySucceeded, setCopySucceeded] = useState(false);
  const [workspaceCopySucceeded, setWorkspaceCopySucceeded] = useState(false);
  const [workspaceCopyError, setWorkspaceCopyError] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiTokenMetadata | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);

  const workspaceId = session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const workspaceName = session?.currentWorkspace.name ?? "Current Workspace";
  const rows = tokens;

  const activeCount = useMemo(() => rows.filter((row) => row.revokedAt === null).length, [rows]);

  async function load() {
    setIsLoading(true);
    try {
      setTokens((await listAccountApiTokens()).items);
      setListError(null);
    } catch (cause) {
      setListError(errorMessage(cause));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

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

  function resetCreateForm() {
    setName("");
    setScopes([]);
    setExpiresOn(defaultExpiry());
    setFormError(null);
    setCopySucceeded(false);
  }

  function closeCreate() {
    setCreateOpen(false);
    setCreatedPlaintext(null);
  }

  async function submitCreate() {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError("Name is required.");
      return;
    }
    if (scopes.length === 0) {
      setFormError("Select at least one scope.");
      return;
    }
    setIsCreating(true);
    setFormError(null);
    try {
      const response = await createAccountApiToken(
        {
          name: trimmedName,
          scopes,
          workspaceAllowlist: [workspaceId],
          expiresAt: expiryToIso(expiresOn),
        },
        await getWriteToken(),
      );
      setCreatedPlaintext(response.token.plaintext);
      resetCreateForm();
      await load();
    } catch (cause) {
      setFormError(errorMessage(cause));
    } finally {
      setIsCreating(false);
    }
  }

  async function confirmRevoke() {
    if (!revokeTarget) return;
    setIsRevoking(true);
    setRevokeError(null);
    try {
      await deleteAccountApiToken(revokeTarget.id, await getWriteToken());
      setRevokeTarget(null);
      await load();
    } catch (cause) {
      setRevokeError(errorMessage(cause));
    } finally {
      setIsRevoking(false);
    }
  }

  function toggleScope(scope: Scope) {
    setScopes((current) =>
      current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope],
    );
  }

  return (
    <main className="space-y-6">
      <section className="rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-xl">
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
            onClick={() => {
              setCreatedPlaintext(null);
              setFormError(null);
              setCreateOpen(true);
            }}
            type="button"
          >
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
      </section>

      <section className="rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-white">Your keys</h2>
          <button
            aria-label="Refresh API keys"
            className="rounded-xl border border-white/10 p-2 text-text-muted hover:text-white"
            onClick={() => void load()}
            type="button"
          >
            Refresh
          </button>
        </div>
        {listError ? <p className="mb-4 rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{listError}</p> : null}
        {isLoading ? (
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
                        onClick={() => {
                          setRevokeError(null);
                          setRevokeTarget(token);
                        }}
                        type="button"
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {createOpen ? (
        <div aria-labelledby="api-key-create-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog">
          <section className="w-full max-w-2xl rounded-3xl border border-white/10 bg-surface-container-low p-6 text-text-main shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-display text-2xl font-semibold text-white" id="api-key-create-title">Create API Key</h2>
                <p className="mt-2 text-sm leading-6 text-text-muted" id="api-key-create-description">Choose the minimum scopes required for this automation.</p>
              </div>
              <button aria-label="Close Create API Key" className="rounded-xl border border-white/10 p-2 text-text-muted hover:text-white" onClick={closeCreate} type="button">Close</button>
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
                    {copySucceeded ? "Copied" : "Copy"}
                  </button>
                </div>
                {formError ? <p className="mt-3 text-sm text-danger">{formError}</p> : null}
                <div className="mt-4 flex justify-end">
                  <button
                    className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
                    onClick={closeCreate}
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
                  void submitCreate();
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
                  <button className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main" onClick={closeCreate} type="button">Cancel</button>
                  <button className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60" disabled={isCreating} type="submit">Create key</button>
                </div>
              </form>
            )}
          </section>
        </div>
      ) : null}

      {revokeTarget !== null ? (
        <div aria-labelledby="api-key-revoke-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog">
          <section className="w-full max-w-md rounded-3xl border border-white/10 bg-surface-container-low p-6 text-text-main shadow-2xl">
            <h2 className="font-display text-2xl font-semibold text-white" id="api-key-revoke-title">Revoke {revokeTarget.name}?</h2>
            <p className="mt-3 text-sm leading-6 text-text-muted" id="api-key-revoke-description">Existing automation using this key will stop authenticating immediately.</p>
            {revokeError ? <p className="mt-3 text-sm text-danger">{revokeError}</p> : null}
            <div className="mt-6 flex justify-end gap-3">
              <button className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main" onClick={() => setRevokeTarget(null)} type="button">Cancel</button>
              <button className="rounded-xl bg-danger px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={isRevoking} onClick={() => void confirmRevoke()} type="button">Revoke key</button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
