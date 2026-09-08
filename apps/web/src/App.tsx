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
import { AppLayout } from "./app/layouts/app-layout";
import { OverviewPage } from "./features/overview/pages/overview-page";
import { AdminSetupStatusPage } from "./features/admin/pages/setup-status-page";

function LoadingPage() {
  return (
    <main>
      <p>Loading SurgePilot…</p>
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

  let page: React.ReactNode;
  if (pathname === "/assets/env-groups") {
    page = <EnvGroupsPage />;
  } else if (pathname === "/assets/dependency-files") {
    page = <DependencyFilesPage />;
  } else if (pathname === "/resources/load-nodes/new") {
    page = <RegisterLoadNodePage />;
  } else if (pathname === "/resources/load-nodes") {
    page = <LoadNodesPage />;
  } else if (pathname.startsWith("/scenarios/")) {
    page = <ScenarioDesignerPage />;
  } else if (pathname === "/scenarios") {
    page = <ScenarioListPage />;
  } else if (pathname.startsWith("/test-plans/")) {
    page = <TestPlanEditorPage />;
  } else if (pathname === "/test-plans") {
    page = <TestPlanListPage />;
  } else if (pathname === "/runs") {
    page = <RunListPage />;
  } else if (pathname.startsWith("/runs/")) {
    const runId = decodeURIComponent(pathname.slice("/runs/".length));
    page = <RunReportPage runId={runId} />;
  } else if (pathname === "/admin/setup-status") {
    page = <AdminSetupStatusPage />;
  } else {
    page = <OverviewPage />;
  }
  return <AppLayout pathname={pathname}>{page}</AppLayout>;
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
