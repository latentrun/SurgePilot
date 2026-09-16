import type { RouteObject } from "react-router-dom";

export const scenarioRoutes: RouteObject[] = [
  {
    path: "/scenarios",
    lazy: async () => {
      const { ScenarioListPage } = await import("./pages/scenario-list-page");
      return { Component: ScenarioListPage };
    },
  },
  {
    path: "/scenarios/:scenarioId",
    lazy: async () => {
      const { ScenarioDesignerPage } =
        await import("./pages/scenario-designer-page");
      return { Component: ScenarioDesignerPage };
    },
  },
];
