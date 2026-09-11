import { useEffect, useState } from "react";

import { ApiError, getApiCatalogSpec, type ApiCatalogSpecResponse } from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { ScalarReference, ScalarReferenceErrorBoundary } from "../components/scalar-reference";

export function ApiCatalogDetailPage({ specId }: { specId: string }) {
  const { session } = useAuthSession();
  const workspaceId = session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const [spec, setSpec] = useState<ApiCatalogSpecResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { let active = true; if (!workspaceId || !specId) return; void getApiCatalogSpec(specId, workspaceId).then((value) => { if (active) setSpec(value); }).catch((cause: unknown) => { if (active) setError(cause instanceof ApiError && cause.body.code === "RESOURCE_NOT_FOUND" ? "The API spec was not found in this workspace." : "API Catalog detail is unavailable. Try again."); }); return () => { active = false; }; }, [specId, workspaceId]);
  if (error) return <main className="space-y-4"><a className="text-primary" href="/api-catalog">← Back to API Catalog</a><h1 className="text-2xl font-semibold text-white">API spec unavailable</h1><p className="text-text-muted">{error}</p></main>;
  if (!spec) return <main><p className="text-text-muted">Loading API spec...</p></main>;
  return <main><ScalarReferenceErrorBoundary><ScalarReference contentUrl={spec.contentUrl} /></ScalarReferenceErrorBoundary></main>;
}
