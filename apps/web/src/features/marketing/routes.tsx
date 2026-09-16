import type { RouteObject } from "react-router-dom";

export const marketingRoutes: RouteObject[] = [
  {
    path: "/",
    lazy: async () => {
      const { LandingPage } = await import("./pages/landing-page");
      return { Component: LandingPage };
    },
  },
];
