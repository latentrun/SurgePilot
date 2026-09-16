import type { RouteObject } from "react-router-dom";

export const runRoutes: RouteObject[] = [
  {
    path: "/runs",
    lazy: async () => {
      const { RunListPage } = await import("./pages/run-list-page");
      return { Component: RunListPage };
    },
  },
  {
    path: "/runs/:runId",
    lazy: async () => {
      const { RunReportPage } = await import("./pages/run-report-page");
      return { Component: RunReportPage };
    },
  },
];
