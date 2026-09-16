import { lazy, Suspense } from "react";
import type { ComponentType } from "react";
import type { RouteObject } from "react-router-dom";

const ApiKeysPage = lazy(() =>
  import("./pages/api-keys-page").then((module) => ({ default: module.ApiKeysPage })),
);

function lazyElement(Component: ComponentType) {
  return (
    <Suspense fallback={<div className="rounded-3xl border border-white/10 bg-surface-container-low p-6 text-sm text-text-muted">Loading API keys...</div>}>
      <Component />
    </Suspense>
  );
}

export const accountRoutes: RouteObject[] = [
  { path: "/account/api-keys", element: lazyElement(ApiKeysPage) },
];
