import { useEffect, useState } from "react";

import {
  ApiError,
  archiveAdminWorkspace,
  createAdminWorkspace,
  getCsrfToken,
  listAdminWorkspaces,
  patchAdminWorkspace,
  type WorkspaceSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { AdminForbidden } from "../admin-access";

export function AdminWorkspacesPage() {
  const { csrfToken, refreshSession, session } = useAuthSession();
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [rename, setRename] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const isAdmin = session?.permissions.canManageWorkspaces === true;
  const token = async () => csrfToken ?? (await getCsrfToken()).csrfToken;

  async function load() {
    setLoading(true);
    try { setWorkspaces((await listAdminWorkspaces("all")).workspaces); setError(null); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Workspaces could not be loaded."); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (isAdmin) void load(); }, [isAdmin]);
  if (!isAdmin) return <AdminForbidden />;

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    try { await createAdminWorkspace({ name: name.trim() }, await token()); setName(""); await load(); await refreshSession(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Workspace could not be created."); }
  }
  async function save(workspaceId: string) {
    if (!rename.trim()) return;
    try { await patchAdminWorkspace(workspaceId, { name: rename.trim() }, await token()); setEditing(null); await load(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Workspace could not be renamed."); }
  }
  async function archive(workspaceId: string) {
    try { await archiveAdminWorkspace(workspaceId, await token()); await load(); }
    catch (cause) { setError(cause instanceof ApiError ? cause.message : "Workspace could not be archived."); }
  }

  return <section>
    <h1>Workspaces</h1>
    <p>Create, rename, and archive workspaces available to SurgePilot users.</p>
    <form onSubmit={(event) => void create(event)}>
      <label htmlFor="workspace-name">Workspace name</label>
      <input id="workspace-name" onChange={(event) => setName(event.target.value)} value={name} />
      <button disabled={!name.trim()} type="submit">Create Workspace</button>
    </form>
    {error ? <p role="alert">{error}</p> : null}
    {loading ? <p>Loading workspaces…</p> : null}
    <ul>
      {workspaces.map((workspace) => <li key={workspace.id}>
        {editing === workspace.id ? <>
          <input aria-label={`Rename ${workspace.name}`} onChange={(event) => setRename(event.target.value)} value={rename} />
          <button onClick={() => void save(workspace.id)} type="button">Save</button>
          <button onClick={() => setEditing(null)} type="button">Cancel</button>
        </> : <>
          <strong>{workspace.name}</strong> <small>{workspace.status ?? "active"}</small>
          <button disabled={workspace.status === "archived"} onClick={() => { setEditing(workspace.id); setRename(workspace.name); }} type="button">Rename</button>
          <button disabled={workspace.status === "archived"} onClick={() => void archive(workspace.id)} type="button">Archive</button>
        </>}
      </li>)}
    </ul>
  </section>;
}
