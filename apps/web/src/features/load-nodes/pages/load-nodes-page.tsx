import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  deleteLoadNode,
  disableLoadNode,
  enableLoadNode,
  getCsrfToken,
  getLoadNodeInitAttempt,
  initializeLoadNode,
  listLoadNodeInitAttempts,
  listLoadNodes,
  patchLoadNode,
  scanLoadNodeSshHostKey,
  trustLoadNodeSshHostKey,
  updateLoadNodeCredentials,
  type LoadNodeAuthType,
  type LoadNodeInitAttemptDetail,
  type LoadNodeInitAttemptSummary,
  type LoadNodePatchRequest,
  type LoadNodeScope,
  type LoadNodeSshHostKeyScanResponse,
  type LoadNodeStatus,
  type LoadNodeSummary,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { loadNodeErrorMessage, statusCopy } from "./load-node-copy";

const pageSize = 20;
const statuses: LoadNodeStatus[] = [
  "uninitialized",
  "initializing",
  "idle",
  "busy",
  "offline",
  "quarantined",
  "disabled",
];
const allowedEditStatuses = new Set<LoadNodeStatus>([
  "uninitialized",
  "idle",
  "offline",
]);

type EditState = Pick<
  LoadNodePatchRequest,
  "host" | "sshPort" | "sshUser" | "runnerHome" | "maintainer" | "remark"
>;
type CredentialState = {
  authType: LoadNodeAuthType;
  password: string;
  privateKey: string;
  privateKeyPassphrase: string;
};

const emptyCredentialForm: CredentialState = {
  authType: "password",
  password: "",
  privateKey: "",
  privateKeyPassphrase: "",
};

const attemptStatusCopy: Record<
  LoadNodeInitAttemptSummary["status"],
  string
> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
};

function cn(...inputs: (string | boolean | null | undefined)[]) {
  return inputs.filter(Boolean).join(" ");
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(status: LoadNodeStatus) {
  return {
    uninitialized: "border-white/10 bg-white/5 text-text-muted",
    initializing: "border-primary/30 bg-primary/10 text-primary",
    idle: "border-success/30 bg-success/10 text-success",
    busy: "border-warning/30 bg-warning/10 text-warning",
    offline: "border-error/30 bg-error-container text-error",
    quarantined: "border-error/40 bg-error-container text-error",
    disabled: "border-white/10 bg-white/5 text-secondary",
  }[status];
}

function attemptStatusTone(status: LoadNodeInitAttemptSummary["status"]) {
  return {
    queued: "border-primary/30 bg-primary/10 text-primary",
    running: "border-warning/30 bg-warning/10 text-warning",
    succeeded: "border-success/30 bg-success/10 text-success",
    failed: "border-error/40 bg-error-container text-error",
  }[status];
}

function nodeToEdit(node: LoadNodeSummary): EditState {
  return {
    host: node.host,
    sshPort: node.sshPort,
    sshUser: node.sshUser,
    runnerHome: node.runnerHome,
    maintainer: node.maintainer ?? "",
    remark: node.remark ?? "",
  };
}

function credentialPayload(form: CredentialState) {
  if (form.authType === "password") {
    return {
      credential: { authType: "password" as const, password: form.password },
    };
  }
  if (form.authType === "private_key") {
    return {
      credential: {
        authType: "private_key" as const,
        privateKey: form.privateKey,
        privateKeyPassphrase: form.privateKeyPassphrase || undefined,
      },
    };
  }
  return { credential: { authType: "generated_key" as const } };
}

function canManageNode(node: LoadNodeSummary, role?: string) {
  return node.scope === "workspace" || role === "admin";
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

async function copyText(text: string): Promise<{
  ok: boolean;
  reason?: string;
}> {
  try {
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch {
    return { ok: false, reason: "Clipboard access is unavailable." };
  }
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
  Overlay({ className }: { className?: string }) {
    const { onClose } = useContext(DialogContext);
    return (
      <div
        aria-hidden="true"
        className={className ?? "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"}
        onClick={onClose}
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
    children,
    className,
    onClick,
  }: {
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
  }) {
    const { onClose } = useContext(DialogContext);
    return (
      <button
        aria-label="Close"
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

function Plus({ className }: { className?: string }) {
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
      <path d="M5 12h14M12 5v14" />
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
      <path d="M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  );
}

function FileText({ className }: { className?: string }) {
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
      <path d="M10 9H8M16 13H8M16 17H8" />
    </svg>
  );
}

function PlayCircle({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" />
      <polygon points="10 8 16 12 10 16 10 8" />
    </svg>
  );
}

function Pencil({ className }: { className?: string }) {
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
      <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
      <path d="m15 5 4 4" />
    </svg>
  );
}

function KeyRound({ className }: { className?: string }) {
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
      <path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z" />
      <circle cx="16.5" cy="7.5" r="0.5" fill="currentColor" />
    </svg>
  );
}

function ShieldOff({ className }: { className?: string }) {
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
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1 1 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m2 2 20 20" />
    </svg>
  );
}

function Archive({ className }: { className?: string }) {
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
      <rect height="5" rx="1" width="20" x="2" y="3" />
      <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
      <path d="M10 12h4" />
    </svg>
  );
}

function Copy({ className }: { className?: string }) {
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
      <rect height="13" rx="2" ry="2" width="13" x="9" y="9" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
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
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}

export function LoadNodesPage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const role = session?.user.role;

  const [q, setQ] = useState("");
  const [scope, setScope] = useState<LoadNodeScope | "">("");
  const [status, setStatus] = useState<LoadNodeStatus | "">("");
  const [page, setPage] = useState(0);

  const [rows, setRows] = useState<LoadNodeSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [listError, setListError] = useState<unknown | null>(null);

  const [actionError, setActionError] = useState<string | null>(null);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const [editTarget, setEditTarget] = useState<LoadNodeSummary | null>(null);
  const [editForm, setEditForm] = useState<EditState | null>(null);
  const [editTrustedHostKey, setEditTrustedHostKey] =
    useState<LoadNodeSshHostKeyScanResponse | null>(null);
  const [isScanningKey, setIsScanningKey] = useState(false);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const [credentialTarget, setCredentialTarget] =
    useState<LoadNodeSummary | null>(null);
  const [credentialForm, setCredentialForm] =
    useState<CredentialState>(emptyCredentialForm);
  const [isSavingCredentials, setIsSavingCredentials] = useState(false);
  const [generatedKeyNode, setGeneratedKeyNode] =
    useState<LoadNodeSummary | null>(null);

  const [initConfirmTarget, setInitConfirmTarget] =
    useState<LoadNodeSummary | null>(null);
  const [initializingId, setInitializingId] = useState<string | null>(null);

  const [toggleId, setToggleId] = useState<string | null>(null);

  const [archiveTarget, setArchiveTarget] = useState<LoadNodeSummary | null>(
    null,
  );
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [isArchiving, setIsArchiving] = useState(false);

  const [logNode, setLogNode] = useState<LoadNodeSummary | null>(null);
  const [selectedAttemptId, setSelectedAttemptId] = useState<string | null>(
    null,
  );
  const [logAttempts, setLogAttempts] = useState<LoadNodeInitAttemptSummary[]>(
    [],
  );
  const [logDetail, setLogDetail] = useState<LoadNodeInitAttemptDetail | null>(
    null,
  );
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [isLogDetailLoading, setIsLogDetailLoading] = useState(false);
  const [logError, setLogError] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    if (!workspaceId) return;
    setIsFetching(true);
    try {
      const data = await listLoadNodes({
        workspaceId,
        q,
        scope,
        status,
        limit: pageSize,
        offset: page * pageSize,
        sort: "-createdAt",
      });
      setRows(data.items);
      setTotal(data.total);
      setListError(null);
    } catch (error) {
      setListError(error);
    } finally {
      setIsLoading(false);
      setIsFetching(false);
    }
  }, [workspaceId, q, scope, status, page]);

  useEffect(() => {
    if (session !== null) {
      void fetchList();
    }
  }, [session, fetchList]);

  const anyInitializing = rows.some((node) => node.status === "initializing");
  useEffect(() => {
    if (!anyInitializing) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void fetchList();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [anyInitializing, fetchList]);

  useEffect(() => {
    if (logNode === null || selectedAttemptId === null) {
      setLogDetail(null);
      return undefined;
    }
    let active = true;
    setIsLogDetailLoading(true);
    setLogError(null);
    getLoadNodeInitAttempt(logNode.id, selectedAttemptId, workspaceId)
      .then((detail) => {
        if (active) {
          setLogDetail(detail);
        }
      })
      .catch((error) => {
        if (active) {
          setLogDetail(null);
          setLogError(loadNodeErrorMessage(error));
        }
      })
      .finally(() => {
        if (active) {
          setIsLogDetailLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [logNode, selectedAttemptId, workspaceId]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const isFiltered = Boolean(q || scope || status);
  const editEndpointChanged =
    editTarget !== null &&
    editForm !== null &&
    (editForm.host !== editTarget.host ||
      editForm.sshPort !== editTarget.sshPort);

  const emptyCopy = useMemo(() => {
    if (isFiltered) {
      return "No load nodes match the current filters. Clear filters and try again.";
    }
    if (role === "admin") {
      return "No load nodes yet. Register a workspace node, or add a public node as an administrator.";
    }
    return "No workspace load nodes yet. Register a node for this workspace to get started.";
  }, [isFiltered, role]);

  if (session === null) {
    return null;
  }

  function updateSearch(value: string) {
    setQ(value);
    setPage(0);
  }

  function startEdit(node: LoadNodeSummary) {
    setActionError(null);
    setEditTarget(node);
    setEditForm(nodeToEdit(node));
    setEditTrustedHostKey(null);
  }

  function startCredentialUpdate(node: LoadNodeSummary) {
    setActionError(null);
    setCredentialTarget(node);
    setCredentialForm(emptyCredentialForm);
  }

  async function handleCopy(text: string) {
    setCopyFeedback(null);
    const result = await copyText(text);
    setCopyFeedback(result.ok ? "Copied." : result.reason ?? "Copy failed.");
  }

  async function handleScanKey() {
    if (!editTarget || !editForm) return;
    setIsScanningKey(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      const result = await scanLoadNodeSshHostKey(
        {
          scope: editTarget.scope,
          host: editForm.host,
          sshPort: editForm.sshPort,
        },
        workspaceId,
        token,
      );
      setEditTrustedHostKey(result);
    } catch (error) {
      setEditTrustedHostKey(null);
      setActionError(loadNodeErrorMessage(error));
    } finally {
      setIsScanningKey(false);
    }
  }

  async function handleSaveEdit() {
    if (!editTarget || !editForm) return;
    const endpointChanged =
      editForm.host !== editTarget.host ||
      editForm.sshPort !== editTarget.sshPort;
    setIsSavingEdit(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      if (endpointChanged && editTrustedHostKey === null) {
        throw new Error(
          "Scan and confirm the SSH host key before saving host or port changes.",
        );
      }
      const updated = await patchLoadNode(
        editTarget.id,
        editForm,
        workspaceId,
        token,
      );
      if (endpointChanged && editTrustedHostKey !== null) {
        await trustLoadNodeSshHostKey(
          updated.id,
          {
            algorithm: editTrustedHostKey.algorithm,
            publicKey: editTrustedHostKey.publicKey,
            fingerprintSha256: editTrustedHostKey.fingerprintSha256,
          },
          workspaceId,
          token,
        );
      }
      setEditTarget(null);
      setEditForm(null);
      setEditTrustedHostKey(null);
      await fetchList();
    } catch (error) {
      if (error instanceof Error && !("body" in error)) {
        setActionError(error.message);
      } else {
        setActionError(loadNodeErrorMessage(error));
      }
    } finally {
      setIsSavingEdit(false);
    }
  }

  async function handleSaveCredentials() {
    if (!credentialTarget) return;
    setIsSavingCredentials(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      const node = await updateLoadNodeCredentials(
        credentialTarget.id,
        credentialPayload(credentialForm),
        workspaceId,
        token,
      );
      setCredentialTarget(null);
      setCredentialForm(emptyCredentialForm);
      setGeneratedKeyNode(node.generatedPublicKey ? node : null);
      await fetchList();
    } catch (error) {
      setActionError(loadNodeErrorMessage(error));
    } finally {
      setIsSavingCredentials(false);
    }
  }

  async function handleConfirmInitialize() {
    if (!initConfirmTarget) return;
    const node = initConfirmTarget;
    setInitConfirmTarget(null);
    setInitializingId(node.id);
    setActionError(null);
    try {
      const token = await getWriteToken();
      await initializeLoadNode(
        node.id,
        workspaceId,
        token,
        node.status === "idle",
      );
    } catch (error) {
      setActionError(loadNodeErrorMessage(error));
    } finally {
      setInitializingId(null);
      await fetchList();
    }
  }

  async function handleToggle(node: LoadNodeSummary) {
    setToggleId(node.id);
    setActionError(null);
    try {
      const token = await getWriteToken();
      if (node.status === "disabled") {
        await enableLoadNode(node.id, workspaceId, token);
      } else {
        await disableLoadNode(
          node.id,
          workspaceId,
          token,
          "Disabled from Load Nodes page",
        );
      }
      await fetchList();
    } catch (error) {
      setActionError(loadNodeErrorMessage(error));
    } finally {
      setToggleId(null);
    }
  }

  async function handleArchive() {
    if (!archiveTarget) return;
    setIsArchiving(true);
    setArchiveError(null);
    try {
      const token = await getWriteToken();
      await deleteLoadNode(archiveTarget.id, workspaceId, token);
      if (rows.length === 1 && page > 0) {
        setPage((current) => Math.max(0, current - 1));
      }
      setArchiveTarget(null);
      await fetchList();
    } catch (error) {
      setArchiveError(loadNodeErrorMessage(error));
    } finally {
      setIsArchiving(false);
    }
  }

  async function openLogs(node: LoadNodeSummary) {
    setLogNode(node);
    setSelectedAttemptId(node.lastInitAttemptId ?? null);
    setLogAttempts([]);
    setLogDetail(null);
    setLogError(null);
    setIsLogsLoading(true);
    try {
      const data = await listLoadNodeInitAttempts(node.id, workspaceId);
      setLogAttempts(data.items);
      setSelectedAttemptId(
        (current) =>
          current ?? data.items[0]?.id ?? null,
      );
    } catch (error) {
      setLogError(loadNodeErrorMessage(error));
    } finally {
      setIsLogsLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-container-max flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-[34px] font-semibold leading-10 text-white">
            Load Nodes
          </h1>
          <p className="mt-2 max-w-3xl text-base leading-6 text-text-muted">
            Manage workspace and public load nodes. Register and initialize
            nodes, then keep connection settings and credentials up to date.
          </p>
        </div>
        <a
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110"
          href="/resources/load-nodes/new"
        >
          <Plus className="h-4 w-4" />
          Register Load Node
        </a>
      </div>

      {actionError ? (
        <div className="rounded-xl border border-error/30 bg-error/10 p-4 text-sm text-error">
          {actionError}
        </div>
      ) : null}

      <div className="grid gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-4 lg:grid-cols-[1fr_auto_auto_auto] lg:items-center">
        <label className="relative block w-full">
          <span className="sr-only">Search Load Nodes</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary" />
          <input
            className="h-11 w-full rounded-lg border border-white/10 bg-surface-container-low px-10 text-sm text-text-main outline-none transition placeholder:text-secondary focus:border-primary/50"
            onChange={(event) => updateSearch(event.target.value)}
            placeholder="Search by host, SSH user, or maintainer..."
            value={q}
          />
        </label>
        <select
          aria-label="Scope filter"
          className="h-11 rounded-lg border border-white/10 bg-surface-container-low px-3 text-sm text-text-main"
          onChange={(event) => {
            setScope(event.target.value as LoadNodeScope | "");
            setPage(0);
          }}
          value={scope}
        >
          <option value="">All scopes</option>
          <option value="public">Public</option>
          <option value="workspace">Private</option>
        </select>
        <select
          aria-label="Status filter"
          className="h-11 rounded-lg border border-white/10 bg-surface-container-low px-3 text-sm text-text-main"
          onChange={(event) => {
            setStatus(event.target.value as LoadNodeStatus | "");
            setPage(0);
          }}
          value={status}
        >
          <option value="">All statuses</option>
          {statuses.map((item) => (
            <option key={item} value={item}>
              {statusCopy[item]}
            </option>
          ))}
        </select>
        <button
          className="inline-flex h-11 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5"
          onClick={() => void fetchList()}
          type="button"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <section className="surgepilot-glass overflow-hidden rounded-xl">
        {isLoading ? (
          <div className="p-8 text-sm text-text-muted">
            Loading Load Nodes...
          </div>
        ) : null}
        {listError ? (
          <div className="flex items-center justify-between gap-4 p-8">
            <p className="text-sm text-error">
              {loadNodeErrorMessage(listError)}
            </p>
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
        {!isLoading && !listError && rows.length === 0 ? (
          <div className="mx-auto flex max-w-md flex-col items-center p-10 text-center">
            <div className="grid h-14 w-14 place-items-center rounded-2xl border border-primary/20 bg-primary-container/10 text-primary">
              <Plus className="h-7 w-7" />
            </div>
            <h2 className="mt-5 text-lg font-semibold leading-7 text-white">
              No Load Nodes yet
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              {emptyCopy}
            </p>
            {isFiltered ? (
              <button
                className="mt-4 inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main"
                onClick={() => {
                  setQ("");
                  setScope("");
                  setStatus("");
                  setPage(0);
                }}
                type="button"
              >
                Clear filters
              </button>
            ) : null}
          </div>
        ) : null}
        {rows.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-left">
                <thead className="border-b border-white/10 bg-white/5">
                  <tr>
                    {[
                      "Host",
                      "Scope",
                      "Status",
                      "Maintainer",
                      "Last checked",
                      "Agent",
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
                  {rows.map((node) => {
                    const manageable = canManageNode(node, role);
                    const busy = node.status === "busy";
                    const pendingAction =
                      initializingId === node.id || toggleId === node.id;
                    const canEditStatus = allowedEditStatuses.has(node.status);
                    return (
                      <tr
                        className="transition hover:bg-white/[0.03]"
                        key={node.id}
                      >
                        <td className="px-5 py-4">
                          <div className="font-semibold text-white">
                            {node.host}
                          </div>
                          <div className="font-mono text-xs text-secondary">
                            {node.sshUser}:{node.sshPort}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-sm text-text-muted">
                          {node.scope === "public" ? "Public" : "Private"}
                        </td>
                        <td className="px-5 py-4">
                          <span
                            className={cn(
                              "inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold",
                              statusTone(node.status),
                            )}
                          >
                            {statusCopy[node.status]}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-sm text-text-muted">
                          {node.maintainer ?? "—"}
                        </td>
                        <td className="px-5 py-4 font-mono text-xs text-text-muted">
                          {formatDate(node.lastCheckedAt)}
                        </td>
                        <td className="px-5 py-4">
                          <div className="text-sm text-text-muted">
                            {node.runnerVersion ?? "—"}
                          </div>
                          <div className="font-mono text-xs text-secondary">
                            Current Run: {node.currentRunId ?? "—"}
                          </div>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex justify-end gap-2">
                            <IconButton
                              label={`View initialization logs for ${node.host}`}
                              onClick={() => void openLogs(node)}
                            >
                              <FileText className="h-4 w-4" />
                            </IconButton>
                            {manageable ? (
                              <>
                                <IconButton
                                  disabled={
                                    pendingAction ||
                                    node.status === "busy" ||
                                    node.status === "disabled" ||
                                    node.status === "quarantined"
                                  }
                                  label={
                                    node.status === "idle"
                                      ? `Reinitialize ${node.host}`
                                      : `Initialize ${node.host}`
                                  }
                                  onClick={() => setInitConfirmTarget(node)}
                                >
                                  <PlayCircle className="h-4 w-4" />
                                </IconButton>
                                <IconButton
                                  disabled={
                                    pendingAction || !canEditStatus
                                  }
                                  label={`Edit ${node.host}`}
                                  onClick={() => startEdit(node)}
                                >
                                  <Pencil className="h-4 w-4" />
                                </IconButton>
                                <IconButton
                                  disabled={
                                    pendingAction || !canEditStatus
                                  }
                                  label={`Update credentials for ${node.host}`}
                                  onClick={() =>
                                    startCredentialUpdate(node)
                                  }
                                >
                                  <KeyRound className="h-4 w-4" />
                                </IconButton>
                                <IconButton
                                  disabled={pendingAction || busy}
                                  label={
                                    node.status === "disabled"
                                      ? `Enable ${node.host}`
                                      : `Disable ${node.host}`
                                  }
                                  onClick={() => void handleToggle(node)}
                                >
                                  <ShieldOff className="h-4 w-4" />
                                </IconButton>
                                <IconButton
                                  disabled={pendingAction || busy}
                                  label={`Archive ${node.host}`}
                                  onClick={() => {
                                    setArchiveError(null);
                                    setArchiveTarget(node);
                                  }}
                                >
                                  <Archive className="h-4 w-4" />
                                </IconButton>
                              </>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-white/10 px-5 py-4">
              <div className="font-mono text-[12px] uppercase tracking-wide text-secondary">
                <span className="text-text-main">{total}</span> node(s)
              </div>
              <div className="flex gap-2">
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={page === 0 || isFetching}
                  onClick={() => setPage((current) => Math.max(0, current - 1))}
                  type="button"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous page
                </button>
                <button
                  className="inline-flex h-9 items-center gap-2 rounded-lg border border-white/10 px-3 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={page + 1 >= totalPages || isFetching}
                  onClick={() => setPage((current) => current + 1)}
                  type="button"
                >
                  Next page
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </>
        ) : null}
      </section>

      <Dialog.Root
        open={editTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditTarget(null);
            setEditForm(null);
            setEditTrustedHostKey(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Edit Load Node"
            className="fixed right-0 top-0 z-50 flex h-dvh w-full max-w-2xl flex-col border-l border-white/10 bg-surface-container-low shadow-2xl"
          >
            <div className="flex items-start justify-between border-b border-white/10 p-6">
              <div>
                <Dialog.Title className="text-xl font-semibold text-white">
                  Edit Load Node
                </Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-text-muted">
                  Updating the endpoint or metadata marks the node for
                  re-initialization.
                </Dialog.Description>
              </div>
              <Dialog.Close
                className="rounded-lg p-2 text-secondary transition hover:bg-white/5 hover:text-white"
                onClick={() => {
                  setEditTarget(null);
                  setEditForm(null);
                  setEditTrustedHostKey(null);
                }}
              >
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>
            {editTarget && editForm ? (
              <form
                className="flex min-h-0 flex-1 flex-col"
                onSubmit={(event) => {
                  event.preventDefault();
                  void handleSaveEdit();
                }}
              >
                <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
                  {actionError ? (
                    <div className="rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                      {actionError}
                    </div>
                  ) : null}
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="Host">
                      <input
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) => {
                          setEditTrustedHostKey(null);
                          setEditForm({
                            ...editForm,
                            host: event.target.value,
                          });
                        }}
                        value={editForm.host ?? ""}
                      />
                    </Field>
                    <Field label="Port">
                      <input
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) => {
                          setEditTrustedHostKey(null);
                          setEditForm({
                            ...editForm,
                            sshPort: Number(event.target.value),
                          });
                        }}
                        type="number"
                        value={editForm.sshPort ?? 22}
                      />
                    </Field>
                    <Field label="SSH user">
                      <input
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) =>
                          setEditForm({
                            ...editForm,
                            sshUser: event.target.value,
                          })
                        }
                        value={editForm.sshUser ?? ""}
                      />
                    </Field>
                    <Field label="Runner home">
                      <input
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) =>
                          setEditForm({
                            ...editForm,
                            runnerHome: event.target.value,
                          })
                        }
                        value={editForm.runnerHome ?? ""}
                      />
                    </Field>
                    <Field label="Maintainer">
                      <input
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) =>
                          setEditForm({
                            ...editForm,
                            maintainer: event.target.value,
                          })
                        }
                        value={editForm.maintainer ?? ""}
                      />
                    </Field>
                    <Field label="Remark">
                      <input
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) =>
                          setEditForm({
                            ...editForm,
                            remark: event.target.value,
                          })
                        }
                        value={editForm.remark ?? ""}
                      />
                    </Field>
                  </div>
                  {editEndpointChanged ? (
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-white">
                            SSH host key trust required
                          </div>
                          <p className="mt-1 text-xs text-text-muted">
                            Host or port changes clear the previous trusted
                            key. Scan and confirm the new endpoint before
                            saving.
                          </p>
                        </div>
                        <button
                          className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-primary/30 px-3 py-2 text-sm font-semibold text-primary transition hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={isScanningKey || !editForm.host}
                          onClick={() => void handleScanKey()}
                          type="button"
                        >
                          <KeyRound className="h-4 w-4" />
                          {isScanningKey ? "Scanning..." : "Scan key"}
                        </button>
                      </div>
                      {editTrustedHostKey ? (
                        <div className="mt-3 rounded-xl border border-success/25 bg-success/10 p-3">
                          <div className="text-xs uppercase tracking-[0.18em] text-success">
                            Trusted for {editTrustedHostKey.host}:
                            {editTrustedHostKey.sshPort}
                          </div>
                          <dl className="mt-3 grid gap-2 text-xs text-text-main">
                            <div>
                              <dt className="text-text-muted">Algorithm</dt>
                              <dd className="font-mono">
                                {editTrustedHostKey.algorithm}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-text-muted">
                                SHA256 fingerprint
                              </dt>
                              <dd className="break-all font-mono">
                                {editTrustedHostKey.fingerprintSha256}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-text-muted">
                                known_hosts line
                              </dt>
                              <dd className="break-all font-mono">
                                {editTrustedHostKey.knownHostsLine}
                              </dd>
                            </div>
                          </dl>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
                <div className="flex justify-end gap-3 border-t border-white/10 p-6">
                  <Dialog.Close
                    className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main"
                    onClick={() => {
                      setEditTarget(null);
                      setEditForm(null);
                      setEditTrustedHostKey(null);
                    }}
                  >
                    Cancel
                  </Dialog.Close>
                  <button
                    className="rounded-lg bg-primary-container px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={isSavingEdit}
                    type="submit"
                  >
                    {isSavingEdit ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </form>
            ) : null}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={credentialTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCredentialTarget(null);
            setCredentialForm(emptyCredentialForm);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Update connection credentials"
            className="fixed right-0 top-0 z-50 flex h-dvh w-full max-w-xl flex-col border-l border-white/10 bg-surface-container-low shadow-2xl"
          >
            <div className="flex items-start justify-between border-b border-white/10 p-6">
              <div>
                <Dialog.Title className="text-xl font-semibold text-white">
                  Update connection credentials
                </Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-text-muted">
                  Existing SSH credentials are write-only. Replacing them
                  resets the node and requires initialization again.
                </Dialog.Description>
              </div>
              <Dialog.Close
                className="rounded-lg p-2 text-secondary transition hover:bg-white/5 hover:text-white"
                onClick={() => {
                  setCredentialTarget(null);
                  setCredentialForm(emptyCredentialForm);
                }}
              >
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>
            <form
              className="flex min-h-0 flex-1 flex-col"
              onSubmit={(event) => {
                event.preventDefault();
                void handleSaveCredentials();
              }}
            >
              <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-6">
                {actionError ? (
                  <div className="rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                    {actionError}
                  </div>
                ) : null}
                <Field label="Authentication method">
                  <select
                    className={cn(inputClass(), "text-text-main")}
                    onChange={(event) =>
                      setCredentialForm({
                        ...credentialForm,
                        authType: event.target.value as LoadNodeAuthType,
                      })
                    }
                    value={credentialForm.authType}
                  >
                    <option value="password">Password</option>
                    <option value="private_key">SSH private key</option>
                    <option value="generated_key">Generate keypair</option>
                  </select>
                </Field>
                {credentialForm.authType === "password" ? (
                  <Field label="Password">
                    <input
                      autoComplete="new-password"
                      className={cn(inputClass(), "text-text-main")}
                      onChange={(event) =>
                        setCredentialForm({
                          ...credentialForm,
                          password: event.target.value,
                        })
                      }
                      type="password"
                      value={credentialForm.password}
                    />
                  </Field>
                ) : null}
                {credentialForm.authType === "private_key" ? (
                  <>
                    <Field label="SSH private key">
                      <textarea
                        className={cn(
                          inputClass(),
                          "min-h-32 resize-y py-3 font-mono text-xs text-text-main",
                        )}
                        onChange={(event) =>
                          setCredentialForm({
                            ...credentialForm,
                            privateKey: event.target.value,
                          })
                        }
                        value={credentialForm.privateKey}
                      />
                    </Field>
                    <Field label="Private key passphrase (optional)">
                      <input
                        autoComplete="new-password"
                        className={cn(inputClass(), "text-text-main")}
                        onChange={(event) =>
                          setCredentialForm({
                            ...credentialForm,
                            privateKeyPassphrase: event.target.value,
                          })
                        }
                        type="password"
                        value={credentialForm.privateKeyPassphrase}
                      />
                    </Field>
                  </>
                ) : null}
                {credentialForm.authType === "generated_key" ? (
                  <div className="rounded-xl border border-primary/20 bg-primary/10 p-4 text-sm text-primary">
                    SurgePilot will generate a new key pair, encrypt the
                    private key, and return only the public key.
                  </div>
                ) : null}
              </div>
              <div className="flex justify-end gap-3 border-t border-white/10 p-6">
                <Dialog.Close
                  className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main"
                  onClick={() => {
                    setCredentialTarget(null);
                    setCredentialForm(emptyCredentialForm);
                  }}
                >
                  Cancel
                </Dialog.Close>
                <button
                  className="rounded-lg bg-primary-container px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={isSavingCredentials}
                  type="submit"
                >
                  {isSavingCredentials ? "Saving..." : "Replace Credentials"}
                </button>
              </div>
            </form>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={initConfirmTarget !== null}
        onOpenChange={(open) => {
          if (!open) setInitConfirmTarget(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Initialize Load Node"
            className="fixed left-1/2 top-1/2 z-50 w-[min(460px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
          >
            <Dialog.Title className="text-lg font-semibold text-white">
              {initConfirmTarget?.status === "idle"
                ? "Reinitialize Load Node?"
                : "Initialize Load Node?"}
            </Dialog.Title>
            <Dialog.Description className="mt-3 text-sm leading-6 text-text-muted">
              {initConfirmTarget?.status === "idle"
                ? `${initConfirmTarget.host} is currently idle. Reinitializing will replace runner files and re-check prerequisites before the node is used again.`
                : `${initConfirmTarget?.host ?? "This node"} will be initialized with the current runner bundle and prerequisite checks.`}
            </Dialog.Description>
            <div className="mt-6 flex justify-end gap-3">
              <Dialog.Close
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main"
                onClick={() => setInitConfirmTarget(null)}
              >
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-primary px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary"
                onClick={() => void handleConfirmInitialize()}
                type="button"
              >
                {initConfirmTarget?.status === "idle"
                  ? "Reinitialize"
                  : "Initialize"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={generatedKeyNode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setGeneratedKeyNode(null);
            setCopyFeedback(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Generated public key"
            className="fixed left-1/2 top-1/2 z-50 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
          >
            <Dialog.Title className="text-lg font-semibold text-white">
              Generated public key
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm leading-6 text-text-muted">
              Add this public key to the target host before initializing the
              node. The private key is encrypted and never displayed.
            </Dialog.Description>
            <div className="mt-5 rounded-xl border border-white/10 bg-black/30 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-mono text-xs uppercase tracking-[0.18em] text-primary">
                  Installation key
                </span>
                <button
                  className="inline-flex items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!generatedKeyNode?.generatedPublicKey}
                  onClick={() =>
                    void handleCopy(generatedKeyNode?.generatedPublicKey ?? "")
                  }
                  type="button"
                >
                  <Copy className="h-3 w-3" />
                  Copy
                </button>
              </div>
              {copyFeedback ? (
                <p className="mb-2 text-xs text-text-muted">{copyFeedback}</p>
              ) : null}
              <pre className="whitespace-pre-wrap break-all font-mono text-xs text-text-main">
                {generatedKeyNode?.generatedPublicKey}
              </pre>
            </div>
            <div className="mt-5 flex justify-end">
              <button
                className="rounded-lg bg-primary px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-on-primary"
                onClick={() => {
                  setGeneratedKeyNode(null);
                  setCopyFeedback(null);
                }}
                type="button"
              >
                Done
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={archiveTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setArchiveTarget(null);
            setArchiveError(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Archive Load Node"
            className="fixed left-1/2 top-1/2 z-50 w-[min(440px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
          >
            <Dialog.Title className="text-lg font-semibold text-white">
              Archive Load Node
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm leading-6 text-text-muted">
              Archive {archiveTarget?.host}? Archived nodes are hidden from the
              default list.
            </Dialog.Description>
            {archiveError ? (
              <p className="mt-4 text-sm text-error">{archiveError}</p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <Dialog.Close
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main"
                onClick={() => {
                  setArchiveTarget(null);
                  setArchiveError(null);
                }}
              >
                Cancel
              </Dialog.Close>
              <button
                className="rounded-lg bg-error px-4 py-2 font-mono text-[12px] font-bold uppercase tracking-wide text-white disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isArchiving}
                onClick={() => void handleArchive()}
                type="button"
              >
                {isArchiving ? "Archiving..." : "Archive"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <Dialog.Root
        open={logNode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setLogNode(null);
            setSelectedAttemptId(null);
            setLogAttempts([]);
            setLogDetail(null);
            setLogError(null);
            setCopyFeedback(null);
          }
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
          <Dialog.Content
            aria-label="Initialization log"
            className="fixed left-1/2 top-1/2 z-50 grid max-h-[82vh] w-[min(960px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 grid-rows-[auto_1fr] gap-4 overflow-hidden rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <Dialog.Title className="text-xl font-semibold text-white">
                  Initialization log
                </Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-text-muted">
                  Sanitized setup output for {logNode?.host}.
                </Dialog.Description>
              </div>
              <Dialog.Close
                className="rounded-lg p-2 text-secondary transition hover:bg-white/5 hover:text-white"
                onClick={() => {
                  setLogNode(null);
                  setSelectedAttemptId(null);
                  setLogAttempts([]);
                  setLogDetail(null);
                  setLogError(null);
                  setCopyFeedback(null);
                }}
              >
                <X className="h-5 w-5" />
              </Dialog.Close>
            </div>
            <div className="grid min-h-0 gap-4 md:grid-cols-[260px_1fr]">
              <div className="min-h-0 space-y-2 overflow-auto">
                {isLogsLoading ? (
                  <p className="text-sm text-text-muted">
                    Loading attempts...
                  </p>
                ) : null}
                {logError ? (
                  <p className="text-sm text-error">{logError}</p>
                ) : null}
                {!isLogsLoading && !logError && logAttempts.length === 0 ? (
                  <p className="text-sm text-text-muted">No attempts yet.</p>
                ) : null}
                {logAttempts.map((attempt) => (
                  <button
                    className={cn(
                      "w-full rounded-xl border px-3 py-2 text-left text-sm transition hover:bg-white/5",
                      selectedAttemptId === attempt.id
                        ? "border-primary bg-primary/10"
                        : "border-white/10 bg-white/[0.03]",
                    )}
                    key={attempt.id}
                    onClick={() => setSelectedAttemptId(attempt.id)}
                    type="button"
                  >
                    <div className="font-mono text-xs text-secondary">
                      {attempt.id.slice(-6)}
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span
                        className={cn(
                          "inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                          attemptStatusTone(attempt.status),
                        )}
                      >
                        {attemptStatusCopy[attempt.status]}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-text-muted">
                      {attempt.errorCode ?? attempt.message ?? "—"}
                    </div>
                  </button>
                ))}
              </div>
              <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-black/30">
                <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
                  <div className="min-w-0 flex-1 text-xs text-text-muted">
                    {logDetail?.status ? (
                      <span className="font-semibold text-text-main">
                        {attemptStatusCopy[logDetail.status]}
                      </span>
                    ) : null}{" "}
                    {logDetail?.errorCode ??
                      logDetail?.message ??
                      "Sanitized setup output"}
                  </div>
                  <button
                    className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={!logDetail?.sanitizedLogTail}
                    onClick={() =>
                      void handleCopy(logDetail?.sanitizedLogTail ?? "")
                    }
                    type="button"
                  >
                    <Copy className="h-3 w-3" />
                    Copy
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-auto p-4">
                  {isLogDetailLoading ? (
                    <p className="text-sm text-text-muted">
                      Loading setup output...
                    </p>
                  ) : (
                    <pre className="whitespace-pre-wrap font-mono text-xs leading-5 text-text-main">
                      {logDetail?.sanitizedLogTail ?? "No setup output recorded."}
                    </pre>
                  )}
                </div>
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}

function inputClass() {
  return "h-10 w-full rounded-lg border border-white/10 bg-surface-container px-3 text-sm outline-none transition focus:border-primary/50";
}

function Field({
  children,
  error,
  label,
}: Readonly<{ children: React.ReactNode; error?: string; label: string }>) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-text-main">
        {label}
      </span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs text-error">{error}</span>
      ) : null}
    </label>
  );
}
