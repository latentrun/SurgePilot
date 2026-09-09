import { useState } from "react";

import { useAuthSession } from "../auth-session";
import type { WorkspaceSwitchGuard } from "../workspace-switch-guard";

type NavItem = {
  label: string;
  path: string;
};

type NavGroup = {
  items: NavItem[];
  label: string;
};

const primaryGroup: NavGroup = {
  label: "Primary",
  items: [
    { label: "Overview", path: "/overview" },
    { label: "Scenarios", path: "/scenarios" },
    { label: "Test Plans", path: "/test-plans" },
    { label: "Runs", path: "/runs" },
  ],
};

const assetsGroup: NavGroup = {
  label: "Assets",
  items: [
    { label: "Env Groups", path: "/assets/env-groups" },
    { label: "Dependency Files", path: "/assets/dependency-files" },
  ],
};

const resourcesGroup: NavGroup = {
  label: "Resources",
  items: [{ label: "Load Nodes", path: "/resources/load-nodes" }],
};

const adminGroup: NavGroup = {
  label: "Admin",
  items: [
    { label: "Setup Status", path: "/admin/setup-status" },
    { label: "Workspaces", path: "/admin/workspaces" },
    { label: "Users", path: "/admin/users" },
    { label: "System Settings", path: "/admin/system-settings" },
  ],
};

function isNavItemActive(pathname: string, item: NavItem) {
  if (item.path === "/overview") {
    return pathname === "/overview" || pathname === "/";
  }
  return pathname.startsWith(item.path);
}

export function AppLayout({
  children,
  pathname,
  workspaceSwitchGuard,
}: Readonly<{
  children: React.ReactNode;
  pathname: string;
  workspaceSwitchGuard: WorkspaceSwitchGuard | null;
}>) {
  const { session, signOut, switchWorkspace } = useAuthSession();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isSwitchingWorkspace, setIsSwitchingWorkspace] = useState(false);
  const [pendingWorkspaceId, setPendingWorkspaceId] = useState<string | null>(null);

  if (session === null) {
    return null;
  }

  const groups: NavGroup[] = [
    primaryGroup,
    assetsGroup,
    resourcesGroup,
  ];
  if (session.user.role === "admin") {
    groups.push(adminGroup);
  }

  async function handleLogout() {
    setIsSigningOut(true);
    try {
      await signOut();
      window.history.replaceState({}, "", "/login");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch {
      // Keep the authenticated view visible if the server could not complete logout.
    } finally {
      setIsSigningOut(false);
    }
  }

  async function performWorkspaceSwitch(
    workspaceId: string,
    guard: WorkspaceSwitchGuard | null = null,
  ) {
    setIsSwitchingWorkspace(true);
    try {
      await switchWorkspace(workspaceId);
      guard?.onAbandon?.();
      window.history.replaceState({}, "", guard?.safePath ?? "/overview");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } finally {
      setIsSwitchingWorkspace(false);
    }
  }

  function handleWorkspaceChange(workspaceId: string) {
    if (workspaceId === session.currentWorkspace.id) return;
    if (workspaceSwitchGuard?.dirty) {
      setPendingWorkspaceId(workspaceId);
      return;
    }
    void performWorkspaceSwitch(workspaceId);
  }

  return (
    <div>
      <aside>
        <div>
          <a href="/overview">
            <strong>SurgePilot</strong>
            <small>Performance testing</small>
          </a>
        </div>
        <nav aria-label="Primary navigation">
          {groups.map((group) => (
            <div key={group.label}>
              {group.label === "Primary" ? null : (
                <div>{group.label}</div>
              )}
              <div>
                {group.items.map((item) => (
                  <a
                    aria-current={
                      isNavItemActive(pathname, item) ? "page" : undefined
                    }
                    href={item.path}
                    key={item.path}
                  >
                    {item.label}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div>
          <label>
            Workspace
            <select
              aria-label="Current workspace"
              disabled={isSwitchingWorkspace}
              onChange={(event) => handleWorkspaceChange(event.target.value)}
              value={session.currentWorkspace.id}
            >
              {session.availableWorkspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
          <div>Signed in as {session.user.displayName}</div>
          <button
            disabled={isSigningOut}
            onClick={() => void handleLogout()}
            type="button"
          >
            {isSigningOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>
      <div>{children}</div>
      {pendingWorkspaceId !== null ? (
        <div role="dialog" aria-labelledby="workspace-switch-title">
          <h2 id="workspace-switch-title">Switch workspace?</h2>
          <p>This page has unsaved changes. Abandon them before switching workspaces, or cancel to keep editing.</p>
          <button onClick={() => setPendingWorkspaceId(null)} type="button">Cancel switch</button>
          <button
            disabled={isSwitchingWorkspace}
            onClick={() => {
              const target = pendingWorkspaceId;
              const guard = workspaceSwitchGuard;
              setPendingWorkspaceId(null);
              void performWorkspaceSwitch(target, guard);
            }}
            type="button"
          >
            Abandon and switch
          </button>
        </div>
      ) : null}
    </div>
  );
}
