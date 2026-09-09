import { useEffect, useState } from "react";

import {
  ApiError, createAdminUser, getCsrfToken, listAdminUsers, listAdminWorkspaces,
  patchAdminUser, replaceAdminUserWorkspaces, resetAdminUserPassword,
  type AdminUserSummary, type WorkspaceSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

export function AdminUsersPage() {
  const { csrfToken, session } = useAuthSession();
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [q, setQ] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "user">("user");
  const [error, setError] = useState<string | null>(null);
  const isAdmin = session?.permissions.canManageUsers === true;
  const token = async () => csrfToken ?? (await getCsrfToken()).csrfToken;
  async function load() {
    try { const [userResult, workspaceResult] = await Promise.all([listAdminUsers(q || undefined), listAdminWorkspaces("active")]); setUsers(userResult.users); setWorkspaces(workspaceResult.workspaces); setError(null); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Users could not be loaded."); }
  }
  useEffect(() => { if (isAdmin) void load(); }, [isAdmin, q]);
  if (!isAdmin) return <AdminForbidden />;
  async function create(event: React.FormEvent) {
    event.preventDefault();
    try { await createAdminUser({ email, displayName, password, role, status: "active", workspaceIds: [] }, await token()); setEmail(""); setDisplayName(""); setPassword(""); await load(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "User could not be created."); }
  }
  async function update(userId: string, payload: Parameters<typeof patchAdminUser>[1]) {
    try { await patchAdminUser(userId, payload, await token()); await load(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "User could not be updated."); }
  }
  async function toggleWorkspace(user: AdminUserSummary, workspaceId: string) {
    const ids = new Set(user.workspaceIds ?? []); ids.has(workspaceId) ? ids.delete(workspaceId) : ids.add(workspaceId);
    try { await replaceAdminUserWorkspaces(user.id, [...ids], await token()); await load(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Membership could not be updated."); }
  }
  async function resetPassword(userId: string) {
    const next = window.prompt("New password");
    if (!next) return;
    try { await resetAdminUserPassword(userId, next, await token()); setError(null); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Password could not be reset."); }
  }
  return <section>
    <h1>Users</h1><p>Manage local users, roles, status, and workspace access.</p>
    <form onSubmit={(event) => void create(event)}>
      <input aria-label="Email" onChange={(event) => setEmail(event.target.value)} placeholder="Email" value={email} />
      <input aria-label="Display name" onChange={(event) => setDisplayName(event.target.value)} placeholder="Display name" value={displayName} />
      <input aria-label="Initial password" onChange={(event) => setPassword(event.target.value)} placeholder="Initial password" type="password" value={password} />
      <select aria-label="New user role" onChange={(event) => setRole(event.target.value as "admin" | "user")} value={role}><option value="user">User</option><option value="admin">Admin</option></select>
      <button disabled={!email || !displayName || !password} type="submit">Create User</button>
    </form>
    <label>Search users <input onChange={(event) => setQ(event.target.value)} value={q} /></label>
    {error ? <p role="alert">{error}</p> : null}
    <ul>{users.map((user) => <li key={user.id}>
      <strong>{user.displayName}</strong> — {user.email} · {user.status}
      <select aria-label={`Role for ${user.email}`} onChange={(event) => void update(user.id, { role: event.target.value as "admin" | "user" })} value={user.role}><option value="user">User</option><option value="admin">Admin</option></select>
      <button onClick={() => void update(user.id, { status: user.status === "active" ? "disabled" : "active" })} type="button">{user.status === "active" ? "Disable" : "Enable"}</button>
      <button onClick={() => void resetPassword(user.id)} type="button">Reset password</button>
      <span>{workspaces.map((workspace) => <label key={workspace.id}><input checked={(user.workspaceIds ?? []).includes(workspace.id)} onChange={() => void toggleWorkspace(user, workspace.id)} type="checkbox" />{workspace.name}</label>)}</span>
    </li>)}</ul>
  </section>;
}
