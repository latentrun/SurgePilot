import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  ApiError,
  archiveAdminWorkspace,
  createAdminWorkspace,
  getCsrfToken,
  listAdminWorkspaces,
  patchAdminWorkspace,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

function errorCopy(error: unknown) {
  if (error instanceof ApiError) {
    return `Request failed. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Request failed. Refresh and try again.";
}

export function AdminWorkspacesPage() {
  const { csrfToken, refreshSession, session } = useAuthSession();
  const [name, setName] = useState("");
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<string | null>(
    null,
  );
  const [renameName, setRenameName] = useState("");
  const queryClient = useQueryClient();
  const isAdmin = session?.permissions.canManageWorkspaces === true;
  const query = useQuery({
    enabled: isAdmin,
    queryKey: ["admin-workspaces"],
    queryFn: () => listAdminWorkspaces("all"),
  });
  const getWriteToken = async () => csrfToken ?? (await getCsrfToken()).csrfToken;
  async function refreshWorkspaceState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["admin-workspaces"] }),
      queryClient.invalidateQueries({ queryKey: ["admin-user-workspaces"] }),
      refreshSession(session?.currentWorkspace.id ?? null),
    ]);
  }
  const createMutation = useMutation({
    mutationFn: async () =>
      createAdminWorkspace({ name }, await getWriteToken()),
    onSuccess: async () => {
      setName("");
      await refreshWorkspaceState();
    },
  });
  const archiveMutation = useMutation({
    mutationFn: async (workspaceId: string) =>
      archiveAdminWorkspace(workspaceId, await getWriteToken()),
    onSuccess: refreshWorkspaceState,
  });
  const renameMutation = useMutation({
    mutationFn: async () =>
      patchAdminWorkspace(
        editingWorkspaceId ?? "",
        { name: renameName },
        await getWriteToken(),
      ),
    onSuccess: async () => {
      setEditingWorkspaceId(null);
      setRenameName("");
      await refreshWorkspaceState();
    },
  });

  if (!isAdmin) {
    return <AdminForbidden />;
  }

  return (
    <section className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="surgepilot-glass rounded-3xl p-7">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-secondary">
          Admin
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-white">
          Workspaces
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
          Create, review, and archive workspaces. Archived workspaces cannot be
          selected for business requests.
        </p>
      </div>
      <form
        className="flex flex-col gap-3 rounded-3xl border border-white/10 bg-white/[0.045] p-5 md:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          createMutation.mutate();
        }}
      >
        <input
          className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
          onChange={(event) => setName(event.target.value)}
          placeholder="Workspace name"
          value={name}
        />
        <button
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60"
          disabled={!name.trim() || createMutation.isPending}
          type="submit"
        >
          Create Workspace
        </button>
      </form>
      {createMutation.isError ? (
        <div className="rounded-2xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
          {errorCopy(createMutation.error)}
        </div>
      ) : null}
      {archiveMutation.isError ? (
        <div className="rounded-2xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
          {errorCopy(archiveMutation.error)}
        </div>
      ) : null}
      {renameMutation.isError ? (
        <div className="rounded-2xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container">
          {errorCopy(renameMutation.error)}
        </div>
      ) : null}
      <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
        {query.isLoading ? (
          <p className="text-sm text-text-muted">Loading workspaces…</p>
        ) : null}
        {query.isError ? (
          <p className="text-sm text-error">{errorCopy(query.error)}</p>
        ) : null}
        <div className="space-y-3">
          {query.data?.workspaces.map((workspace) => (
            <div
              className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/15 p-4"
              key={workspace.id}
            >
              <div>
                <p className="font-semibold text-white">{workspace.name}</p>
                <p className="mt-1 font-mono text-xs text-secondary">
                  {workspace.status}
                </p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                {editingWorkspaceId === workspace.id ? (
                  <form
                    className="flex flex-wrap gap-2"
                    onSubmit={(event) => {
                      event.preventDefault();
                      renameMutation.mutate();
                    }}
                  >
                    <input
                      aria-label={`Rename ${workspace.name}`}
                      className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
                      onChange={(event) => setRenameName(event.target.value)}
                      value={renameName}
                    />
                    <button
                      className="rounded-xl bg-primary px-3 py-2 text-sm font-semibold text-on-primary disabled:opacity-50"
                      disabled={!renameName.trim() || renameMutation.isPending}
                      type="submit"
                    >
                      Save
                    </button>
                    <button
                      className="rounded-xl border border-white/10 px-3 py-2 text-sm text-text-main"
                      onClick={() => setEditingWorkspaceId(null)}
                      type="button"
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <button
                    className="rounded-xl border border-white/10 px-3 py-2 text-sm text-text-main disabled:opacity-50"
                    disabled={workspace.status === "archived"}
                    onClick={() => {
                      setEditingWorkspaceId(workspace.id);
                      setRenameName(workspace.name);
                    }}
                    type="button"
                  >
                    Rename
                  </button>
                )}
                <button
                  className="rounded-xl border border-white/10 px-3 py-2 text-sm text-text-main disabled:opacity-50"
                  disabled={
                    workspace.status === "archived" ||
                    archiveMutation.isPending
                  }
                  onClick={() => archiveMutation.mutate(workspace.id)}
                  type="button"
                >
                  Archive
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
