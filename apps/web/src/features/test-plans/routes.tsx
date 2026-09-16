import type { RouteObject } from "react-router-dom";

export const testPlanRoutes: RouteObject[] = [
  {
    path: "/test-plans",
    lazy: async () => {
      const { TestPlanListPage } = await import("./pages/test-plan-list-page");
      return { Component: TestPlanListPage };
    },
  },
  {
    path: "/test-plans/:planId",
    lazy: async () => {
      const { TestPlanEditorPage } =
        await import("./pages/test-plan-editor-page");
      return { Component: TestPlanEditorPage };
    },
  },
];
