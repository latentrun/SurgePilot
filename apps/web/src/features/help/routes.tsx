import { lazy, Suspense } from "react";
import type { ComponentType } from "react";
import type { RouteObject } from "react-router-dom";

import { HELP_COPY } from "./copy";


const HelpPage = lazy(() =>
  import("./pages/help-page").then((module) => ({ default: module.HelpPage })),
);

function lazyElement(Component: ComponentType) {
  return (
    <Suspense
      fallback={
        <div className="rounded-3xl border border-white/10 bg-surface-container-low p-6 text-sm text-text-muted">
          {HELP_COPY.loading}
        </div>
      }
    >
      <Component />
    </Suspense>
  );
}

export const helpRoutes: RouteObject[] = [
  { path: "/help", element: lazyElement(HelpPage) },
];
