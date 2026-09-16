import {
  isRouteErrorResponse,
  Navigate,
  Outlet,
  useRouteError,
  type RouteObject,
} from "react-router-dom";

import { useAuthSession } from "./auth-session";
import { AppLayout } from "./layouts/app-layout";
import { LoadingPage } from "./layouts/loading-page";
import { LoginPage } from "../features/auth/pages/login-page";
import { EnvGroupsPage } from "../features/env-groups/pages/env-groups-page";
import { DependencyFilesPage } from "../features/dependency-files/pages/dependency-files-page";
import { RegisterPage } from "../features/auth/pages/register-page";
import { OverviewPage } from "../features/overview/pages/overview-page";
import { LoadNodesPage } from "../features/load-nodes/pages/load-nodes-page";
import { RegisterLoadNodePage } from "../features/load-nodes/pages/register-load-node-page";
import { AdminSetupStatusPage } from "../features/admin/pages/setup-status-page";
import { AdminSystemSettingsPage } from "../features/admin/pages/system-settings-page";
import { AdminUsersPage } from "../features/admin/pages/users-page";
import { AdminWorkspacesPage } from "../features/admin/pages/workspaces-page";
import { scenarioRoutes } from "../features/scenarios/routes";
import { testPlanRoutes } from "../features/test-plans/routes";
import { runRoutes } from "../features/runs/routes";
import { monitoringRoutes } from "../features/monitoring/routes";
import { apiCatalogRoutes } from "../features/api-catalog/routes";
import { accountRoutes } from "../features/account/routes";
import { marketingRoutes } from "../features/marketing/routes";
import { helpRoutes } from "../features/help/routes";

function RequireAuth() {
  const { isAuthenticated, isRestoring, postLogoutRedirectPath } =
    useAuthSession();

  if (isRestoring) {
    return <LoadingPage />;
  }
  if (!isAuthenticated) {
    return <Navigate to={postLogoutRedirectPath ?? "/login"} replace />;
  }
  return <Outlet />;
}

function PublicOnly() {
  const { isAuthenticated, isRestoring } = useAuthSession();

  if (isRestoring) {
    return <LoadingPage />;
  }
  if (isAuthenticated) {
    return <Navigate to="/overview" replace />;
  }
  return <Outlet />;
}

function RouteErrorElement() {
  const error = useRouteError();
  const detail = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : "Unexpected application error";

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-6 text-text-main">
      <section className="max-w-md rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-xl">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-secondary">
          SurgePilot
        </p>
        <h1 className="mt-3 text-2xl font-semibold text-white">
          Something went wrong
        </h1>
        <p className="mt-3 text-sm leading-6 text-text-muted">
          Refresh the page and try again. If the problem persists, contact an
          administrator.
        </p>
        <p className="mt-4 font-mono text-xs text-secondary">{detail}</p>
      </section>
    </main>
  );
}

export const routes: RouteObject[] = [
  ...marketingRoutes,
  {
    element: <PublicOnly />,
    errorElement: <RouteErrorElement />,
    children: [
      {
        path: "/login",
        element: <LoginPage />,
      },
      {
        path: "/register",
        element: <RegisterPage />,
      },
    ],
  },
  {
    element: <RequireAuth />,
    errorElement: <RouteErrorElement />,
    children: [
      {
        element: <AppLayout />,
        children: [
          {
            path: "/overview",
            element: <OverviewPage />,
          },
          ...scenarioRoutes,
          ...testPlanRoutes,
          ...runRoutes,
          ...monitoringRoutes,
          ...apiCatalogRoutes,
          ...accountRoutes,
          ...helpRoutes,
          {
            path: "/assets/env-groups",
            element: <EnvGroupsPage />,
          },
          {
            path: "/assets/dependency-files",
            element: <DependencyFilesPage />,
          },
          {
            path: "/resources/load-nodes",
            element: <LoadNodesPage />,
          },
          {
            path: "/resources/load-nodes/new",
            element: <RegisterLoadNodePage />,
          },
          {
            path: "/admin",
            element: <Navigate to="/admin/setup-status" replace />,
          },
          {
            path: "/admin/setup-status",
            element: <AdminSetupStatusPage />,
          },
          {
            path: "/admin/workspaces",
            element: <AdminWorkspacesPage />,
          },
          {
            path: "/admin/users",
            element: <AdminUsersPage />,
          },
          {
            path: "/admin/system-settings",
            element: <AdminSystemSettingsPage />,
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to="/overview" replace />,
  },
];
