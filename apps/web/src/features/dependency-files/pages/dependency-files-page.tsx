import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  deleteDependencyFile,
  downloadDependencyFile,
  getCsrfToken,
  listDependencyFiles,
  uploadDependencyFile,
  type DependencyFileSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";

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

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

const DialogContext = createContext<{ onClose: () => void }>({
  onClose: () => {},
});

const Dialog = {
  Root({
    children,
    onOpenChange,
    open,
  }: {
    children: React.ReactNode;
    onOpenChange?: (open: boolean) => void;
    open: boolean;
  }) {
    if (!open) return null;
    const onClose = () => onOpenChange?.(false);
    return (
      <DialogContext.Provider value={{ onClose }}>
        <div data-dialog-root="">{children}</div>
      </DialogContext.Provider>
    );
  },
  Portal({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  },
  Overlay({
    className,
    onClick,
  }: {
    className?: string;
    onClick?: () => void;
  }) {
    const { onClose } = useContext(DialogContext);
    return (
      <div
        aria-hidden="true"
        className={
          className ?? "fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        }
        onClick={() => {
          onClick?.();
          onClose();
        }}
      />
    );
  },
  Content({
    "aria-label": ariaLabel,
    children,
    className,
  }: {
    "aria-label"?: string;
    children: React.ReactNode;
    className?: string;
  }) {
    return (
      <div
        aria-label={ariaLabel}
        aria-modal="true"
        className={className}
        role="dialog"
      >
        {children}
      </div>
    );
  },
  Title({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) {
    return <h2 className={className}>{children}</h2>;
  },
  Description({
    children,
    className,
  }: {
    children: React.ReactNode;
    className?: string;
  }) {
    return <p className={className}>{children}</p>;
  },
  Close({
    "aria-label": ariaLabel,
    children,
    className,
    onClick,
  }: {
    "aria-label"?: string;
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
  }) {
    const { onClose } = useContext(DialogContext);
    return (
      <button
        aria-label={ariaLabel ?? "Close"}
        className={className}
        onClick={() => {
          onClick?.();
          onClose();
        }}
        type="button"
      >
        {children}
      </button>
    );
  },
};

function UploadCloud({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="M12 12v9" />
      <path d="m16 16-4-4-4 4" />
    </svg>
  );
}

function Search({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function ShieldAlert({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M12 8v4" />
      <path d="M12 16h.01" />
    </svg>
  );
}

function RefreshCw({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}

function FileUp({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M12 12v6" />
      <path d="m15 15-3-3-3 3" />
    </svg>
  );
}

function Download({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" x2="12" y1="15" y2="3" />
    </svg>
  );
}

function Trash2({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
      <line x1="10" x2="10" y1="11" y2="17" />
      <line x1="14" x2="14" y1="11" y2="17" />
    </svg>
  );
}

function X({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function ChevronLeft({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

function ChevronRight({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="16"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="16"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
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

export function DependencyFilesPage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadApiError, setUploadApiError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [deleteTarget, setDeleteTarget] =
    useState<DependencyFileSummary | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadPendingId, setDownloadPendingId] = useState<string | null>(
    null,
  );
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [rows, setRows] = useState<DependencyFileSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [listError, setListError] = useState<unknown | null>(null);

  const workspaceId = session?.defaultWorkspace.id ?? "";

  const fetchList = useCallback(async () => {
    if (!workspaceId) return;
    setIsFetching(true);
    try {
      const data = await listDependencyFiles({
        workspaceId,
        page,
        pageSize,
        q,
        sort: "-createdAt",
      });
      setRows(data.items);
      setTotal(data.total);
      setListError(null);
    } catch (err) {
      setListError(err);
    } finally {
      setIsLoading(false);
      setIsFetching(false);
    }
  }, [workspaceId, page, q]);

  useEffect(() => {
    if (session !== null) {
      void fetchList();
    }
  }, [session, fetchList]);

  if (session === null) {
    return null;
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isEmpty = !isLoading && !listError && rows.length === 0;

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
    if (nextError !== null || !selectedFile) {
      return;
    }
    setIsUploading(true);
    try {
      const token = await getWriteToken();
      await uploadDependencyFile(selectedFile, workspaceId, token);
      setPage(1);
      setUploadOpen(false);
      setSelectedFile(null);
      setFileError(null);
      setUploadApiError(null);
      await fetchList();
    } catch (error) {
      setUploadApiError(uploadErrorMessage(error));
    } finally {
      setIsUploading(false);
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

  async function handleDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      const token = await getWriteToken();
      await deleteDependencyFile(deleteTarget.id, workspaceId, token);
      if (rows.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      }
      setDeleteTarget(null);
      await fetchList();
    } catch (error) {
      if (error instanceof ApiError && error.body.code === "FILE_IN_USE") {
        setDeleteError(
          "This file is used by a scenario or test plan and cannot be deleted yet.",
        );
        return;
      }
      setDeleteError(errorMessage(error));
    } finally {
      setIsDeleting(false);
    }
  }

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
        {isLoading ? (
          <div className="p-8 text-sm text-text-muted">
            Loading Dependency Files...
          </div>
        ) : null}
        {listError ? (
          <div className="flex flex-col gap-4 p-8 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 text-error" />
              <p className="text-sm text-error">
                {errorMessage(listError)}
              </p>
            </div>
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main"
              onClick={() => void fetchList()}
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
                            disabled={downloadPendingId === file.id}
                            label={`Download ${file.filename}`}
                            onClick={() => void handleDownload(file)}
                          >
                            <Download className="h-4 w-4" />
                          </IconButton>
                          <IconButton
                            label={`Delete ${file.filename}`}
                            onClick={() => {
                              setDeleteTarget(file);
                              setDeleteError(null);
                            }}
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
                  disabled={page <= 1 || isFetching}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  type="button"
                >
                  <ChevronLeft className="h-4 w-4 inline mr-1" />
                  Previous
                </button>
                <button
                  className="rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={page >= totalPages || isFetching}
                  onClick={() => setPage((current) => current + 1)}
                  type="button"
                >
                  Next
                  <ChevronRight className="h-4 w-4 inline ml-1" />
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      <Dialog.Root open={uploadOpen} onOpenChange={setUploadOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Upload Dependency File"
            className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container p-6 shadow-2xl"
          >
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
              <Dialog.Close
                aria-label="Close"
                className="rounded-lg p-2 text-secondary transition hover:bg-white/10 hover:text-white"
                onClick={() => setUploadOpen(false)}
              >
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
                  onClick={() => setUploadOpen(false)}
                  type="button"
                >
                  Cancel
                </Dialog.Close>
                <button
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary-container px-5 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={isUploading}
                  type="submit"
                >
                  {isUploading ? "Uploading..." : "Upload"}
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label={`Delete ${deleteTarget?.filename ?? "file"}?`}
            className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container p-6 shadow-2xl"
          >
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
                onClick={() => setDeleteTarget(null)}
                type="button"
              >
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-error px-5 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isDeleting || deleteTarget === null}
                onClick={() => void handleDelete()}
                type="button"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
