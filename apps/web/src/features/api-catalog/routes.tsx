import { lazy, Suspense } from "react";
import type { ComponentType } from "react";
import type { RouteObject } from "react-router-dom";

const ApiCatalogListPage = lazy(() =>
  import("./pages/api-catalog-list-page").then((module) => ({
    default: module.ApiCatalogListPage,
  })),
);
const ApiCatalogDetailPage = lazy(() =>
  import("./pages/api-catalog-detail-page").then((module) => ({
    default: module.ApiCatalogDetailPage,
  })),
);

function lazyElement(Component: ComponentType) {
  return (
    <Suspense
      fallback={
        <div className="rounded-3xl border border-white/10 bg-surface-container-low p-6 text-sm text-text-muted">
          Loading API Catalog...
        </div>
      }
    >
      <Component />
    </Suspense>
  );
}

export const apiCatalogRoutes: RouteObject[] = [
  { path: "/api-catalog", element: lazyElement(ApiCatalogListPage) },
  { path: "/api-catalog/:specId", element: lazyElement(ApiCatalogDetailPage) },
];
