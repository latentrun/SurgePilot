import { useState } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  Braces,
  Building2,
  ClipboardList,
  CircleUserRound,
  CircleHelp,
  LogOut,
  Files,
  KeyRound,
  Library,
  LayoutDashboard,
  LineChart,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  UsersRound,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import { useAuthSession } from "../auth-session";
import {
  WorkspaceSwitchGuardProvider,
  type WorkspaceSwitchGuard,
} from "../workspace-switch-guard";
import { SurgePilotLogo } from "../../components/surgepilot-logo";

type NavItem = {
  label: string;
  path: string;
  Icon: LucideIcon;
};

const primaryNav: NavItem[] = [
  { label: "Overview", path: "/overview", Icon: LayoutDashboard },
  { label: "Scenarios", path: "/scenarios", Icon: Workflow },
  { label: "Test Plans", path: "/test-plans", Icon: ClipboardList },
  { label: "Runs", path: "/runs", Icon: Activity },
];

const assetNav: NavItem[] = [
  { label: "Env Groups", path: "/assets/env-groups", Icon: Braces },
  { label: "Dependency Files", path: "/assets/dependency-files", Icon: Files },
  { label: "API Catalog", path: "/api-catalog", Icon: Library },
];

const resourceNav: NavItem[] = [
  { label: "Load Nodes", path: "/resources/load-nodes", Icon: Server },
];

const observabilityNav: NavItem[] = [
  { label: "Monitoring", path: "/observability/monitoring", Icon: LineChart },
];

const accountNav: NavItem[] = [
  { label: "API Keys", path: "/account/api-keys", Icon: KeyRound },
];

const supportNav: NavItem[] = [
  { label: "Help", path: "/help", Icon: CircleHelp },
];

const adminNav: NavItem[] = [
  { label: "Setup Status", path: "/admin/setup-status", Icon: ShieldCheck },
  { label: "Workspaces", path: "/admin/workspaces", Icon: Building2 },
  { label: "Users", path: "/admin/users", Icon: UsersRound },
  {
    label: "System Settings",
    path: "/admin/system-settings",
    Icon: SlidersHorizontal,
  },
];

function currentCrumbs(pathname: string) {
  if (pathname.startsWith("/scenarios")) {
    return ["Scenarios"];
  }
  if (pathname.startsWith("/test-plans")) {
    return ["Test Plans"];
  }
  if (pathname.startsWith("/runs")) {
    return ["Runs"];
  }
  if (pathname.startsWith("/assets/env-groups")) {
    return ["Assets", "Env Groups"];
  }
  if (pathname.startsWith("/assets/dependency-files")) {
    return ["Assets", "Dependency Files"];
  }
  if (pathname.startsWith("/api-catalog")) {
    return ["Assets", "API Catalog"];
  }
  if (pathname.startsWith("/resources/load-nodes/new")) {
    return ["Resources", "Load Nodes", "Register"];
  }
  if (pathname.startsWith("/resources/load-nodes")) {
    return ["Resources", "Load Nodes"];
  }
  if (pathname.startsWith("/observability/monitoring")) {
    return ["Observability", "Monitoring"];
  }
  if (pathname.startsWith("/admin/workspaces")) {
    return ["Admin", "Workspaces"];
  }
  if (pathname.startsWith("/admin/users")) {
    return ["Admin", "Users"];
  }
  if (pathname.startsWith("/admin/system-settings")) {
    return ["Admin", "System Settings"];
  }
  if (pathname.startsWith("/admin/setup-status")) {
    return ["Admin", "Setup Status"];
  }
  if (pathname.startsWith("/account/api-keys")) {
    return ["Account", "API Keys"];
  }
  if (pathname.startsWith("/help")) {
    return ["Help"];
  }
  return ["Overview"];
}

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { session, signOut, switchWorkspace } = useAuthSession();
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isSwitchingWorkspace, setIsSwitchingWorkspace] = useState(false);
  const [workspaceSwitchGuard, setWorkspaceSwitchGuard] =
    useState<WorkspaceSwitchGuard | null>(null);
  const [pendingWorkspaceId, setPendingWorkspaceId] = useState<string | null>(
    null,
  );

  if (session === null) {
    return null;
  }

  const activeSession = session;
  const crumbs = currentCrumbs(location.pathname);
  const isMonitoringPage = location.pathname.startsWith(
    "/observability/monitoring",
  );
  const isApiCatalogDetailPage = /^\/api-catalog\/[^/]+/.test(
    location.pathname,
  );
  const usesEmbeddedContentLayout = isMonitoringPage || isApiCatalogDetailPage;

  async function performWorkspaceSwitch(
    workspaceId: string,
    safePath = "/overview",
    onAbandon?: () => void,
  ) {
    setIsSwitchingWorkspace(true);
    try {
      await switchWorkspace(workspaceId);
      onAbandon?.();
      navigate(safePath, { replace: true });
    } finally {
      setIsSwitchingWorkspace(false);
    }
  }

  function handleWorkspaceChange(workspaceId: string) {
    if (workspaceId === activeSession.currentWorkspace.id) {
      return;
    }
    if (workspaceSwitchGuard?.dirty) {
      setPendingWorkspaceId(workspaceId);
      return;
    }
    void performWorkspaceSwitch(workspaceId);
  }

  async function handleLogout() {
    setIsSigningOut(true);
    try {
      await signOut({ redirectPath: "/" });
    } finally {
      setIsSigningOut(false);
    }
  }

  return (
    <div className="surgepilot-aurora-surface min-h-screen bg-background text-text-main">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[248px] flex-col border-r border-white/10 bg-surface-container-low backdrop-blur-xl md:flex">
        <div className="px-6 pb-4 pt-6">
          <Link className="flex items-center gap-3" to="/overview">
            <span className="grid h-9 w-9 place-items-center rounded-lg shadow-[0_0_18px_rgba(34,211,238,0.16)]">
              <SurgePilotLogo className="h-9 w-9 rounded-lg" decorative />
            </span>
            <span>
              <span className="block font-display text-lg font-semibold leading-6 text-white">
                SurgePilot
              </span>
              <span className="block font-mono text-[10px] uppercase leading-4 tracking-[0.22em] text-secondary">
                Performance testing
              </span>
            </span>
          </Link>
        </div>

        <nav aria-label="Primary navigation" className="surgepilot-sidebar-scroll min-h-0 flex-1 overflow-y-auto px-2 py-3">
          <div className="space-y-1">
            {primaryNav.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                      : "text-text-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")
                }
                key={item.path}
                to={item.path}
              >
                <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                  <item.Icon
                    aria-hidden
                    className="h-4 w-4"
                    strokeWidth={1.8}
                  />
                </span>
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="px-4 pb-2 pt-5 font-mono text-[10px] font-semibold uppercase leading-4 tracking-[0.22em] text-secondary/70">
            Assets
          </div>
          <div className="space-y-1">
            {assetNav.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                      : "text-text-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")
                }
                key={item.path}
                to={item.path}
              >
                <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                  <item.Icon
                    aria-hidden
                    className="h-4 w-4"
                    strokeWidth={1.8}
                  />
                </span>
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="px-4 pb-2 pt-5 font-mono text-[10px] font-semibold uppercase leading-4 tracking-[0.22em] text-secondary/70">
            Resources
          </div>
          <div className="space-y-1">
            {resourceNav.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                      : "text-text-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")
                }
                key={item.path}
                to={item.path}
              >
                <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                  <item.Icon
                    aria-hidden
                    className="h-4 w-4"
                    strokeWidth={1.8}
                  />
                </span>
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="px-4 pb-2 pt-5 font-mono text-[10px] font-semibold uppercase leading-4 tracking-[0.22em] text-secondary/70">
            Observability
          </div>
          <div className="space-y-1">
            {observabilityNav.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                      : "text-text-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")
                }
                key={item.path}
                to={item.path}
              >
                <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                  <item.Icon
                    aria-hidden
                    className="h-4 w-4"
                    strokeWidth={1.8}
                  />
                </span>
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="px-4 pb-2 pt-5 font-mono text-[10px] font-semibold uppercase leading-4 tracking-[0.22em] text-secondary/70">
            Account
          </div>
          <div className="space-y-1">
            {accountNav.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                      : "text-text-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")
                }
                key={item.path}
                to={item.path}
              >
                <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                  <item.Icon
                    aria-hidden
                    className="h-4 w-4"
                    strokeWidth={1.8}
                  />
                </span>
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="px-4 pb-2 pt-5 font-mono text-[10px] font-semibold uppercase leading-4 tracking-[0.22em] text-secondary/70">
            Support
          </div>
          <div className="space-y-1">
            {supportNav.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  [
                    "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                    isActive
                      ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                      : "text-text-muted hover:bg-white/5 hover:text-white",
                  ].join(" ")
                }
                key={item.path}
                to={item.path}
              >
                <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                  <item.Icon
                    aria-hidden
                    className="h-4 w-4"
                    strokeWidth={1.8}
                  />
                </span>
                {item.label}
              </NavLink>
            ))}
          </div>

          {activeSession.user.role === "admin" ? (
            <>
              <div className="px-4 pb-2 pt-5 font-mono text-[10px] font-semibold uppercase leading-4 tracking-[0.22em] text-secondary/70">
                Admin
              </div>
              <div className="space-y-1">
                {adminNav.map((item) => (
                  <NavLink
                    className={({ isActive }) =>
                      [
                        "flex items-center gap-3 rounded-r-md px-4 py-2 text-sm font-medium transition",
                        isActive
                          ? "border-l-2 border-primary-container bg-primary-container/10 text-white shadow-[-10px_0_20px_-12px_rgba(34,211,238,0.65)]"
                          : "text-text-muted hover:bg-white/5 hover:text-white",
                      ].join(" ")
                    }
                    key={item.path}
                    to={item.path}
                  >
                    <span className="grid h-6 w-6 place-items-center rounded-md border border-white/10 text-primary">
                      <item.Icon
                        aria-hidden
                        className="h-4 w-4"
                        strokeWidth={1.8}
                      />
                    </span>
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </>
          ) : null}
        </nav>

      </aside>

      <header
        aria-label="Global top bar"
        className="fixed left-0 right-0 top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-surface-container-low px-4 backdrop-blur-xl md:left-[248px] md:px-6"
      >
        <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
          {crumbs.map((crumb, index) => (
            <span className="flex min-w-0 items-center gap-2" key={crumb}>
              {index > 0 ? <span className="text-secondary/50">/</span> : null}
              <span
                className={
                  index === crumbs.length - 1 ? "text-white" : "text-secondary"
                }
              >
                {crumb}
              </span>
            </span>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <label className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 sm:flex">
            <span
              aria-hidden
              className="h-2 w-2 rounded-full bg-success shadow-[0_0_8px_rgba(47,217,160,0.65)]"
            />
            <span className="sr-only">Current Workspace</span>
            <select
              aria-label="Current Workspace"
              className="max-w-[220px] bg-transparent font-mono text-[12px] leading-4 text-text-muted outline-none"
              disabled={isSwitchingWorkspace}
              onChange={(event) =>
                void handleWorkspaceChange(event.target.value)
              }
              value={activeSession.currentWorkspace.id}
            >
              {activeSession.availableWorkspaces.map((workspace) => (
                <option
                  className="bg-surface text-text-main"
                  key={workspace.id}
                  value={workspace.id}
                >
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <button
                aria-label={`Open user menu for ${activeSession.user.displayName}`}
                className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 bg-white/5 text-primary transition hover:border-primary/30 hover:bg-white/10 focus:outline-none focus:ring-2 focus:ring-primary/50"
                title={activeSession.user.displayName}
                type="button"
              >
                <CircleUserRound
                  aria-hidden
                  className="h-5 w-5"
                  strokeWidth={1.8}
                />
              </button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                className="z-50 min-w-56 rounded-2xl border border-white/10 bg-surface-container-low p-2 text-text-main shadow-2xl shadow-black/40 backdrop-blur-xl"
                sideOffset={10}
              >
                <DropdownMenu.Label className="px-3 py-2">
                  <span className="block truncate text-sm font-semibold text-white">
                    {activeSession.user.displayName}
                  </span>
                  <span className="mt-1 block text-xs text-text-muted">
                    Signed in
                  </span>
                </DropdownMenu.Label>
                <DropdownMenu.Separator className="my-1 h-px bg-white/10" />
                <DropdownMenu.Item asChild>
                  <button
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold text-text-main outline-none transition hover:bg-white/10 focus:bg-white/10 disabled:pointer-events-none disabled:opacity-60"
                    disabled={isSigningOut}
                    onClick={handleLogout}
                    type="button"
                  >
                    <LogOut aria-hidden className="h-4 w-4" strokeWidth={1.8} />
                    {isSigningOut ? "Logging out" : "Logout"}
                  </button>
                </DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </header>

      <main
        className={
          usesEmbeddedContentLayout
            ? "min-h-screen px-0 pb-0 pt-16 md:ml-[248px] md:px-0"
            : "min-h-screen px-4 pb-10 pt-24 md:ml-[248px] md:px-8"
        }
      >
        <WorkspaceSwitchGuardProvider onGuardChange={setWorkspaceSwitchGuard}>
          <Outlet />
        </WorkspaceSwitchGuardProvider>
      </main>
      {pendingWorkspaceId ? (
        <div
          aria-labelledby="workspace-switch-title"
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm"
          role="dialog"
        >
          <section className="w-full max-w-md rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-secondary">
              Unsaved changes
            </p>
            <h2
              className="mt-3 font-display text-2xl font-semibold text-white"
              id="workspace-switch-title"
            >
              Switch workspace?
            </h2>
            <p className="mt-3 text-sm leading-6 text-text-muted">
              This page has unsaved changes. Abandon them before switching
              workspaces, or cancel to keep editing in the current workspace.
            </p>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main"
                onClick={() => setPendingWorkspaceId(null)}
                type="button"
              >
                Cancel switch
              </button>
              <button
                className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60"
                disabled={isSwitchingWorkspace}
                onClick={() => {
                  const guard = workspaceSwitchGuard;
                  const targetWorkspaceId = pendingWorkspaceId;
                  setPendingWorkspaceId(null);
                  void performWorkspaceSwitch(
                    targetWorkspaceId,
                    guard?.safePath ?? "/overview",
                    guard?.onAbandon,
                  );
                }}
                type="button"
              >
                Abandon and switch
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
