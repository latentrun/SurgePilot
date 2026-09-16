import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, FileUp, RefreshCw, Search, ShieldCheck, Trash2, UploadCloud } from "lucide-react";

import {
  ApiError,
  deleteApiCatalogSpec,
  getCsrfToken,
  listApiCatalogSpecs,
  uploadApiCatalogSpec,
  type ApiCatalogSpecSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { IconActionButton, IconActionLink } from "../../../components/icon-action";

const pageSize = 50;
const allowedSpecFilename = /^[A-Za-z0-9._-]+\.(json|ya?ml)$/i;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
}

function sourceFormatLabel(value: string) {
  if (value === "openapi_json") return "OpenAPI JSON";
  if (value === "openapi_yaml") return "OpenAPI YAML";
  if (value === "swagger_json") return "Swagger JSON";
  if (value === "swagger_yaml") return "Swagger YAML";
  return value;
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "API_SPEC_TOO_LARGE") return "This API spec is too large to upload.";
    if (error.body.code === "API_SPEC_PARSE_FAILED") return "The API spec could not be parsed. Check the JSON or YAML syntax.";
    if (error.body.code === "UNSUPPORTED_API_SPEC_FORMAT") return "Upload an OpenAPI 3.x or Swagger 2.0 JSON/YAML document.";
    if (error.body.code === "STORAGE_UNAVAILABLE") return "Spec storage is temporarily unavailable. Try again later.";
    if (error.body.code === "WORKSPACE_ACCESS_DENIED") return "You do not have access to this workspace.";
    if (error.body.code === "RESOURCE_NOT_FOUND") return "The API spec was not found. Refresh the list and try again.";
  }
  return "Something went wrong. Try again.";
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

export function ApiCatalogListPage() {
  const queryClient = useQueryClient();
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [q, setQ] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiCatalogSpecSummary | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const workspaceId = session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const listQuery = useQuery({
    enabled: session !== null,
    queryKey: ["api-catalog-specs", workspaceId],
    queryFn: () => listApiCatalogSpecs({ workspaceId, limit: pageSize, offset: 0 }),
    retry: false,
  });
  const rows = (listQuery.data?.items ?? []).filter((item) => {
    const value = q.trim().toLowerCase();
    if (!value) return true;
    return (
      item.name.toLowerCase().includes(value) ||
      item.filename.toLowerCase().includes(value) ||
      item.documentTitle.toLowerCase().includes(value)
    );
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error("Select a file before uploading.");
      return uploadApiCatalogSpec({
        file: selectedFile,
        name: displayName,
        workspaceId,
        csrfToken: await getWriteToken(),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["api-catalog-specs", workspaceId] });
      setSelectedFile(null);
      setDisplayName("");
      setFileError(null);
      setUploadError(null);
      setUploadOpen(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (error) => setUploadError(apiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: async (specId: string) =>
      deleteApiCatalogSpec(specId, workspaceId, await getWriteToken()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["api-catalog-specs", workspaceId] });
      setDeleteTarget(null);
      setDeleteError(null);
    },
    onError: (error) => setDeleteError(apiErrorMessage(error)),
  });

  function chooseFile(file: File | undefined) {
    setSelectedFile(null);
    setFileError(null);
    setUploadError(null);
    if (!file) return;
    if (!allowedSpecFilename.test(file.name)) {
      setFileError("Choose a .json, .yaml, or .yml OpenAPI/Swagger file.");
      return;
    }
    setSelectedFile(file);
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.22em] text-secondary">Assets</p>
          <h1 className="mt-2 font-display text-3xl font-semibold text-white">API Catalog</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-text-muted">
            Manage OpenAPI and Swagger documentation assets for this workspace. API Catalog is documentation only and does not create Scenarios or Test Plans.
          </p>
        </div>
        <button
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary shadow-lg shadow-primary/20 transition hover:bg-primary/90"
          onClick={() => setUploadOpen(true)}
          type="button"
        >
          <UploadCloud aria-hidden className="h-4 w-4" />
          Upload API Spec
        </button>
      </div>

      <div className="rounded-3xl border border-white/10 bg-surface-container-low p-5 shadow-xl">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <label className="flex max-w-lg flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-text-muted focus-within:border-primary/50">
            <Search aria-hidden className="h-4 w-4" />
            <span className="sr-only">Search API specs</span>
            <input
              className="w-full bg-transparent text-text-main outline-none placeholder:text-text-muted"
              onChange={(event) => setQ(event.target.value)}
              placeholder="Search API specs"
              value={q}
            />
          </label>
          <button
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-text-main transition hover:bg-white/5"
            onClick={() => void listQuery.refetch()}
            type="button"
          >
            <RefreshCw aria-hidden className="h-4 w-4" />
            Refresh
          </button>
        </div>

        {listQuery.isError ? (
          <div className="mt-6 rounded-2xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
            {apiErrorMessage(listQuery.error)}
          </div>
        ) : null}

        {listQuery.isLoading ? (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-text-muted">Loading API specs...</div>
        ) : rows.length === 0 ? (
          <div className="mt-6 rounded-2xl border border-dashed border-white/15 bg-white/5 p-8 text-center">
            <FileUp aria-hidden className="mx-auto h-10 w-10 text-primary" />
            <h2 className="mt-4 text-lg font-semibold text-white">No API specs yet</h2>
            <p className="mt-2 text-sm text-text-muted">Upload an OpenAPI or Swagger document to render read-only API reference docs.</p>
          </div>
        ) : (
          <div className="mt-6 overflow-hidden rounded-2xl border border-white/10">
            <table className="min-w-full divide-y divide-white/10 text-left text-sm">
              <thead className="bg-white/5 text-xs uppercase tracking-[0.18em] text-secondary">
                <tr>
                  <th className="px-4 py-3 font-semibold">Spec</th>
                  <th className="px-4 py-3 font-semibold">Format</th>
                  <th className="px-4 py-3 font-semibold">Size</th>
                  <th className="px-4 py-3 font-semibold">SHA-256</th>
                  <th className="px-4 py-3 font-semibold">Updated</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {rows.map((spec) => (
                  <tr className="bg-surface-container-low/60" key={spec.id}>
                    <td className="px-4 py-4">
                      <p className="font-semibold text-white">{spec.name}</p>
                      <p className="mt-1 text-xs text-text-muted">{spec.filename} · {spec.documentTitle} · v{spec.documentVersion}</p>
                    </td>
                    <td className="px-4 py-4 text-text-muted">{sourceFormatLabel(spec.sourceFormat)}</td>
                    <td className="px-4 py-4 text-text-muted">{formatBytes(spec.sizeBytes)}</td>
                    <td className="max-w-[260px] px-4 py-4">
                      <code
                        className="block break-all font-mono text-[11px] leading-5 text-text-muted"
                        title={spec.sha256}
                      >
                        {spec.sha256}
                      </code>
                    </td>
                    <td className="px-4 py-4 text-text-muted">{formatDate(spec.updatedAt)}</td>
                    <td className="px-4 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        <IconActionLink
                          Icon={Eye}
                          label={`View ${spec.name}`}
                          to={`/api-catalog/${spec.id}`}
                        />
                        <IconActionButton
                          Icon={Trash2}
                          label={`Delete ${spec.name}`}
                          onClick={() => setDeleteTarget(spec)}
                          tone="danger"
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {uploadOpen ? (
        <div aria-labelledby="api-spec-upload-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm" role="dialog">
          <section className="w-full max-w-lg rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <h2 className="font-display text-2xl font-semibold text-white" id="api-spec-upload-title">Upload API Spec</h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">Upload one OpenAPI 3.x or Swagger 2.0 JSON/YAML document. Remote references are stored as text only and are not resolved.</p>
            <div className="mt-5 space-y-4">
              <label className="block text-sm font-semibold text-text-main">
                Display name (optional)
                <input className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-text-main outline-none focus:border-primary/50" maxLength={120} onChange={(event) => setDisplayName(event.target.value)} placeholder="Derived from info.title when empty" value={displayName} />
              </label>
              <div className="block text-sm font-semibold text-text-main">
                <label htmlFor="api-spec-file-input">API spec file</label>
                <input
                  ref={fileInputRef}
                  accept=".json,.yaml,.yml,application/json,text/yaml,application/yaml"
                  className="sr-only"
                  id="api-spec-file-input"
                  onChange={(event) => chooseFile(event.target.files?.[0])}
                  type="file"
                />
                <div className="mt-2 flex flex-col gap-3 rounded-xl border border-white/10 bg-white/5 p-3 sm:flex-row sm:items-center">
                  <button
                    className="inline-flex items-center justify-center rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-on-primary transition hover:bg-primary/90"
                    onClick={() => fileInputRef.current?.click()}
                    type="button"
                  >
                    Choose file
                  </button>
                  <span className="min-w-0 truncate text-sm font-normal text-text-muted">
                    {selectedFile ? selectedFile.name : "No file chosen"}
                  </span>
                </div>
              </div>
              {selectedFile ? <p className="text-xs text-text-muted">Selected: {selectedFile.name} · {formatBytes(selectedFile.size)}</p> : null}
              {fileError ? <p className="text-sm text-danger">{fileError}</p> : null}
              {uploadError ? <p className="text-sm text-danger">{uploadError}</p> : null}
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main" onClick={() => setUploadOpen(false)} type="button">Cancel</button>
              <button className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-60" disabled={!selectedFile || uploadMutation.isPending} onClick={() => uploadMutation.mutate()} type="button">
                <ShieldCheck aria-hidden className="h-4 w-4" />
                {uploadMutation.isPending ? "Uploading" : "Upload"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {deleteTarget ? (
        <div aria-labelledby="api-spec-delete-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm" role="dialog">
          <section className="w-full max-w-md rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <h2 className="font-display text-2xl font-semibold text-white" id="api-spec-delete-title">Delete {deleteTarget.name}?</h2>
            <p className="mt-3 text-sm leading-6 text-text-muted">This removes only the API Catalog documentation asset. It does not affect Scenarios, Test Plans, Runs, or Artifacts.</p>
            {deleteError ? <p className="mt-3 text-sm text-danger">{deleteError}</p> : null}
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-text-main" onClick={() => setDeleteTarget(null)} type="button">Cancel</button>
              <button className="rounded-xl bg-danger px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(deleteTarget.id)} type="button">Delete</button>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
