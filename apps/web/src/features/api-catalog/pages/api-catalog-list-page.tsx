import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  deleteApiCatalogSpec,
  getCsrfToken,
  listApiCatalogSpecs,
  uploadApiCatalogSpec,
  type ApiCatalogSpecSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";

const allowedFilename = /^[A-Za-z0-9._-]+\.(json|ya?ml)$/i;

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const value = bytes / 1024;
  return `${value.toFixed(value >= 10 ? 0 : 1)} KB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatError(error: unknown) {
  if (error instanceof ApiError && error.body.code === "API_SPEC_PARSE_FAILED") return "The API spec could not be parsed. Check the JSON or YAML syntax.";
  if (error instanceof ApiError && error.body.code === "API_SPEC_TOO_LARGE") return "This API spec is too large to upload.";
  if (error instanceof ApiError && error.body.code === "WORKSPACE_ACCESS_DENIED") return "You do not have access to this workspace.";
  return "Something went wrong. Try again.";
}

export function ApiCatalogListPage() {
  const { session, csrfToken } = useAuthSession();
  const workspaceId = session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<ApiCatalogSpecSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiCatalogSpecSummary | null>(null);

  async function load() {
    if (!workspaceId) return;
    setLoading(true);
    try { setItems((await listApiCatalogSpecs({ workspaceId })).items); setError(null); }
    catch (cause) { setError(formatError(cause)); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [workspaceId]);

  const rows = items.filter((item) => {
    const value = query.trim().toLowerCase();
    return !value || item.name.toLowerCase().includes(value) || item.filename.toLowerCase().includes(value) || item.documentTitle.toLowerCase().includes(value);
  });

  async function upload() {
    if (!file) return;
    try {
      await uploadApiCatalogSpec({ file, name, workspaceId, csrfToken: csrfToken ?? (await getCsrfToken()).csrfToken });
      setUploadOpen(false); setFile(null); setName(""); setUploadError(null); if (inputRef.current) inputRef.current.value = ""; await load();
    } catch (cause) { setUploadError(formatError(cause)); }
  }

  async function remove(spec: ApiCatalogSpecSummary) {
    try { await deleteApiCatalogSpec(spec.id, workspaceId, csrfToken ?? (await getCsrfToken()).csrfToken); setDeleteTarget(null); await load(); }
    catch (cause) { setError(formatError(cause)); }
  }

  return <main className="space-y-6">
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div><p className="font-mono text-xs uppercase tracking-[0.22em] text-secondary">Assets</p><h1 className="mt-2 font-display text-3xl font-semibold text-white">API Catalog</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">Manage OpenAPI and Swagger documentation assets for this workspace. API Catalog is documentation only and does not create Scenarios or Test Plans.</p></div>
      <button className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary" onClick={() => setUploadOpen(true)} type="button">Upload API Spec</button>
    </header>
    <section className="rounded-3xl border border-white/10 bg-surface-container-low p-5 shadow-xl">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between"><label className="flex max-w-lg flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-text-muted"><span aria-hidden>⌕</span><span className="sr-only">Search API specs</span><input className="w-full bg-transparent text-text-main outline-none" onChange={(event) => setQuery(event.target.value)} placeholder="Search API specs" value={query} /></label><button className="rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-text-main" onClick={() => void load()} type="button">Refresh</button></div>
      {error ? <p className="mt-6 rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">{error}</p> : null}
      {loading ? <p className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-text-muted">Loading API specs...</p> : rows.length === 0 ? <div className="mt-6 rounded-2xl border border-dashed border-white/15 bg-white/5 p-8 text-center"><h2 className="text-lg font-semibold text-white">No API specs yet</h2><p className="mt-2 text-sm text-text-muted">Upload an OpenAPI or Swagger document to render read-only API reference docs.</p></div> : <div className="mt-6 overflow-x-auto rounded-2xl border border-white/10"><table className="min-w-full divide-y divide-white/10 text-left text-sm"><thead className="bg-white/5 text-xs uppercase tracking-[0.18em] text-secondary"><tr>{["Spec", "Format", "Size", "SHA-256", "Updated", "Actions"].map((heading) => <th className="px-4 py-3 font-semibold" key={heading}>{heading}</th>)}</tr></thead><tbody className="divide-y divide-white/10">{rows.map((spec) => <tr key={spec.id}><td className="px-4 py-4"><p className="font-semibold text-white">{spec.name}</p><p className="mt-1 text-xs text-text-muted">{spec.filename} · {spec.documentTitle} · v{spec.documentVersion}</p></td><td className="px-4 py-4 text-text-muted">{spec.sourceFormat}</td><td className="px-4 py-4 text-text-muted">{formatBytes(spec.sizeBytes)}</td><td className="max-w-[260px] break-all px-4 py-4 font-mono text-[11px] text-text-muted">{spec.sha256}</td><td className="px-4 py-4 text-text-muted">{formatDate(spec.updatedAt)}</td><td className="px-4 py-4 text-right"><a className="mr-3 text-primary" href={`/api-catalog/${spec.id}`}>View</a><button className="text-danger" onClick={() => setDeleteTarget(spec)} type="button">Delete</button></td></tr>)}</tbody></table></div>}
    </section>
    {uploadOpen ? <div aria-labelledby="api-spec-upload-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog"><section className="w-full max-w-lg rounded-3xl border border-white/10 bg-surface-container-low p-6"><h2 className="text-2xl font-semibold text-white" id="api-spec-upload-title">Upload API Spec</h2><p className="mt-2 text-sm text-text-muted">Upload one OpenAPI 3.x or Swagger 2.0 JSON/YAML document.</p><label className="mt-5 block text-sm text-text-main">Display name (optional)<input className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2" onChange={(event) => setName(event.target.value)} value={name} /></label><label className="mt-4 block text-sm text-text-main">API spec file<input accept=".json,.yaml,.yml" className="mt-2 block w-full text-sm text-text-muted" onChange={(event) => { const selected = event.target.files?.[0]; setFile(selected && allowedFilename.test(selected.name) ? selected : null); }} ref={inputRef} type="file" /></label>{uploadError ? <p className="mt-3 text-sm text-danger">{uploadError}</p> : null}<div className="mt-6 flex justify-end gap-3"><button className="rounded-xl border border-white/10 px-4 py-2" onClick={() => setUploadOpen(false)} type="button">Cancel</button><button className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary" disabled={!file} onClick={() => void upload()} type="button">Upload</button></div></section></div> : null}
    {deleteTarget ? <div aria-labelledby="api-spec-delete-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4" role="dialog"><section className="w-full max-w-md rounded-3xl border border-white/10 bg-surface-container-low p-6"><h2 className="text-xl font-semibold text-white" id="api-spec-delete-title">Delete {deleteTarget.name}?</h2><p className="mt-3 text-sm text-text-muted">This removes only the API Catalog documentation asset.</p><div className="mt-6 flex justify-end gap-3"><button className="rounded-xl border border-white/10 px-4 py-2" onClick={() => setDeleteTarget(null)} type="button">Cancel</button><button className="rounded-xl bg-danger px-4 py-2 font-semibold text-white" onClick={() => void remove(deleteTarget)} type="button">Delete</button></div></section></div> : null}
  </main>;
}
