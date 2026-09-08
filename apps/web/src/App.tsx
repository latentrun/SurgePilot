import { useEffect, useState } from "react";

import { AuthSessionProvider, useAuthSession } from "./app/auth-session";
import {
  WorkspaceSwitchGuardProvider,
  type WorkspaceSwitchGuard,
} from "./app/workspace-switch-guard";
import { LoginPage } from "./features/auth/pages/login-page";
import { RegisterPage } from "./features/auth/pages/register-page";
import { EnvGroupsPage } from "./features/env-groups/pages/env-groups-page";
import { DependencyFilesPage } from "./features/dependency-files/pages/dependency-files-page";
import { LoadNodesPage } from "./features/load-nodes/pages/load-nodes-page";
import { RegisterLoadNodePage } from "./features/load-nodes/pages/register-load-node-page";
import { ScenarioListPage } from "./features/scenarios/pages/scenario-list-page";
import { ScenarioDesignerPage } from "./features/scenarios/pages/scenario-designer-page";
import { TestPlanListPage } from "./features/test-plans/pages/test-plan-list-page";
import { TestPlanEditorPage } from "./features/test-plans/pages/test-plan-editor-page";
import { RunListPage } from "./features/runs/pages/run-list-page";
import { RunReportPage } from "./features/runs/pages/run-report-page";

function LoadingPage() {
  return (
    <main>
      <p>Loading SurgePilot…</p>
    </main>
  );
}

function OverviewPage() {
  const { session, signOut } = useAuthSession();

  async function handleLogout() {
    try {
      await signOut();
      window.history.replaceState({}, "", "/login");
      window.dispatchEvent(new PopStateEvent("popstate"));
    } catch {
      // Keep the authenticated view visible if the server could not complete logout.
    }
  }

  if (!session) return null;
  return (
    <main>
      <p>Overview</p>
      <h1>Welcome to SurgePilot</h1>
      <p>Signed in as {session.user.displayName} ({session.user.email}).</p>
      <p>Workspace: {session.defaultWorkspace.name}</p>
      <nav>
        <a href="/assets/env-groups">Env Groups</a>
        <a href="/assets/dependency-files">Dependency Files</a>
        <a href="/resources/load-nodes">Load Nodes</a>
        <a href="/scenarios">Scenarios</a>
        <a href="/test-plans">Test Plans</a>
      </nav>
      <button onClick={() => void handleLogout()} type="button">
        Sign out
      </button>
    </main>
  );
}

function AppRoutes() {
  const { isAuthenticated, isRestoring } = useAuthSession();
  const [pathname, setPathname] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  if (isRestoring) return <LoadingPage />;
  if (!isAuthenticated) return pathname === "/register" ? <RegisterPage /> : <LoginPage />;
  if (pathname === "/assets/env-groups") return <EnvGroupsPage />;
  if (pathname === "/assets/dependency-files") return <DependencyFilesPage />;
  if (pathname === "/resources/load-nodes/new") {
    return <RegisterLoadNodePage />;
  }
  if (pathname === "/resources/load-nodes") return <LoadNodesPage />;
  if (pathname.startsWith("/scenarios/")) return <ScenarioDesignerPage />;
  if (pathname === "/scenarios") return <ScenarioListPage />;
  if (pathname.startsWith("/test-plans/")) return <TestPlanEditorPage />;
  if (pathname === "/test-plans") return <TestPlanListPage />;
  if (pathname === "/runs") return <RunListPage />;
  if (pathname.startsWith("/runs/")) {
    const runId = decodeURIComponent(pathname.slice("/runs/".length));
    return <RunReportPage runId={runId} />;
  }
  return <OverviewPage />;
}

export function App() {
  const [_guard, setGuard] = useState<WorkspaceSwitchGuard | null>(null);

  return (
    <AuthSessionProvider>
      <WorkspaceSwitchGuardProvider onGuardChange={setGuard}>
        <AppRoutes />
      </WorkspaceSwitchGuardProvider>
    </AuthSessionProvider>
  );
}
