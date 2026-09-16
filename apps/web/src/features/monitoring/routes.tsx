import type { RouteObject } from "react-router-dom";

export const monitoringRoutes: RouteObject[] = [
  {
    path: "/observability/monitoring",
    lazy: async () => {
      const { MonitoringPage } = await import("./pages/monitoring-page");
      return { Component: MonitoringPage };
    },
  },
];
