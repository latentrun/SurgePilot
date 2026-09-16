import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import { ApiError, getApiCatalogSpec } from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { ScalarReference, ScalarReferenceErrorBoundary } from "../components/scalar-reference";

function detailErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "RESOURCE_NOT_FOUND") return "The API spec was not found in this workspace.";
    if (error.body.code === "STORAGE_UNAVAILABLE") return "Spec storage is temporarily unavailable. Try again later.";
    if (error.body.code === "WORKSPACE_ACCESS_DENIED") return "You do not have access to this workspace.";
  }
  return "API Catalog detail is unavailable. Try again.";
}

export function ApiCatalogDetailPage() {
  const { specId = "" } = useParams();
  const { session } = useAuthSession();
  const workspaceId = session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const detailQuery = useQuery({
    enabled: session !== null && specId.length > 0,
    queryKey: ["api-catalog-spec", workspaceId, specId],
    queryFn: () => getApiCatalogSpec(specId, workspaceId),
    retry: false,
  });

  if (detailQuery.isLoading) {
    return <div className="rounded-3xl border border-white/10 bg-surface-container-low p-6 text-sm text-text-muted">Loading API spec...</div>;
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <section className="space-y-4 rounded-3xl border border-white/10 bg-surface-container-low p-6">
        <Link className="inline-flex items-center gap-2 text-sm font-semibold text-primary" to="/api-catalog"><ArrowLeft aria-hidden className="h-4 w-4" />Back to API Catalog</Link>
        <h1 className="font-display text-2xl font-semibold text-white">API spec unavailable</h1>
        <p className="text-sm text-text-muted">{detailErrorMessage(detailQuery.error)}</p>
      </section>
    );
  }

  return (
    <ScalarReferenceErrorBoundary>
      <ScalarReference contentUrl={detailQuery.data.contentUrl} />
    </ScalarReferenceErrorBoundary>
  );
}
