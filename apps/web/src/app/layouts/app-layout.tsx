import { useState } from "react";

import { useAuthSession } from "../auth-session";

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
  items: [{ label: "Setup Status", path: "/admin/setup-status" }],
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
}: Readonly<{ children: React.ReactNode; pathname: string }>) {
  const { session, signOut } = useAuthSession();
  const [isSigningOut, setIsSigningOut] = useState(false);

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
          <div>{session.defaultWorkspace.name}</div>
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
    </div>
  );
}
