import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  ApiError,
  createAdminUser,
  getCsrfToken,
  listAdminUsers,
  listAdminWorkspaces,
  patchAdminUser,
  replaceAdminUserWorkspaces,
  resetAdminUserPassword,
  type AdminUserSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

function errorCopy(error: unknown) {
  if (error instanceof ApiError) {
    return `Request failed. Error code: ${error.body.code}. Request ID: ${error.body.requestId}.`;
  }
  return "Request failed. Refresh and try again.";
}

function hasWorkspace(user: AdminUserSummary, workspaceId: string) {
  return (user.workspaceIds ?? []).includes(workspaceId);
}

export function AdminUsersPage() {
  const { csrfToken, session } = useAuthSession();
  const queryClient = useQueryClient();
  const isAdmin = session?.permissions.canManageUsers === true;
  const [q, setQ] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");
  const [workspaceId, setWorkspaceId] = useState("");
  const [resetPasswordByUserId, setResetPasswordByUserId] = useState<
    Record<string, string>
  >({});
  const users = useQuery({
    enabled: isAdmin,
    queryKey: ["admin-users", q],
    queryFn: () => listAdminUsers(q || undefined),
  });
  const workspaces = useQuery({
    enabled: isAdmin,
    queryKey: ["admin-user-workspaces"],
    queryFn: () => listAdminWorkspaces("active"),
  });
  const firstWorkspaceId =
    workspaceId || workspaces.data?.workspaces[0]?.id || "";
  const getWriteToken = async () => csrfToken ?? (await getCsrfToken()).csrfToken;
  const createMutation = useMutation({
    mutationFn: async () =>
      createAdminUser(
        {
          email,
          displayName,
          password,
          role,
          status: "active",
          workspaceIds: role === "admin" ? [] : [firstWorkspaceId],
        },
        await getWriteToken(),
      ),
    onSuccess: async () => {
      setEmail("");
      setDisplayName("");
      setPassword("");
      setRole("user");
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
  const patchMutation = useMutation({
    mutationFn: async ({
      userId,
      role: nextRole,
      status,
    }: {
      userId: string;
      role?: "admin" | "user";
      status?: "active" | "disabled";
    }) => patchAdminUser(userId, { role: nextRole, status }, await getWriteToken()),
    onSuccess: async () =>
      queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });
  const membershipMutation = useMutation({
    mutationFn: async ({
      user,
      workspaceId: changedWorkspaceId,
    }: {
      user: AdminUserSummary;
      workspaceId: string;
    }) => {
      const current = new Set(user.workspaceIds ?? []);
      if (current.has(changedWorkspaceId)) {
        current.delete(changedWorkspaceId);
      } else {
        current.add(changedWorkspaceId);
      }
      return replaceAdminUserWorkspaces(user.id, [...current], await getWriteToken());
    },
    onSuccess: async () =>
      queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });
  const resetMutation = useMutation({
    mutationFn: async (userId: string) =>
      resetAdminUserPassword(
        userId,
        resetPasswordByUserId[userId] ?? "",
        await getWriteToken(),
      ),
    onSuccess: async (_result, userId) => {
      setResetPasswordByUserId((current) => ({ ...current, [userId]: "" }));
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  if (!isAdmin) {
    return <AdminForbidden />;
  }

  return (
    <section className="mx-auto flex max-w-6xl flex-col gap-6">
      <div className="surgepilot-glass rounded-3xl p-7">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-secondary">
          Admin
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-white">
          Users
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
          Create local users, manage global roles, reset passwords, and update
          workspace access. Passwords are never shown after submission.
        </p>
      </div>
      <form
        className="grid gap-3 rounded-3xl border border-white/10 bg-white/[0.045] p-5 md:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          createMutation.mutate();
        }}
      >
        <input
          className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Email"
          value={email}
        />
        <input
          className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
          onChange={(event) => setDisplayName(event.target.value)}
          placeholder="Display name"
          value={displayName}
        />
        <input
          className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Initial password"
          type="password"
          value={password}
        />
        <select
          aria-label="New user role"
          className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
          onChange={(event) => setRole(event.target.value as "admin" | "user")}
          value={role}
        >
          <option className="bg-surface" value="user">
            User
          </option>
          <option className="bg-surface" value="admin">
            Admin
          </option>
        </select>
        {role === "user" ? (
          <select
            aria-label="Initial workspace"
            className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white md:col-span-2"
            onChange={(event) => setWorkspaceId(event.target.value)}
            value={firstWorkspaceId}
          >
            {workspaces.data?.workspaces.map((workspace) => (
              <option
                className="bg-surface"
                key={workspace.id}
                value={workspace.id}
              >
                {workspace.name}
              </option>
            ))}
          </select>
        ) : null}
        <button
          className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60 md:col-span-2"
          disabled={
            !email ||
            !displayName ||
            !password ||
            (role === "user" && !firstWorkspaceId) ||
            createMutation.isPending
          }
          type="submit"
        >
          Create User
        </button>
      </form>
      {[createMutation, patchMutation, membershipMutation, resetMutation].map(
        (mutation, index) =>
          mutation.isError ? (
            <div
              className="rounded-2xl border border-error/30 bg-error-container p-4 text-sm text-on-error-container"
              key={index}
            >
              {errorCopy(mutation.error)}
            </div>
          ) : null,
      )}
      <div className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
        <label className="block text-sm text-text-muted">
          Search users
          <input
            className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
            onChange={(event) => setQ(event.target.value)}
            placeholder="Email or display name"
            value={q}
          />
        </label>
      </div>
      <div className="space-y-3 rounded-3xl border border-white/10 bg-white/[0.045] p-5">
        {users.isLoading ? (
          <p className="text-sm text-text-muted">Loading users…</p>
        ) : null}
        {users.data?.users.map((user) => (
          <div
            className="grid gap-4 rounded-2xl border border-white/10 bg-black/15 p-4 lg:grid-cols-[1fr_auto]"
            key={user.id}
          >
            <div>
              <p className="font-semibold text-white">{user.displayName}</p>
              <p className="mt-1 text-sm text-text-muted">
                {user.email} · {user.role} · {user.status}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {workspaces.data?.workspaces.map((workspace) => (
                  <label
                    className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1 text-xs text-text-main"
                    key={workspace.id}
                  >
                    <input
                      checked={hasWorkspace(user, workspace.id)}
                      disabled={membershipMutation.isPending}
                      onChange={() =>
                        membershipMutation.mutate({ user, workspaceId: workspace.id })
                      }
                      type="checkbox"
                    />
                    {workspace.name}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2 lg:min-w-72">
              <select
                aria-label={`Role for ${user.email}`}
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
                disabled={patchMutation.isPending}
                onChange={(event) =>
                  patchMutation.mutate({
                    userId: user.id,
                    role: event.target.value as "admin" | "user",
                  })
                }
                value={user.role}
              >
                <option className="bg-surface" value="user">
                  User
                </option>
                <option className="bg-surface" value="admin">
                  Admin
                </option>
              </select>
              <button
                className="rounded-xl border border-white/10 px-3 py-2 text-sm text-text-main disabled:opacity-50"
                disabled={patchMutation.isPending}
                onClick={() =>
                  patchMutation.mutate({
                    userId: user.id,
                    status: user.status === "active" ? "disabled" : "active",
                  })
                }
                type="button"
              >
                {user.status === "active" ? "Disable" : "Enable"}
              </button>
              <div className="flex gap-2">
                <input
                  aria-label={`New password for ${user.email}`}
                  className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
                  onChange={(event) =>
                    setResetPasswordByUserId((current) => ({
                      ...current,
                      [user.id]: event.target.value,
                    }))
                  }
                  placeholder="New password"
                  type="password"
                  value={resetPasswordByUserId[user.id] ?? ""}
                />
                <button
                  className="rounded-xl border border-white/10 px-3 py-2 text-sm text-text-main disabled:opacity-50"
                  disabled={
                    !(resetPasswordByUserId[user.id] ?? "") ||
                    resetMutation.isPending
                  }
                  onClick={() => resetMutation.mutate(user.id)}
                  type="button"
                >
                  Reset
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
