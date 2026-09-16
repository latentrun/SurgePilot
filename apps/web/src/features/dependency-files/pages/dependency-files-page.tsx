import { useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Copy,
  Download,
  Eye,
  FileUp,
  RefreshCw,
  Search,
  ShieldAlert,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";

import {
  ApiError,
  deleteDependencyFile,
  downloadDependencyFile,
  getCsrfToken,
  listDependencyFiles,
  previewDependencyFile,
  uploadDependencyFile,
  type DependencyFileSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { copyText } from "../../../utils/clipboard";

const pageSize = 20;
const safeFilenamePattern = /^[A-Za-z0-9._-]{1,255}$/;

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
}

function validateFilename(filename: string) {
  if (
    !safeFilenamePattern.test(filename) ||
    filename === "." ||
    filename === ".."
  ) {
    return "Use A-Z, a-z, numbers, dots, underscores, or dashes only.";
  }
  const lower = filename.toLowerCase();
  if (
    lower === ".env" ||
    lower.startsWith(".env.") ||
    lower === ".git" ||
    lower.startsWith(".git") ||
    lower === "private.pem" ||
    lower === "private.key" ||
    lower.endsWith(".private.pem") ||
    lower.endsWith(".private.key") ||
    lower === "id_rsa" ||
    lower.startsWith("id_rsa") ||
    lower === "id_dsa" ||
    lower.startsWith("id_dsa") ||
    lower === "id_ecdsa" ||
    lower.startsWith("id_ecdsa") ||
    lower === "id_ed25519" ||
    lower.startsWith("id_ed25519") ||
    lower === "known_hosts" ||
    lower === "authorized_keys"
  ) {
    return "This filename is blocked because it may contain sensitive credentials.";
  }
  return null;
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "STORAGE_UNAVAILABLE") {
      return "File storage is temporarily unavailable. Try again later.";
    }
    if (error.body.code === "WORKSPACE_ACCESS_DENIED") {
      return "You do not have access to this workspace.";
    }
    if (error.body.code === "RESOURCE_NOT_FOUND") {
      return "The Dependency File was not found. Refresh the list and try again.";
    }
    return "Something went wrong. Try again.";
  }
  return "Something went wrong. Try again.";
}

function uploadErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.body.code === "DEPENDENCY_FILE_NAME_CONFLICT") {
      return "A Dependency File with this filename already exists.";
    }
    if (error.body.code === "INVALID_FILENAME") {
      return "Use A-Z, a-z, numbers, dots, underscores, or dashes only.";
    }
    if (error.body.code === "PAYLOAD_TOO_LARGE") {
      return "This file is too large to upload.";
    }
    if (error.body.code === "STORAGE_UNAVAILABLE") {
      return "File storage is temporarily unavailable. Try again later.";
    }
    if (error.body.code === "VALIDATION_ERROR") {
      const detailMessage = error.body.details?.find(
        (detail) => detail.field === "file",
      )?.message;
      if (detailMessage) {
        return detailMessage;
      }
      return "Check the file and try again.";
    }
    return "Something went wrong. Try again.";
  }
  return "Upload failed.";
}

function previewUnavailableMessage(reason: string | null | undefined) {
  if (reason === "binary_content") {
    return "This file looks binary, so inline preview is disabled.";
  }
  if (reason === "decode_failed") {
    return "This file is not valid UTF-8 text, so inline preview is disabled.";
  }
  return "Preview is not available for this file.";
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

export function DependencyFilesPage() {
  const queryClient = useQueryClient();
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadApiError, setUploadApiError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] =
    useState<DependencyFileSummary | null>(null);
  const [previewTarget, setPreviewTarget] =
    useState<DependencyFileSummary | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadPendingId, setDownloadPendingId] = useState<string | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const workspaceId = session?.defaultWorkspace.id ?? "";
  const listQuery = useQuery({
    enabled: session !== null,
    queryKey: ["dependency-files", workspaceId, q, page],
    queryFn: () =>
      listDependencyFiles({
        workspaceId,
        page,
        pageSize,
        q,
        sort: "-createdAt",
      }),
    retry: false,
  });
  const previewQuery = useQuery({
    enabled: session !== null && previewTarget !== null,
    queryKey: ["dependency-file-preview", workspaceId, previewTarget?.id],
    queryFn: () => previewDependencyFile(previewTarget?.id ?? "", workspaceId),
    retry: false,
  });

  const rows = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isEmpty =
    !listQuery.isLoading && !listQuery.isError && rows.length === 0;

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (selectedFile === null) {
        throw new Error("Select a file before uploading.");
      }
      return uploadDependencyFile(
        selectedFile,
        workspaceId,
        await getWriteToken(),
      );
    },
    onSuccess: async () => {
      setPage(1);
      await queryClient.invalidateQueries({
        queryKey: ["dependency-files", workspaceId],
      });
      setUploadOpen(false);
      setSelectedFile(null);
      setFileError(null);
      setUploadApiError(null);
    },
    onError: (error) => {
      setUploadApiError(uploadErrorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (dependencyFileId: string) =>
      deleteDependencyFile(
        dependencyFileId,
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: async () => {
      if (rows.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      }
      await queryClient.invalidateQueries({
        queryKey: ["dependency-files", workspaceId],
      });
      setDeleteTarget(null);
      setDeleteError(null);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.body.code === "FILE_IN_USE") {
        setDeleteError(
          "This file is used by a scenario or test plan and cannot be deleted yet.",
        );
        return;
      }
      setDeleteError(errorMessage(error));
    },
  });

  if (session === null) {
    return null;
  }

  function updateSearch(value: string) {
    setQ(value);
    setPage(1);
  }

  function updateSelectedFile(file: File | null) {
    setSelectedFile(file);
    setUploadApiError(null);
    setFileError(
      file ? validateFilename(file.name) : "Select a file to upload.",
    );
  }

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextError = selectedFile
      ? validateFilename(selectedFile.name)
      : "Select a file to upload.";
    setFileError(nextError);
    setUploadApiError(null);
    if (nextError !== null) {
      return;
    }
    try {
      await uploadMutation.mutateAsync();
    } catch {
      // Mutation onError owns user-visible API errors.
    }
  }

  async function handleDownload(file: DependencyFileSummary) {
    setDownloadError(null);
    setDownloadPendingId(file.id);
    try {
      const blob = await downloadDependencyFile(file.id, workspaceId);
      if (typeof URL.createObjectURL === "function") {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = file.filename;
        link.rel = "noopener";
        document.body.append(link);
        if (!navigator.userAgent.includes("jsdom")) {
          link.click();
        }
        link.remove();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      setDownloadError(errorMessage(error));
    } finally {
      setDownloadPendingId(null);
    }
  }

  async function handleCopyPreview(text: string) {
    setCopyMessage(null);
    setCopyError(null);
    const result = await copyText(text);
    if (result.ok) {
      setCopyMessage("Preview text copied.");
    } else {
      setCopyError(result.reason);
    }
  }

  const previewData =
    previewTarget !== null && previewQuery.data?.id === previewTarget.id
      ? previewQuery.data
      : null;

  return (
    <div className="mx-auto flex max-w-container-max flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-[34px] font-semibold leading-10 text-white">
            Dependency Files
          </h1>
          <p className="mt-2 max-w-3xl text-base leading-6 text-text-muted">
            Upload files that scenarios and test plans can use during runs.
          </p>
        </div>
        <button
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          onClick={() => {
            setSelectedFile(null);
            setFileError(null);
            setUploadApiError(null);
            setUploadOpen(true);
          }}
          type="button"
        >
          <UploadCloud className="h-4 w-4" />
          Upload Dependency File
        </button>
      </div>

      <div className="grid gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-4 sm:grid-cols-[1fr_auto] sm:items-center">
        <label className="relative block w-full max-w-md">
          <span className="sr-only">Search Dependency Files</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary" />
          <input
            className="h-11 w-full rounded-lg border border-white/10 bg-surface-container-low px-10 text-sm text-text-main outline-none transition placeholder:text-secondary focus:border-primary/50"
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="Search by filename..."
            value={q}
          />
        </label>
        <div className="font-mono text-[12px] uppercase tracking-wide text-secondary">
          Sort: <span className="text-text-main">Newest first</span>
        </div>
      </div>

      {downloadError ? (
        <div className="rounded-xl border border-error/30 bg-error/10 p-4 text-sm text-error">
          {downloadError}
        </div>
      ) : null}

      <section className="surgepilot-glass overflow-hidden rounded-xl">
        {listQuery.isLoading ? (
          <div className="p-8 text-sm text-text-muted">
            Loading Dependency Files...
          </div>
        ) : null}
        {listQuery.isError ? (
          <div className="flex flex-col gap-4 p-8 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 text-error" />
              <p className="text-sm text-error">
                {errorMessage(listQuery.error)}
              </p>
            </div>
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main"
              onClick={() => listQuery.refetch()}
              type="button"
            >
              <RefreshCw className="h-4 w-4" />
              Retry
            </button>
          </div>
        ) : null}
        {isEmpty ? (
          <div className="mx-auto flex max-w-md flex-col items-center p-10 text-center">
            <div className="grid h-14 w-14 place-items-center rounded-2xl border border-primary/20 bg-primary-container/10 text-primary">
              <FileUp className="h-7 w-7" />
            </div>
            <h2 className="mt-5 text-lg font-semibold leading-7 text-white">
              No Dependency Files yet
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Upload data files, payload examples, certificates, or other files
              used by scenarios and test plans.
            </p>
          </div>
        ) : null}
        {rows.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] border-collapse text-left">
                <thead className="border-b border-white/10 bg-white/5">
                  <tr>
                    {[
                      "Filename",
                      "Type",
                      "Size",
                      "In use",
                      "Created",
                      "Actions",
                    ].map((heading) => (
                      <th
                        className="px-5 py-4 font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-secondary"
                        key={heading}
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {rows.map((file) => (
                    <tr
                      className="transition hover:bg-white/[0.03]"
                      key={file.id}
                    >
                      <td className="px-5 py-4 font-semibold text-white">
                        {file.filename}
                      </td>
                      <td className="px-5 py-4 text-sm text-text-muted">
                        {file.contentType ?? "Unknown"}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-text-muted">
                        {formatBytes(file.sizeBytes)}
                      </td>
                      <td className="px-5 py-4 text-sm text-text-muted">
                        {file.inUse ? "Yes" : "No"}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-text-muted">
                        {formatDate(file.createdAt)}
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-2">
                          <IconButton
                            label={`Preview ${file.filename}`}
                            onClick={() => {
                              setPreviewTarget(file);
                              setCopyMessage(null);
                              setCopyError(null);
                            }}
                          >
                            <Eye className="h-4 w-4" />
                          </IconButton>
                          <IconButton
                            disabled={downloadPendingId === file.id}
                            label={`Download ${file.filename}`}
                            onClick={() => void handleDownload(file)}
                          >
                            <Download className="h-4 w-4" />
                          </IconButton>
                          <IconButton
                            label={`Delete ${file.filename}`}
                            onClick={() => setDeleteTarget(file)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </IconButton>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
              <div className="font-mono text-[12px] uppercase tracking-wide text-secondary">
                Page <span className="text-text-main">{page}</span> of{" "}
                <span className="text-text-main">{totalPages}</span>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={page <= 1 || listQuery.isFetching}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  type="button"
                >
                  Previous
                </button>
                <button
                  className="rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={page >= totalPages || listQuery.isFetching}
                  onClick={() => setPage((current) => current + 1)}
                  type="button"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      <Dialog.Root open={uploadOpen} onOpenChange={setUploadOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <Dialog.Title className="font-display text-2xl font-semibold text-white">
                  Upload Dependency File
                </Dialog.Title>
                <Dialog.Description className="mt-2 text-sm leading-6 text-text-muted">
                  Choose one file to make it available for scenarios and test
                  plans in this Workspace.
                </Dialog.Description>
              </div>
              <Dialog.Close className="rounded-lg p-2 text-secondary transition hover:bg-white/10 hover:text-white">
                <X className="h-4 w-4" />
              </Dialog.Close>
            </div>
            <form className="mt-6 space-y-5" onSubmit={handleUpload}>
              <div>
                <label
                  className="mb-2 block text-sm font-semibold text-white"
                  htmlFor="dependency-file-input"
                >
                  File
                </label>
                <input
                  aria-label="File"
                  className="sr-only"
                  id="dependency-file-input"
                  onChange={(event) =>
                    updateSelectedFile(event.target.files?.[0] ?? null)
                  }
                  ref={fileInputRef}
                  type="file"
                />
                <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-2">
                  <button
                    className="inline-flex items-center justify-center rounded-md bg-primary-container px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary transition hover:brightness-110"
                    onClick={() => fileInputRef.current?.click()}
                    type="button"
                  >
                    Choose file
                  </button>
                  <span className="min-w-0 truncate text-sm text-text-muted">
                    {selectedFile?.name ?? "No file selected"}
                  </span>
                </div>
              </div>
              <p className="text-xs leading-5 text-text-muted">
                Use only letters, numbers, dots, underscores, and dashes in the
                filename. Folders and spaces are not supported.
              </p>
              {fileError ? (
                <p className="text-sm text-error">{fileError}</p>
              ) : null}
              {uploadApiError ? (
                <p className="text-sm text-error">{uploadApiError}</p>
              ) : null}
              <div className="flex justify-end gap-3 pt-2">
                <Dialog.Close
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main"
                  type="button"
                >
                  Cancel
                </Dialog.Close>
                <button
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary-container px-5 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={uploadMutation.isPending}
                  type="submit"
                >
                  {uploadMutation.isPending ? "Uploading..." : "Upload"}
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={previewTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPreviewTarget(null);
            setCopyMessage(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(100vw,720px)] flex-col border-l border-white/10 bg-surface-container shadow-2xl">
            <div className="border-b border-white/10 p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Dialog.Title className="truncate font-display text-2xl font-semibold text-white">
                    Preview {previewTarget?.filename}
                  </Dialog.Title>
                  <Dialog.Description className="mt-2 text-sm leading-6 text-text-muted">
                    Review a bounded read-only text preview. Download remains
                    available for the full file.
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  aria-label="Close preview"
                  className="rounded-lg p-2 text-secondary transition hover:bg-white/10 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </Dialog.Close>
              </div>
              {previewTarget ? (
                <div className="mt-4 grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-text-muted sm:grid-cols-2">
                  <div>
                    Type:{" "}
                    <span className="text-text-main">
                      {previewTarget.contentType ?? "Unknown"}
                    </span>
                  </div>
                  <div>
                    Size:{" "}
                    <span className="text-text-main">
                      {formatBytes(previewTarget.sizeBytes)}
                    </span>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              {previewTarget !== null && previewQuery.isLoading ? (
                <p className="text-sm text-text-muted">
                  Loading preview for {previewTarget.filename}...
                </p>
              ) : null}

              {previewTarget !== null && previewQuery.isError ? (
                <div className="space-y-4 rounded-xl border border-error/30 bg-error/10 p-4">
                  <p className="text-sm text-error">
                    {errorMessage(previewQuery.error)}
                  </p>
                  <button
                    className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main"
                    onClick={() => void previewQuery.refetch()}
                    type="button"
                  >
                    <RefreshCw className="h-4 w-4" />
                    Retry preview
                  </button>
                </div>
              ) : null}

              {previewData?.canPreview && previewData.text !== null ? (
                <div className="space-y-4">
                  {previewData.truncated ? (
                    <div className="rounded-xl border border-primary/30 bg-primary-container/10 p-3 text-sm text-primary">
                      Preview truncated at {formatBytes(previewData.maxBytes)}.
                    </div>
                  ) : null}
                  <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-white/10 bg-background/70 p-4 font-mono text-xs leading-5 text-text-main">
                    {previewData.text}
                  </pre>
                  {copyMessage ? (
                    <p className="text-sm text-success">{copyMessage}</p>
                  ) : null}
                  {copyError ? (
                    <p className="text-sm text-error">{copyError}</p>
                  ) : null}
                </div>
              ) : null}

              {previewData !== null && !previewData.canPreview ? (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-text-muted">
                  {previewUnavailableMessage(previewData.reason)}
                </div>
              ) : null}
            </div>

            <div className="flex flex-wrap justify-end gap-3 border-t border-white/10 p-6">
              {previewData?.canPreview && previewData.text !== null ? (
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:border-primary/30 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!previewData.text}
                  onClick={() => void handleCopyPreview(previewData.text ?? "")}
                  type="button"
                >
                  <Copy className="h-4 w-4" />
                  Copy preview text
                </button>
              ) : null}
              {previewTarget ? (
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:border-primary/30 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={downloadPendingId === previewTarget.id}
                  onClick={() => void handleDownload(previewTarget)}
                  type="button"
                >
                  <Download className="h-4 w-4" />
                  Download {previewTarget.filename}
                </button>
              ) : null}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container p-6 shadow-2xl">
            <Dialog.Title className="font-display text-2xl font-semibold text-white">
              Delete {deleteTarget?.filename}?
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm leading-6 text-text-muted">
              This removes the file from your Dependency Files list. You cannot
              undo this action.
            </Dialog.Description>
            {deleteError ? (
              <p className="mt-4 text-sm text-error">{deleteError}</p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <Dialog.Close
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main"
                type="button"
              >
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-error px-5 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-60"
                disabled={deleteMutation.isPending || deleteTarget === null}
                onClick={() =>
                  deleteTarget && deleteMutation.mutate(deleteTarget.id)
                }
                type="button"
              >
                Delete
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

function IconButton({
  children,
  disabled = false,
  label,
  onClick,
}: Readonly<{
  children: React.ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}>) {
  return (
    <button
      aria-label={label}
      className="grid h-9 w-9 place-items-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-primary-container/10 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}
