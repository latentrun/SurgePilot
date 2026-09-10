import { useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  cloneScenario,
  createRun,
  deleteScenario,
  getCsrfToken,
  getScenario,
  listDependencyFiles,
  listEnvGroups,
  listLoadNodes,
  patchScenario,
  type DependencyFileSummary,
  type EnvGroupSummary,
  type LoadNodeSummary,
  type ScenarioDetail,
  type ScenarioStep,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { useWorkspaceSwitchGuard } from "../../../app/workspace-switch-guard";
import { scenarioCopy } from "../copy";
import {
  cloneStep,
  newAssertion,
  newDataSource,
  newExtractor,
  newFormField,
  newNamedValue,
  newScript,
  newStep,
  newUploadFile,
  toPatchPayload,
  type ScenarioAssertion,
  type ScenarioDataSource,
  type ScenarioExtractor,
  type ScenarioFormField,
  type ScenarioNamedValue,
  type ScenarioScript,
  type ScenarioUploadFile,
} from "../model";

const HTTP_METHODS = [
  "GET",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
  "HEAD",
  "OPTIONS",
];
const EXTRACTOR_SUBJECTS = ["body", "headers", "code", "message", "url"];
const RAW_CONTENT_TYPES = [
  "application/json",
  "application/xml",
  "text/plain",
  "text/html",
  "application/x-www-form-urlencoded",
  "application/graphql",
];
const DELIMITER_OPTIONS = [
  { label: "Comma (,)", value: "," },
  { label: "Semicolon (;)", value: ";" },
  { label: "Tab", value: "tab" },
  { label: "Pipe (|)", value: "|" },
];

type StepTabKey =
  | "params"
  | "headers"
  | "body"
  | "files"
  | "extractors"
  | "assertions"
  | "scripts"
  | "settings";

const stepTabs: Array<{ key: StepTabKey; label: string }> = [
  { key: "params", label: "Params" },
  { key: "headers", label: "Headers" },
  { key: "body", label: "Body" },
  { key: "files", label: "Files" },
  { key: "extractors", label: "Extractors" },
  { key: "assertions", label: "Assertions" },
  { key: "scripts", label: "Scripts" },
  { key: "settings", label: "Settings" },
];

type ConfigTabKey = "settings" | "dataSources";
const configTabs: Array<{ key: ConfigTabKey; label: string }> = [
  { key: "settings", label: "Settings" },
  { key: "dataSources", label: "Data Sources" },
];

function currentScenarioId() {
  const segments = window.location.pathname.split("/").filter(Boolean);
  return segments[1] ?? "";
}

function useCsrfToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function cn(...inputs: (string | boolean | null | undefined)[]) {
  return inputs.filter(Boolean).join(" ");
}

function textInputClass(extra = "") {
  return cn(
    "w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-text-main outline-none transition focus:border-primary/50",
    extra,
  );
}

function inputClass(hasError: boolean) {
  return cn(
    "h-10 w-full rounded-lg border bg-surface-container px-3 text-sm text-text-main outline-none transition focus:border-primary/50",
    hasError ? "border-error/60" : "border-white/10",
  );
}

function navigateTo(path: string) {
  window.history.replaceState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function errorMessage(error: unknown, action: "save" | "debug" = "debug") {
  const code = (error as ApiError | undefined)?.body?.code;
  if (code === "SCENARIO_REVISION_CONFLICT") {
    return "Scenario changed elsewhere. Reload and try again.";
  }
  if (code === "LOAD_NODE_BUSY") {
    return "Selected Load Node is no longer idle. Pick another node.";
  }
  if (code === "VALIDATION_ERROR") {
    return action === "save"
      ? "Scenario needs attention before it can be saved."
      : "Scenario needs attention before the Debug Run can start.";
  }
  if (code === "RESOURCE_NOT_FOUND") {
    return "The Scenario does not exist or is no longer visible.";
  }
  return "Action failed. Refresh and try again.";
}

function lifecycleErrorMessage(error: unknown) {
  const code = (error as ApiError | undefined)?.body?.code;
  if (code === "RESOURCE_IN_USE") {
    return scenarioCopy.resourceInUse;
  }
  if (code === "WORKSPACE_ACCESS_DENIED") {
    return "You do not have access to this workspace.";
  }
  return errorMessage(error, "save");
}

function isRevisionConflict(error: unknown) {
  return (
    (error as ApiError | undefined)?.body?.code ===
    "SCENARIO_REVISION_CONFLICT"
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function urlPreview(detail: ScenarioDetail, step: ScenarioStep | undefined) {
  if (!step) return detail.baseUrlExpression;
  const query = (step.queryParams ?? [])
    .filter((item) => item.enabled !== false)
    .map((item) => `${item.name}=${item.value}`)
    .join("&");
  return `${detail.baseUrlExpression}${step.path}${query ? `?${query}` : ""}`;
}

function parseCsvNames(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function booleanOverrideValue(value: boolean | null | undefined) {
  if (value === true) return "true";
  if (value === false) return "false";
  return "";
}

function parseBooleanOverride(value: string) {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

function scriptsEnabled(detail: ScenarioDetail) {
  return detail.steps.some(
    (step) =>
      step.enabled !== false &&
      (step.scripts ?? []).some((script) => script.enabled !== false),
  );
}

function stepBody(step: ScenarioStep) {
  return (
    step.body ?? {
      type: "none" as const,
      contentType: null,
      rawText: null,
      formFields: [],
    }
  );
}

function navigateToLoadNodes() {
  window.history.replaceState({}, "", "/resources/load-nodes");
  window.dispatchEvent(new PopStateEvent("popstate"));
}

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
      <rect height="14" rx="2" ry="2" width="14" x="8" y="8" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
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

function FieldSection({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white">{title}</h3>
          {description ? (
            <p className="mt-1 text-sm text-text-muted">{description}</p>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function MiniButton({
  children,
  onClick,
  tone = "neutral",
  disabled = false,
}: {
  children: React.ReactNode;
  onClick: () => void;
  tone?: "neutral" | "danger" | "primary";
  disabled?: boolean;
}) {
  const toneClass =
    tone === "primary"
      ? "border-primary/40 bg-primary/10 text-primary"
      : tone === "danger"
        ? "border-error/30 text-error"
        : "border-white/10 text-white";
  return (
    <button
      className={cn(
        "rounded-lg border px-3 py-1.5 text-xs transition hover:bg-white/5",
        toneClass,
        disabled && "cursor-not-allowed opacity-40",
      )}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function NamedValueRows({
  label,
  items,
  onChange,
  onRemove,
}: {
  label: string;
  items: ScenarioNamedValue[] | undefined;
  onChange: (id: string, fields: Partial<ScenarioNamedValue>) => void;
  onRemove: (id: string) => void;
}) {
  const rows = items ?? [];
  return (
    <div className="space-y-2">
      {rows.map((item, index) => (
        <div
          className="grid gap-2 rounded-xl border border-white/10 bg-black/10 p-3 md:grid-cols-[1fr_1fr_auto_auto]"
          key={item.id}
        >
          <label className="grid gap-1 text-xs text-text-muted">
            {label} {index + 1} name
            <input
              aria-label={`${label} ${index + 1} name`}
              className={textInputClass("font-mono")}
              onChange={(event) => onChange(item.id, { name: event.target.value })}
              value={item.name}
            />
          </label>
          <label className="grid gap-1 text-xs text-text-muted">
            {label} {index + 1} value
            <input
              aria-label={`${label} ${index + 1} value`}
              className={textInputClass("font-mono")}
              onChange={(event) =>
                onChange(item.id, { value: event.target.value })
              }
              value={item.value}
            />
          </label>
          <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
            <input
              checked={item.enabled !== false}
              onChange={(event) =>
                onChange(item.id, { enabled: event.target.checked })
              }
              type="checkbox"
            />
            Enabled
          </label>
          <div className="flex items-end">
            <MiniButton onClick={() => onRemove(item.id)} tone="danger">
              Remove
            </MiniButton>
          </div>
        </div>
      ))}
      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">No {label.toLowerCase()} yet.</p>
      ) : null}
    </div>
  );
}

export function ScenarioDesignerPage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const scenarioId = currentScenarioId();

  const [draft, setDraft] = useState<ScenarioDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isReloading, setIsReloading] = useState(false);

  const [dirty, setDirty] = useState(false);
  const [renamingName, setRenamingName] = useState(false);
  const [tagText, setTagText] = useState("");
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [activeStepTab, setActiveStepTab] = useState<StepTabKey>("params");
  const [actionError, setActionError] = useState<string | null>(null);

  const [envGroups, setEnvGroups] = useState<EnvGroupSummary[]>([]);
  const [dependencyFiles, setDependencyFiles] = useState<
    DependencyFileSummary[]
  >([]);
  const [idleNodes, setIdleNodes] = useState<LoadNodeSummary[]>([]);
  const [isLoadingNodes, setIsLoadingNodes] = useState(false);

  const [showConfig, setShowConfig] = useState(false);
  const [activeConfigTab, setActiveConfigTab] =
    useState<ConfigTabKey>("settings");
  const configBackupRef = useRef<{
    draft: ScenarioDetail | null;
    dirty: boolean;
  } | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [selectedEnvId, setSelectedEnvId] = useState(
    () =>
      window.localStorage.getItem(
        `surgepilot:scenario:${currentScenarioId()}:env`,
      ) ?? "",
  );
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [isStartingDebug, setIsStartingDebug] = useState(false);
  const [needsReload, setNeedsReload] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);

  const envStorageKey = `surgepilot:scenario:${scenarioId}:env`;

  const fetchScenario = useMemo(
    () => async () => {
      if (!workspaceId || !scenarioId) return;
      setIsLoading(true);
      setLoadError(null);
      try {
        const data = await getScenario(scenarioId, workspaceId);
        setDraft(data);
        setTagText(data.tags.join(", "));
        setSelectedStepId(data.steps[0]?.id ?? null);
        setDirty(false);
        setRenamingName(false);
      } catch (error) {
        setLoadError(errorMessage(error, "save"));
      } finally {
        setIsLoading(false);
      }
    },
    [scenarioId, workspaceId],
  );

  useEffect(() => {
    if (session !== null) {
      void fetchScenario();
    }
  }, [session, fetchScenario]);

  useEffect(() => {
    if (!workspaceId) return;
    let active = true;
    listEnvGroups({ workspaceId, pageSize: 100, sort: "name" })
      .then((data) => {
        if (active) setEnvGroups(data.items);
      })
      .catch(() => {
        if (active) setEnvGroups([]);
      });
    listDependencyFiles({ workspaceId, pageSize: 100, sort: "filename" })
      .then((data) => {
        if (active) setDependencyFiles(data.items);
      })
      .catch(() => {
        if (active) setDependencyFiles([]);
      });
    return () => {
      active = false;
    };
  }, [workspaceId]);

  const fetchIdleNodes = useMemo(
    () => async () => {
      if (!workspaceId) return;
      setIsLoadingNodes(true);
      try {
        const data = await listLoadNodes({
          workspaceId,
          status: "idle",
          limit: 100,
          offset: 0,
          sort: "host",
        });
        setIdleNodes(data.items);
      } catch {
        setIdleNodes([]);
      } finally {
        setIsLoadingNodes(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    if (showDebug) {
      void fetchIdleNodes();
    }
  }, [showDebug, fetchIdleNodes]);

  useEffect(() => {
    if (selectedEnvId) {
      window.localStorage.setItem(envStorageKey, selectedEnvId);
    } else {
      window.localStorage.removeItem(envStorageKey);
    }
  }, [envStorageKey, selectedEnvId]);

  useEffect(() => {
    if (!dirty) return undefined;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const workspaceSwitchGuard = useMemo(
    () => ({
      dirty,
      safePath: "/scenarios",
      onAbandon: () => {
        window.localStorage.removeItem(envStorageKey);
        setSelectedEnvId("");
        setShowDebug(false);
        setActionError(null);
        setDirty(false);
      },
    }),
    [dirty, envStorageKey],
  );
  useWorkspaceSwitchGuard(workspaceSwitchGuard);

  const selectedStep = useMemo(
    () =>
      draft?.steps.find((step) => step.id === selectedStepId) ??
      draft?.steps[0],
    [draft, selectedStepId],
  );
  const enabledStepCount =
    draft?.steps.filter((step) => step.enabled !== false).length ?? 0;
  const enabledDataSourceCount =
    draft?.dataSources.filter((item) => item.enabled !== false).length ?? 0;
  const selectedEnvName =
    envGroups.find((env) => env.id === selectedEnvId)?.name ??
    scenarioCopy.noEnvironment;

  function updateDraft(updater: (current: ScenarioDetail) => ScenarioDetail) {
    setDraft((current) => (current ? updater(current) : current));
    setDirty(true);
  }

  function updateStep(stepId: string, fields: Partial<ScenarioStep>) {
    updateDraft((current) => ({
      ...current,
      steps: current.steps.map((step) =>
        step.id === stepId ? { ...step, ...fields } : step,
      ),
    }));
  }

  function updateDataSource(
    dataSourceId: string,
    fields: Partial<ScenarioDataSource>,
  ) {
    updateDraft((current) => ({
      ...current,
      dataSources: current.dataSources.map((dataSource) =>
        dataSource.id === dataSourceId
          ? { ...dataSource, ...fields }
          : dataSource,
      ),
    }));
  }

  function addStep() {
    if (!draft) return;
    const step = newStep();
    setSelectedStepId(step.id);
    updateDraft((current) => ({ ...current, steps: [...current.steps, step] }));
  }

  function moveStep(stepId: string, direction: -1 | 1) {
    updateDraft((current) => {
      const index = current.steps.findIndex((step) => step.id === stepId);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.steps.length) {
        return current;
      }
      const next = [...current.steps];
      const [moved] = next.splice(index, 1);
      next.splice(target, 0, moved);
      return { ...current, steps: next };
    });
  }

  function duplicateSelectedStep() {
    if (!selectedStep) return;
    const copy = cloneStep(selectedStep);
    setSelectedStepId(copy.id);
    updateDraft((current) => ({
      ...current,
      steps: [...current.steps, copy],
    }));
  }

  function removeSelectedStep() {
    if (!selectedStep) return;
    updateDraft((current) => {
      const remaining = current.steps.filter(
        (step) => step.id !== selectedStep.id,
      );
      if (remaining[0]) {
        setSelectedStepId(remaining[0].id);
      } else {
        setSelectedStepId(null);
      }
      return { ...current, steps: remaining };
    });
  }

  function stepTabCount(tab: StepTabKey) {
    if (!selectedStep) return 0;
    if (tab === "params") return selectedStep.queryParams?.length ?? 0;
    if (tab === "headers") return selectedStep.headers?.length ?? 0;
    if (tab === "files") return selectedStep.uploadFiles?.length ?? 0;
    if (tab === "extractors") return selectedStep.extractors?.length ?? 0;
    if (tab === "assertions") return selectedStep.assertions?.length ?? 0;
    if (tab === "scripts") return selectedStep.scripts?.length ?? 0;
    return 0;
  }

  async function handleSave(): Promise<ScenarioDetail | null> {
    if (!draft) return null;
    setIsSaving(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      const updated = await patchScenario(
        draft.id,
        toPatchPayload(draft, draft.revision),
        workspaceId,
        token,
      );
      setDraft(updated);
      setTagText(updated.tags.join(", "));
      setDirty(false);
      setRenamingName(false);
      return updated;
    } catch (error) {
      setActionError(errorMessage(error, "save"));
      if (isRevisionConflict(error)) {
        setNeedsReload(true);
      }
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  async function handleStartDebug() {
    if (!draft || !selectedNodeId) return;
    setIsStartingDebug(true);
    setActionError(null);
    setNeedsReload(false);
    try {
      const saved = dirty ? await handleSave() : draft;
      if (!saved) return;
      const token = await getWriteToken();
      const run = await createRun(
        {
          runType: "debug",
          sourceType: "debug_scenario",
          sourceId: saved.id,
          expectedSourceRevision: saved.revision,
          envGroupId: selectedEnvId || null,
          selectedNodeId,
        },
        workspaceId,
        token,
      );
      setDirty(false);
      navigateTo(`/runs/${run.id}`);
    } catch (error) {
      setActionError(errorMessage(error, "debug"));
      if (
        (error as ApiError | undefined)?.body?.code === "LOAD_NODE_BUSY"
      ) {
        void fetchIdleNodes();
      }
      if (isRevisionConflict(error)) {
        setNeedsReload(true);
      }
    } finally {
      setIsStartingDebug(false);
    }
  }

  async function handleReload() {
    setIsReloading(true);
    setActionError(null);
    setNeedsReload(false);
    try {
      await fetchScenario();
    } finally {
      setIsReloading(false);
    }
  }

  async function handleClone() {
    if (!draft) return;
    setIsCloning(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      const cloned = await cloneScenario(draft.id, {}, workspaceId, token);
      setDirty(false);
      navigateTo(`/scenarios/${cloned.id}`);
    } catch (error) {
      setActionError(lifecycleErrorMessage(error));
    } finally {
      setIsCloning(false);
    }
  }

  async function handleArchive() {
    if (!draft) return;
    setIsArchiving(true);
    setActionError(null);
    try {
      const token = await getWriteToken();
      await deleteScenario(draft.id, workspaceId, token);
      setDirty(false);
      setArchiveOpen(false);
      navigateTo("/scenarios");
    } catch (error) {
      setActionError(lifecycleErrorMessage(error));
    } finally {
      setIsArchiving(false);
    }
  }

  function openGlobalConfiguration() {
    configBackupRef.current = {
      draft: draft ? (JSON.parse(JSON.stringify(draft)) as ScenarioDetail) : null,
      dirty,
    };
    setActiveConfigTab("settings");
    setShowConfig(true);
  }

  function cancelGlobalConfiguration() {
    const backup = configBackupRef.current;
    if (backup) {
      if (backup.draft) {
        setDraft(backup.draft);
        setTagText(backup.draft.tags.join(", "));
        setSelectedStepId(backup.draft.steps[0]?.id ?? null);
      }
      setDirty(backup.dirty);
    }
    configBackupRef.current = null;
    setShowConfig(false);
  }

  function doneGlobalConfiguration() {
    configBackupRef.current = null;
    setShowConfig(false);
  }

  function openDebug() {
    setActionError(null);
    setNeedsReload(false);
    setSelectedNodeId("");
    setShowDebug(true);
  }

  if (session === null) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-container-max p-8 text-sm text-text-muted">
        Loading Scenario...
      </div>
    );
  }

  if (loadError || draft === null) {
    return (
      <div className="mx-auto max-w-container-max rounded-xl border border-error/30 bg-error-container p-6">
        <p className="text-sm text-on-error-container">
          {loadError ?? "The Scenario could not be loaded."}
        </p>
        <div className="mt-4 flex gap-3">
          <a
            className="inline-flex items-center rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
            href="/scenarios"
          >
            Back to Scenarios
          </a>
          <button
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isReloading}
            onClick={() => void handleReload()}
            type="button"
          >
            {isReloading ? "Reloading..." : "Reload"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-container-max flex-col gap-5">
      <section className="surgepilot-glass rounded-2xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              {renamingName ? (
                <input
                  aria-label={scenarioCopy.renameInputLabel}
                  autoFocus
                  className="min-w-0 max-w-lg rounded-lg border border-primary/40 bg-surface-container px-3 py-1 font-display text-[26px] font-semibold leading-9 text-white outline-none focus:border-primary/50"
                  onChange={(event) =>
                    updateDraft((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.currentTarget.blur();
                    }
                  }}
                  onBlur={() => setRenamingName(false)}
                  value={draft.name}
                />
              ) : (
                <>
                  <h1 className="font-display text-[26px] font-semibold leading-9 text-white">
                    {draft.name}
                  </h1>
                  <button
                    aria-label={scenarioCopy.rename}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white"
                    onClick={() => setRenamingName(true)}
                    title={scenarioCopy.rename}
                    type="button"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                </>
              )}
              <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 font-mono text-[11px] text-secondary">
                Revision {draft.revision}
              </span>
              <span
                className={cn(
                  "rounded-full border px-3 py-1 font-mono text-[11px]",
                  dirty
                    ? "border-warning/30 bg-warning/10 text-warning"
                    : "border-success/30 bg-success/10 text-success",
                )}
              >
                {dirty ? "Unsaved changes" : "Saved"}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-text-muted">
              <span>
                Updated {formatDate(draft.updatedAt)}
              </span>
              {draft.description ? (
                <span className="max-w-2xl truncate normal-case">
                  {draft.description}
                </span>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="grid gap-1 text-sm text-text-muted">
              <span className="sr-only">Environment</span>
              <select
                aria-label="Environment"
                className="h-10 rounded-lg border border-white/10 bg-surface-container-low px-3 text-sm text-text-main outline-none"
                onChange={(event) => setSelectedEnvId(event.target.value)}
                value={selectedEnvId}
              >
                <option value="">{scenarioCopy.noEnvironment}</option>
                {envGroups.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name}
                  </option>
                ))}
              </select>
            </label>
            {selectedEnvId ? (
              <button
                className="rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:bg-white/5 hover:text-white"
                onClick={() => setSelectedEnvId("")}
                type="button"
              >
                Clear
              </button>
            ) : null}
            <button
              className="rounded-lg border border-primary/30 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/20"
              onClick={openGlobalConfiguration}
              type="button"
            >
              Global Config
            </button>
            <button
              className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!dirty || isSaving}
              onClick={() => void handleSave()}
              type="button"
            >
              {isSaving ? "Saving..." : "Save"}
            </button>
            <button
              aria-label={`${scenarioCopy.clone} ${draft.name}`}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
              disabled={isCloning}
              onClick={() => void handleClone()}
              title={scenarioCopy.clone}
              type="button"
            >
              <Copy className="h-4 w-4" />
            </button>
            <button
              aria-label={`${scenarioCopy.archive} ${draft.name}`}
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-error/30 hover:bg-white/5 hover:text-error"
              onClick={() => setArchiveOpen(true)}
              title={scenarioCopy.archive}
              type="button"
            >
              <Archive className="h-4 w-4" />
            </button>
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={enabledStepCount < 1}
              onClick={openDebug}
              title={
                dirty
                  ? "Unsaved changes will be saved before the debug run."
                  : undefined
              }
              type="button"
            >
              Debug
            </button>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 px-4 py-3">
          <div className="text-sm text-text-muted">
            Base URL:{" "}
            <code className="font-mono text-primary">
              {draft.baseUrlExpression}
            </code>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-secondary">
            <span>
              {enabledDataSourceCount} data sources
            </span>
            <span>
              {enabledStepCount} enabled steps
            </span>
            <span>timeout {Math.round(draft.defaultSettings.timeoutMs / 1000)}s</span>
            <span>think-time {draft.defaultSettings.thinkTimeMs}ms</span>
            <span>
              keep-alive {draft.defaultSettings.keepAlive ? "on" : "off"}
            </span>
            <span>
              redirects {draft.defaultSettings.followRedirects ? "on" : "off"}
            </span>
          </div>
        </div>
        {actionError ? (
          <div className="mt-4 flex items-center justify-between gap-4 rounded-xl border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
            <span>{actionError}</span>
            {needsReload ? (
              <button
                className="shrink-0 rounded-lg border border-white/10 px-3 py-1 text-xs text-text-main transition hover:bg-white/5"
                onClick={() => void handleReload()}
                type="button"
              >
                Reload
              </button>
            ) : null}
          </div>
        ) : null}
      </section>

      <div className="grid items-start gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="surgepilot-glass rounded-2xl p-4">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-white">Steps</h2>
            <button
              aria-label="Add Step"
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110"
              onClick={addStep}
              type="button"
            >
              <Plus className="h-4 w-4" />
              Add Step
            </button>
          </div>
          {draft.steps.length === 0 ? (
            <p className="rounded-xl border border-dashed border-white/10 p-4 text-sm text-text-muted">
              Add a Step to define the first request. Debug Runs require at
              least one enabled Step.
            </p>
          ) : null}
          <div className="space-y-2">
            {draft.steps.map((step, index) => (
              <div
                className={cn(
                  "rounded-2xl border p-2",
                  step.id === selectedStep?.id
                    ? "border-primary/50 bg-primary/10"
                    : "border-white/10 bg-black/10",
                )}
                key={step.id}
              >
                <button
                  className="w-full px-1 py-1 text-left"
                  onClick={() => setSelectedStepId(step.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        "truncate font-medium text-white",
                        step.enabled === false && "opacity-50 line-through",
                      )}
                    >
                      {index + 1}. {step.name}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-primary">
                      {step.enabled === false ? "off" : step.method}
                    </span>
                  </div>
                  <p className="mt-1 truncate font-mono text-xs text-text-muted">
                    {step.path}
                  </p>
                </button>
                <div className="mt-2 flex items-center gap-2 border-t border-white/10 pt-2">
                  <button
                    aria-label={`Move ${step.name} up`}
                    className="rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={index === 0}
                    onClick={() => moveStep(step.id, -1)}
                    type="button"
                  >
                    ↑
                  </button>
                  <button
                    aria-label={`Move ${step.name} down`}
                    className="rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={index === draft.steps.length - 1}
                    onClick={() => moveStep(step.id, 1)}
                    type="button"
                  >
                    ↓
                  </button>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-secondary">
                    Reorder
                  </span>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <main className="surgepilot-glass rounded-2xl p-5">
          {selectedStep ? (
            <div className="space-y-5">
              <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
                <div className="grid gap-3 lg:grid-cols-[150px_minmax(0,1fr)_auto] lg:items-end">
                  <Field label="Method">
                    <select
                      aria-label="Method"
                      className={cn(inputClass(false), "text-text-main")}
                      onChange={(event) =>
                        updateStep(selectedStep.id, {
                          method: event.target.value as ScenarioStep["method"],
                        })
                      }
                      value={selectedStep.method}
                    >
                      {HTTP_METHODS.map((method) => (
                        <option key={method} value={method}>
                          {method}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Path">
                    <input
                      aria-label="Path"
                      className={cn(inputClass(false), "font-mono text-text-main")}
                      onChange={(event) =>
                        updateStep(selectedStep.id, {
                          path: event.target.value,
                        })
                      }
                      placeholder="/health"
                      value={selectedStep.path}
                    />
                  </Field>
                  <div className="flex flex-wrap gap-2 pb-0.5">
                    <button
                      className="rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main transition hover:bg-white/5"
                      onClick={() =>
                        updateStep(selectedStep.id, {
                          enabled: !selectedStep.enabled,
                        })
                      }
                      type="button"
                    >
                      {selectedStep.enabled ? "Disable" : "Enable"}
                    </button>
                    <button
                      className="rounded-lg border border-white/10 px-3 py-2 text-sm text-text-main transition hover:bg-white/5"
                      onClick={duplicateSelectedStep}
                      type="button"
                    >
                      Duplicate
                    </button>
                    <button
                      className="rounded-lg border border-error/30 px-3 py-2 text-sm text-error transition hover:bg-error/10"
                      onClick={removeSelectedStep}
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="mt-3 rounded-xl border border-white/10 bg-black/30 p-3">
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
                    URL Preview
                  </p>
                  <p className="mt-2 break-all font-mono text-sm text-primary">
                    {urlPreview(draft, selectedStep)}
                  </p>
                </div>
              </div>

              <div
                aria-label="Step configuration tabs"
                className="flex flex-wrap gap-2 border-b border-white/10"
                role="tablist"
              >
                {stepTabs.map((tab) => {
                  const count = stepTabCount(tab.key);
                  const isActive = activeStepTab === tab.key;
                  return (
                    <button
                      aria-selected={isActive}
                      className={cn(
                        "-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition",
                        isActive
                          ? "border-primary text-white"
                          : "border-transparent text-text-muted hover:text-white",
                      )}
                      key={tab.key}
                      onClick={() => setActiveStepTab(tab.key)}
                      role="tab"
                      type="button"
                    >
                      {tab.label}
                      {count > 0 ? (
                        <span className="rounded-full border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-secondary">
                          {count}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>

              {activeStepTab === "params" ? (
                <FieldSection
                  title="Query Params"
                  description="Add URL parameters for this request."
                  action={
                    <MiniButton
                      onClick={() =>
                        updateStep(selectedStep.id, {
                          queryParams: [
                            ...(selectedStep.queryParams ?? []),
                            newNamedValue(),
                          ],
                        })
                      }
                      tone="primary"
                    >
                      Add query param
                    </MiniButton>
                  }
                >
                  <NamedValueRows
                    items={selectedStep.queryParams}
                    label="Query param"
                    onChange={(id, fields) =>
                      updateStep(selectedStep.id, {
                        queryParams: (selectedStep.queryParams ?? []).map(
                          (item) =>
                            item.id === id ? { ...item, ...fields } : item,
                        ),
                      })
                    }
                    onRemove={(id) =>
                      updateStep(selectedStep.id, {
                        queryParams: (selectedStep.queryParams ?? []).filter(
                          (item) => item.id !== id,
                        ),
                      })
                    }
                  />
                </FieldSection>
              ) : null}

              {activeStepTab === "headers" ? (
                <FieldSection
                  title="Headers"
                  description="Add request headers. Duplicate header names must be unique when enabled."
                  action={
                    <MiniButton
                      onClick={() =>
                        updateStep(selectedStep.id, {
                          headers: [
                            ...(selectedStep.headers ?? []),
                            newNamedValue(),
                          ],
                        })
                      }
                      tone="primary"
                    >
                      Add header
                    </MiniButton>
                  }
                >
                  <NamedValueRows
                    items={selectedStep.headers}
                    label="Header"
                    onChange={(id, fields) =>
                      updateStep(selectedStep.id, {
                        headers: (selectedStep.headers ?? []).map((item) =>
                          item.id === id ? { ...item, ...fields } : item,
                        ),
                      })
                    }
                    onRemove={(id) =>
                      updateStep(selectedStep.id, {
                        headers: (selectedStep.headers ?? []).filter(
                          (item) => item.id !== id,
                        ),
                      })
                    }
                  />
                </FieldSection>
              ) : null}

              {activeStepTab === "body" ? (
                <BodyEditor
                  step={selectedStep}
                  onChange={(fields) =>
                    updateStep(selectedStep.id, { body: fields })
                  }
                />
              ) : null}

              {activeStepTab === "files" ? (
                <FieldSection
                  title="Upload Files"
                  description="Attach Dependency Files already uploaded in this Workspace."
                  action={
                    <MiniButton
                      onClick={() =>
                        updateStep(selectedStep.id, {
                          uploadFiles: [
                            ...(selectedStep.uploadFiles ?? []),
                            newUploadFile(),
                          ],
                        })
                      }
                      tone="primary"
                    >
                      Add file
                    </MiniButton>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.uploadFiles ?? []).map((file, index) => (
                      <UploadFileRow
                        dependencyFiles={dependencyFiles}
                        file={file}
                        index={index}
                        key={file.id}
                        onChange={(fields) =>
                          updateStep(selectedStep.id, {
                            uploadFiles: (selectedStep.uploadFiles ?? []).map(
                              (item) =>
                                item.id === file.id
                                  ? { ...item, ...fields }
                                  : item,
                            ),
                          })
                        }
                        onRemove={() =>
                          updateStep(selectedStep.id, {
                            uploadFiles: (selectedStep.uploadFiles ?? []).filter(
                              (item) => item.id !== file.id,
                            ),
                          })
                        }
                      />
                    ))}
                    {(selectedStep.uploadFiles ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No upload files yet.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}

              {activeStepTab === "extractors" ? (
                <FieldSection
                  title="Extractors"
                  description="Capture response values into variables used by later enabled Steps."
                  action={
                    <MiniButton
                      onClick={() =>
                        updateStep(selectedStep.id, {
                          extractors: [
                            ...(selectedStep.extractors ?? []),
                            newExtractor("jsonpath"),
                          ],
                        })
                      }
                      tone="primary"
                    >
                      Add extractor
                    </MiniButton>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.extractors ?? []).map((extractor, index) => (
                      <ExtractorRow
                        extractor={extractor}
                        index={index}
                        key={extractor.id}
                        onChange={(fields) =>
                          updateStep(selectedStep.id, {
                            extractors: (selectedStep.extractors ?? []).map(
                              (item) =>
                                item.id === extractor.id
                                  ? { ...item, ...fields }
                                  : item,
                            ),
                          })
                        }
                        onRemove={() =>
                          updateStep(selectedStep.id, {
                            extractors: (selectedStep.extractors ?? []).filter(
                              (item) => item.id !== extractor.id,
                            ),
                          })
                        }
                      />
                    ))}
                    {(selectedStep.extractors ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No extractors yet.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}

              {activeStepTab === "assertions" ? (
                <FieldSection
                  title="Assertions"
                  description="Assert the response status, body text, or JSONPath value."
                  action={
                    <div className="flex flex-wrap gap-2">
                      {(
                        [
                          ["status_code", "Status Code"],
                          ["body_contains", "Body Contains"],
                          ["jsonpath_exists", "JSONPath Exists"],
                          ["jsonpath_equals", "JSONPath Equals"],
                        ] as Array<
                          [ScenarioAssertion["type"], string]
                        >
                      ).map(([type, label]) => (
                        <MiniButton
                          key={type}
                          onClick={() =>
                            updateStep(selectedStep.id, {
                              assertions: [
                                ...(selectedStep.assertions ?? []),
                                newAssertion(type),
                              ],
                            })
                          }
                          tone="neutral"
                        >
                          + {label}
                        </MiniButton>
                      ))}
                    </div>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.assertions ?? []).map((assertion, index) => (
                      <AssertionRow
                        assertion={assertion}
                        index={index}
                        key={assertion.id}
                        onChange={(fields) =>
                          updateStep(selectedStep.id, {
                            assertions: (selectedStep.assertions ?? []).map(
                              (item) =>
                                item.id === assertion.id
                                  ? { ...item, ...fields }
                                  : item,
                            ),
                          })
                        }
                        onRemove={() =>
                          updateStep(selectedStep.id, {
                            assertions: (selectedStep.assertions ?? []).filter(
                              (item) => item.id !== assertion.id,
                            ),
                          })
                        }
                      />
                    ))}
                    {(selectedStep.assertions ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No assertions yet.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}

              {activeStepTab === "scripts" ? (
                <FieldSection
                  title="Scripts"
                  description="Request-level Groovy JSR223 scripts execute on the selected Load Node as part of JMeter. Keep script text bounded and use only variables this Step can see."
                  action={
                    <div className="flex flex-wrap gap-2">
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            scripts: [
                              ...(selectedStep.scripts ?? []),
                              newScript("before"),
                            ],
                          })
                        }
                        tone="primary"
                      >
                        Add Groovy before script
                      </MiniButton>
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            scripts: [
                              ...(selectedStep.scripts ?? []),
                              newScript("after"),
                            ],
                          })
                        }
                        tone="neutral"
                      >
                        Add Groovy after script
                      </MiniButton>
                    </div>
                  }
                >
                  <div className="space-y-3">
                    {(selectedStep.scripts ?? []).map((script, index) => (
                      <ScriptRow
                        index={index}
                        key={script.id}
                        onChange={(fields) =>
                          updateStep(selectedStep.id, {
                            scripts: (selectedStep.scripts ?? []).map((item) =>
                              item.id === script.id
                                ? { ...item, ...fields }
                                : item,
                            ),
                          })
                        }
                        onRemove={() =>
                          updateStep(selectedStep.id, {
                            scripts: (selectedStep.scripts ?? []).filter(
                              (item) => item.id !== script.id,
                            ),
                          })
                        }
                        script={script}
                      />
                    ))}
                    {(selectedStep.scripts ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No scripts. Most requests do not need one.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}

              {activeStepTab === "settings" ? (
                <FieldSection
                  title="Step Settings"
                  description="Optional request-level overrides. Blank values inherit Scenario defaults."
                >
                  <div className="grid gap-3">
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step think time override (ms)
                      <input
                        aria-label="Step think time override (ms)"
                        className={textInputClass("font-mono")}
                        onChange={(event) =>
                          updateStep(selectedStep.id, {
                            settings: {
                              thinkTimeMs:
                                event.target.value === ""
                                  ? null
                                  : Number(event.target.value),
                              timeoutMs:
                                selectedStep.settings?.timeoutMs ?? null,
                              followRedirects:
                                selectedStep.settings?.followRedirects ?? null,
                              keepAlive:
                                selectedStep.settings?.keepAlive ?? null,
                            },
                          })
                        }
                        type="number"
                        value={selectedStep.settings?.thinkTimeMs ?? ""}
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step timeout override (ms)
                      <input
                        aria-label="Step timeout override (ms)"
                        className={textInputClass("font-mono")}
                        onChange={(event) =>
                          updateStep(selectedStep.id, {
                            settings: {
                              thinkTimeMs:
                                selectedStep.settings?.thinkTimeMs ?? null,
                              timeoutMs:
                                event.target.value === ""
                                  ? null
                                  : Number(event.target.value),
                              followRedirects:
                                selectedStep.settings?.followRedirects ?? null,
                              keepAlive:
                                selectedStep.settings?.keepAlive ?? null,
                            },
                          })
                        }
                        type="number"
                        value={selectedStep.settings?.timeoutMs ?? ""}
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step follow redirects override
                      <select
                        aria-label="Step follow redirects override"
                        className={textInputClass()}
                        onChange={(event) =>
                          updateStep(selectedStep.id, {
                            settings: {
                              thinkTimeMs:
                                selectedStep.settings?.thinkTimeMs ?? null,
                              timeoutMs:
                                selectedStep.settings?.timeoutMs ?? null,
                              followRedirects: parseBooleanOverride(
                                event.target.value,
                              ),
                              keepAlive:
                                selectedStep.settings?.keepAlive ?? null,
                            },
                          })
                        }
                        value={booleanOverrideValue(
                          selectedStep.settings?.followRedirects,
                        )}
                      >
                        <option value="">Inherit</option>
                        <option value="true">On</option>
                        <option value="false">Off</option>
                      </select>
                    </label>
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step keep alive override
                      <select
                        aria-label="Step keep alive override"
                        className={textInputClass()}
                        onChange={(event) =>
                          updateStep(selectedStep.id, {
                            settings: {
                              thinkTimeMs:
                                selectedStep.settings?.thinkTimeMs ?? null,
                              timeoutMs:
                                selectedStep.settings?.timeoutMs ?? null,
                              followRedirects:
                                selectedStep.settings?.followRedirects ?? null,
                              keepAlive: parseBooleanOverride(
                                event.target.value,
                              ),
                            },
                          })
                        }
                        value={booleanOverrideValue(
                          selectedStep.settings?.keepAlive,
                        )}
                      >
                        <option value="">Inherit</option>
                        <option value="true">On</option>
                        <option value="false">Off</option>
                      </select>
                    </label>
                  </div>
                </FieldSection>
              ) : null}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-white/15 p-10 text-center">
              <h2 className="text-lg font-semibold text-white">
                No Step selected
              </h2>
              <p className="mt-2 text-sm text-text-muted">
                Add a Step to start editing this Scenario.
              </p>
              <button
                className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110"
                onClick={addStep}
                type="button"
              >
                <Plus className="h-4 w-4" />
                Add Step
              </button>
            </div>
          )}
        </main>
      </div>

      {showConfig && draft ? (
        <div
          aria-label="Global configuration"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-start justify-end bg-black/50 p-0"
          role="dialog"
        >
          <div className="flex h-dvh w-full max-w-3xl flex-col overflow-hidden border-l border-white/10 bg-surface-container-low shadow-2xl">
            <div className="flex items-start justify-between border-b border-white/10 p-6">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Global Config
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  Scenario settings, defaults and CSV data sources.
                </p>
              </div>
              <button
                aria-label="Close global configuration"
                className="rounded-lg p-2 text-text-muted transition hover:bg-white/5 hover:text-white"
                onClick={doneGlobalConfiguration}
                type="button"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div
              aria-label="Global Configuration tabs"
              className="flex flex-wrap gap-2 border-b border-white/10 px-6"
              role="tablist"
            >
              {configTabs.map((tab) => {
                const isActive = activeConfigTab === tab.key;
                return (
                  <button
                    aria-selected={isActive}
                    className={cn(
                      "-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition",
                      isActive
                        ? "border-primary text-white"
                        : "border-transparent text-text-muted hover:text-white",
                    )}
                    key={tab.key}
                    onClick={() => setActiveConfigTab(tab.key)}
                    role="tab"
                    type="button"
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-6">
              {activeConfigTab === "settings" ? (
                <div className="space-y-4">
                  <Field label="Scenario name">
                    <input
                      className={inputClass(false)}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                      value={draft.name}
                    />
                  </Field>
                  <Field label="Base URL expression">
                    <input
                      aria-label="Base URL expression"
                      className={cn(inputClass(false), "font-mono text-text-main")}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          baseUrlExpression: event.target.value,
                        }))
                      }
                      placeholder="${base_url}"
                      value={draft.baseUrlExpression}
                    />
                  </Field>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Scenario description">
                      <textarea
                        aria-label="Scenario description"
                        className={cn(
                          inputClass(false),
                          "min-h-24 resize-y py-3 text-text-main",
                        )}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            description: event.target.value || null,
                          }))
                        }
                        value={draft.description ?? ""}
                      />
                    </Field>
                    <Field label="Tags">
                      <input
                        aria-label="Tags"
                        className={cn(inputClass(false), "font-mono text-text-main")}
                        onChange={(event) => {
                          setTagText(event.target.value);
                          updateDraft((current) => ({
                            ...current,
                            tags: parseCsvNames(event.target.value),
                          }));
                        }}
                        placeholder="checkout, smoke"
                        value={tagText}
                      />
                    </Field>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Think time (ms)">
                      <input
                        className={cn(inputClass(false), "font-mono text-text-main")}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            defaultSettings: {
                              ...current.defaultSettings,
                              thinkTimeMs: Number(event.target.value),
                            },
                          }))
                        }
                        type="number"
                        value={draft.defaultSettings.thinkTimeMs}
                      />
                    </Field>
                    <Field label="Timeout (ms)">
                      <input
                        className={cn(inputClass(false), "font-mono text-text-main")}
                        onChange={(event) =>
                          updateDraft((current) => ({
                            ...current,
                            defaultSettings: {
                              ...current.defaultSettings,
                              timeoutMs: Number(event.target.value),
                            },
                          }))
                        }
                        type="number"
                        value={draft.defaultSettings.timeoutMs}
                      />
                    </Field>
                  </div>
                  <div className="flex flex-wrap gap-4 text-sm text-text-muted">
                    {[
                      ["followRedirects", "Follow redirects"],
                      ["keepAlive", "Keep alive"],
                      ["storeCache", "Store cache"],
                      ["storeCookie", "Store cookies"],
                      ["retrieveResources", "Retrieve resources"],
                    ].map(([key, label]) => (
                      <label className="flex items-center gap-2" key={key}>
                        <input
                          checked={Boolean(
                            draft.defaultSettings[
                              key as keyof ScenarioDetail["defaultSettings"]
                            ],
                          )}
                          onChange={(event) =>
                            updateDraft((current) => ({
                              ...current,
                              defaultSettings: {
                                ...current.defaultSettings,
                                [key]: event.target.checked,
                              },
                            }))
                          }
                          type="checkbox"
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </div>
              ) : null}
              {activeConfigTab === "dataSources" ? (
                <FieldSection
                  title="CSV Data Sources"
                  description="Reference CSV Dependency Files to loop variables across Steps."
                  action={
                    <MiniButton
                      onClick={() =>
                        updateDraft((current) => ({
                          ...current,
                          dataSources: [
                            newDataSource(),
                            ...current.dataSources,
                          ],
                        }))
                      }
                      tone="primary"
                    >
                      Add data source
                    </MiniButton>
                  }
                >
                  <div className="space-y-3">
                    {draft.dataSources.map((dataSource, index) => (
                      <DataSourceRow
                        dataSource={dataSource}
                        dependencyFiles={dependencyFiles}
                        index={index}
                        key={dataSource.id}
                        onChange={(fields) =>
                          updateDataSource(dataSource.id, fields)
                        }
                        onRemove={() =>
                          updateDraft((current) => ({
                            ...current,
                            dataSources: current.dataSources.filter(
                              (item) => item.id !== dataSource.id,
                            ),
                          }))
                        }
                      />
                    ))}
                    {draft.dataSources.length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No CSV data sources.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
            </div>
            <div className="flex justify-end gap-3 border-t border-white/10 p-6">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
                onClick={cancelGlobalConfiguration}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSaving}
                onClick={() => void handleSave()}
                type="button"
              >
                {isSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showDebug ? (
        <div
          aria-label={scenarioCopy.debugRun}
          aria-modal="true"
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col overflow-y-auto border-l border-white/10 bg-surface-container-low p-6 shadow-2xl"
          role="dialog"
        >
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">
                {scenarioCopy.debugRun}
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                1 virtual user · 1 iteration
              </p>
            </div>
            <button
              className="rounded-lg p-2 text-text-muted transition hover:bg-white/5 hover:text-white"
              onClick={() => setShowDebug(false)}
              type="button"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="mt-6 space-y-4">
            <div className="rounded-2xl border border-white/10 p-4">
              <p className="text-sm text-text-muted">Environment</p>
              <p className="mt-1 text-text-main">{selectedEnvName}</p>
              <select
                aria-label="Debug Environment"
                className="mt-3 w-full rounded-lg border border-white/10 bg-surface-container px-3 py-2 text-sm text-text-main outline-none"
                onChange={(event) => setSelectedEnvId(event.target.value)}
                value={selectedEnvId}
              >
                <option value="">{scenarioCopy.noEnvironment}</option>
                {envGroups.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name}
                  </option>
                ))}
              </select>
            </div>
            <Field label="Load Node">
              <select
                aria-label="Load Node"
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) => setSelectedNodeId(event.target.value)}
                value={selectedNodeId}
              >
                <option value="">Select an idle node</option>
                {idleNodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.host}
                  </option>
                ))}
              </select>
            </Field>
            {isLoadingNodes ? (
              <p className="text-sm text-text-muted">
                Loading idle Load Nodes...
              </p>
            ) : null}
            {!isLoadingNodes && idleNodes.length === 0 ? (
              <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
                {scenarioCopy.noNodes}{" "}
                <button
                  className="font-semibold text-primary underline"
                  onClick={navigateToLoadNodes}
                  type="button"
                >
                  Open Load Nodes
                </button>
              </p>
            ) : null}
            {scriptsEnabled(draft) ? (
              <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
                This Scenario contains custom JSR223 scripts.
              </p>
            ) : null}
            {actionError ? (
              <div className="rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
                {actionError}
              </div>
            ) : null}
            <button
              className="inline-flex w-full items-center justify-center rounded-xl bg-primary px-4 py-3 font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!selectedNodeId || isStartingDebug}
              onClick={() => void handleStartDebug()}
              type="button"
            >
              {isStartingDebug ? "Starting Debug Run..." : "Start Debug Run"}
            </button>
          </div>
        </div>
      ) : null}

      {archiveOpen ? (
        <div
          aria-label={scenarioCopy.archiveTitle}
          aria-modal="true"
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4"
          role="dialog"
        >
          <div className="w-[min(440px,calc(100vw-32px))] rounded-2xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <h2 className="text-lg font-semibold text-white">
              {scenarioCopy.archiveTitle}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              Archive {draft.name}? {scenarioCopy.archiveBody}
            </p>
            {actionError ? (
              <p className="mt-4 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
                {actionError}
              </p>
            ) : null}
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
                onClick={() => {
                  setArchiveOpen(false);
                  setActionError(null);
                }}
                type="button"
              >
                Cancel
              </button>
              <button
                className="rounded-lg bg-error-container px-4 py-2 text-sm font-semibold text-on-error-container transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isArchiving}
                onClick={() => void handleArchive()}
                type="button"
              >
                {isArchiving ? "Archiving..." : scenarioCopy.archive}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function BodyEditor({
  step,
  onChange,
}: {
  step: ScenarioStep;
  onChange: (body: ScenarioStep["body"]) => void;
}) {
  const body = stepBody(step);
  return (
    <FieldSection
      title="Body"
      description="Define a request body when the method allows one."
    >
      <div className="grid gap-4">
        <Field label="Body type">
          <select
            aria-label="Body type"
            className={cn(inputClass(false), "text-text-main")}
            onChange={(event) => {
              const type = event.target.value as
                | "none"
                | "raw"
                | "form";
              if (type === "none") {
                onChange({
                  type,
                  contentType: null,
                  rawText: null,
                  formFields: [],
                });
              } else if (type === "raw") {
                onChange({
                  type,
                  contentType: body.contentType ?? "application/json",
                  rawText: body.rawText ?? "",
                  formFields: [],
                });
              } else {
                onChange({
                  type,
                  contentType: null,
                  rawText: null,
                  formFields: body.formFields ?? [],
                });
              }
            }}
            value={body.type}
          >
            <option value="none">None</option>
            <option value="raw">Raw</option>
            <option value="form">Form fields</option>
          </select>
        </Field>
        {body.type === "raw" ? (
          <>
            <Field label="Content type">
              <input
                aria-label="Content type"
                className={cn(inputClass(false), "font-mono text-text-main")}
                list="scenario-content-types"
                onChange={(event) =>
                  onChange({ ...body, contentType: event.target.value || null })
                }
                value={body.contentType ?? ""}
              />
              <datalist id="scenario-content-types">
                {RAW_CONTENT_TYPES.map((contentType) => (
                  <option key={contentType} value={contentType} />
                ))}
              </datalist>
            </Field>
            <Field label="Body text">
              <textarea
                aria-label="Body text"
                className={cn(
                  inputClass(false),
                  "min-h-40 resize-y py-3 font-mono text-xs text-text-main",
                )}
                onChange={(event) =>
                  onChange({ ...body, rawText: event.target.value })
                }
                placeholder='{"key": "value"}'
                value={body.rawText ?? ""}
              />
            </Field>
          </>
        ) : null}
        {body.type === "form" ? (
          <FieldSection
            title="Form Fields"
            description="Form fields are sent as application/x-www-form-urlencoded."
            action={
              <MiniButton
                onClick={() =>
                  onChange({ ...body, formFields: [...(body.formFields ?? []), newFormField()] })
                }
                tone="primary"
              >
                Add form field
              </MiniButton>
            }
          >
            <NamedValueRows
              items={body.formFields as ScenarioNamedValue[] | undefined}
              label="Form field"
              onChange={(id, fields) =>
                onChange({
                  ...body,
                  formFields: (body.formFields ?? []).map((item) =>
                    item.id === id
                      ? ({ ...item, ...fields } as ScenarioFormField)
                      : item,
                  ),
                })
              }
              onRemove={(id) =>
                onChange({
                  ...body,
                  formFields: (body.formFields ?? []).filter(
                    (item) => item.id !== id,
                  ),
                })
              }
            />
          </FieldSection>
        ) : null}
        {body.type === "none" ? (
          <p className="text-sm text-text-muted">
            This request is sent without a body.
          </p>
        ) : null}
      </div>
    </FieldSection>
  );
}

function UploadFileRow({
  dependencyFiles,
  file,
  index,
  onChange,
  onRemove,
}: {
  dependencyFiles: DependencyFileSummary[];
  file: ScenarioUploadFile;
  index: number;
  onChange: (fields: Partial<ScenarioUploadFile>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="grid gap-2 rounded-xl border border-white/10 bg-black/10 p-3 md:grid-cols-[1fr_1.2fr_1fr_auto_auto] md:items-end">
      <Field label={`Upload file ${index + 1} field name`}>
        <input
          aria-label={`Upload file ${index + 1} field name`}
          className={cn(textInputClass(), "font-mono")}
          onChange={(event) => onChange({ fieldName: event.target.value })}
          placeholder="file"
          value={file.fieldName}
        />
      </Field>
      <Field label="Dependency File">
        <select
          aria-label={`Upload file ${index + 1} Dependency File`}
          className={cn(textInputClass(), "text-text-main")}
          onChange={(event) => {
            const selected = dependencyFiles.find(
              (item) => item.id === event.target.value,
            );
            onChange({
              dependencyFileId: event.target.value,
              mimeType: selected?.contentType ?? null,
            });
          }}
          value={file.dependencyFileId}
        >
          <option value="">Select a Dependency File</option>
          {dependencyFiles.map((item) => (
            <option key={item.id} value={item.id}>
              {item.filename}
            </option>
          ))}
        </select>
      </Field>
      <Field label="MIME type">
        <input
          aria-label={`Upload file ${index + 1} MIME type`}
          className={cn(textInputClass(), "font-mono")}
          onChange={(event) =>
            onChange({ mimeType: event.target.value || null })
          }
          value={file.mimeType ?? ""}
        />
      </Field>
      <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
        <input
          checked={file.enabled !== false}
          onChange={(event) => onChange({ enabled: event.target.checked })}
          type="checkbox"
        />
        Enabled
      </label>
      <div className="flex items-end">
        <MiniButton onClick={onRemove} tone="danger">
          Remove
        </MiniButton>
      </div>
    </div>
  );
}

function ExtractorRow({
  extractor,
  index,
  onChange,
  onRemove,
}: {
  extractor: ScenarioExtractor;
  index: number;
  onChange: (fields: Partial<ScenarioExtractor>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="grid gap-2 md:grid-cols-[160px_1fr_1fr_auto_auto] md:items-end">
        <Field label="Type">
          <select
            aria-label={`Extractor ${index + 1} type`}
            className={cn(textInputClass(), "text-text-main")}
            onChange={(event) => {
              const type = event.target.value as ScenarioExtractor["type"];
              onChange({
                type,
                expression: type === "jsonpath" ? "$." : "",
                template: type === "regexp" ? "1" : null,
              });
            }}
            value={extractor.type}
          >
            <option value="jsonpath">JSONPath</option>
            <option value="regexp">Regexp</option>
          </select>
        </Field>
        <Field label="Variable name">
          <input
            aria-label={`Extractor ${index + 1} variable name`}
            className={cn(textInputClass(), "font-mono")}
            onChange={(event) => onChange({ variableName: event.target.value })}
            placeholder="user_id"
            value={extractor.variableName}
          />
        </Field>
        <Field label={extractor.type === "jsonpath" ? "JSONPath expression" : "Regexp"}>
          <input
            aria-label={`Extractor ${index + 1} expression`}
            className={cn(textInputClass(), "font-mono")}
            onChange={(event) => onChange({ expression: event.target.value })}
            value={extractor.expression}
          />
        </Field>
        <Field label="Subject">
          <select
            aria-label={`Extractor ${index + 1} subject`}
            className={cn(textInputClass(), "text-text-main")}
            onChange={(event) =>
              onChange({ subject: event.target.value || null })
            }
            value={extractor.subject ?? "body"}
          >
            {EXTRACTOR_SUBJECTS.map((subject) => (
              <option key={subject} value={subject}>
                {subject}
              </option>
            ))}
          </select>
        </Field>
        <div className="flex items-end gap-2">
          <label className="flex items-center gap-2 pb-2 text-xs text-text-muted">
            <input
              checked={extractor.enabled !== false}
              onChange={(event) => onChange({ enabled: event.target.checked })}
              type="checkbox"
            />
            Enabled
          </label>
          <MiniButton onClick={onRemove} tone="danger">
            Remove
          </MiniButton>
        </div>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_1fr]">
        <Field label="Match number">
          <input
            aria-label={`Extractor ${index + 1} match number`}
            className={cn(textInputClass(), "font-mono")}
            min={0}
            onChange={(event) =>
              onChange({ matchNo: Number(event.target.value) })
            }
            type="number"
            value={extractor.matchNo}
          />
        </Field>
        {extractor.type === "regexp" ? (
          <Field label="Template group">
            <input
              aria-label={`Extractor ${index + 1} template`}
              className={cn(textInputClass(), "font-mono")}
              onChange={(event) => onChange({ template: event.target.value || null })}
              placeholder="1"
              value={extractor.template ?? ""}
            />
          </Field>
        ) : null}
        <Field label="Default value">
          <input
            aria-label={`Extractor ${index + 1} default value`}
            className={cn(textInputClass(), "font-mono")}
            onChange={(event) => onChange({ defaultValue: event.target.value })}
            value={extractor.defaultValue}
          />
        </Field>
      </div>
    </div>
  );
}

function AssertionRow({
  assertion,
  index,
  onChange,
  onRemove,
}: {
  assertion: ScenarioAssertion;
  index: number;
  onChange: (fields: Partial<ScenarioAssertion>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="grid gap-2 md:grid-cols-[180px_1fr_auto_auto] md:items-end">
        <Field label="Type">
          <select
            aria-label={`Assertion ${index + 1} type`}
            className={cn(textInputClass(), "text-text-main")}
            onChange={(event) => {
              const type = event.target.value as ScenarioAssertion["type"];
              onChange({
                type,
                expectedStatus: type === "status_code" ? 200 : null,
                contains: type === "body_contains" ? "" : null,
                jsonpath:
                  type === "jsonpath_exists" || type === "jsonpath_equals"
                    ? "$."
                    : null,
                expectedValue: type === "jsonpath_equals" ? "" : null,
              });
            }}
            value={assertion.type}
          >
            <option value="status_code">Status Code</option>
            <option value="body_contains">Body Contains</option>
            <option value="jsonpath_exists">JSONPath Exists</option>
            <option value="jsonpath_equals">JSONPath Equals</option>
          </select>
        </Field>
        {assertion.type === "status_code" ? (
          <Field label="Expected status">
            <input
              aria-label={`Assertion ${index + 1} expected status`}
              className={cn(textInputClass(), "font-mono")}
              onChange={(event) =>
                onChange({ expectedStatus: Number(event.target.value) })
              }
              type="number"
              value={assertion.expectedStatus ?? 200}
            />
          </Field>
        ) : null}
        {assertion.type === "body_contains" ? (
          <Field label="Contains text">
            <input
              aria-label={`Assertion ${index + 1} contains`}
              className={cn(textInputClass(), "font-mono")}
              onChange={(event) => onChange({ contains: event.target.value })}
              value={assertion.contains ?? ""}
            />
          </Field>
        ) : null}
        {assertion.type === "jsonpath_exists" ||
        assertion.type === "jsonpath_equals" ? (
          <>
            <Field label="JSONPath">
              <input
                aria-label={`Assertion ${index + 1} jsonpath`}
                className={cn(textInputClass(), "font-mono")}
                onChange={(event) => onChange({ jsonpath: event.target.value })}
                value={assertion.jsonpath ?? ""}
              />
            </Field>
            {assertion.type === "jsonpath_equals" ? (
              <Field label="Expected value">
                <input
                  aria-label={`Assertion ${index + 1} expected value`}
                  className={cn(textInputClass(), "font-mono")}
                  onChange={(event) =>
                    onChange({ expectedValue: event.target.value })
                  }
                  value={assertion.expectedValue ?? ""}
                />
              </Field>
            ) : null}
          </>
        ) : null}
        <div className="flex items-end gap-3 pb-2 text-xs text-text-muted">
          {assertion.type !== "status_code" ? (
            <>
              <label className="flex items-center gap-1">
                <input
                  checked={assertion.not === true}
                  onChange={(event) => onChange({ not: event.target.checked })}
                  type="checkbox"
                />
                Not
              </label>
              <label className="flex items-center gap-1">
                <input
                  checked={assertion.regexp === true}
                  onChange={(event) =>
                    onChange({ regexp: event.target.checked })
                  }
                  type="checkbox"
                />
                Regexp
              </label>
            </>
          ) : null}
          <label className="flex items-center gap-1">
            <input
              checked={assertion.enabled !== false}
              onChange={(event) => onChange({ enabled: event.target.checked })}
              type="checkbox"
            />
            Enabled
          </label>
          <MiniButton onClick={onRemove} tone="danger">
            Remove
          </MiniButton>
        </div>
      </div>
    </div>
  );
}

function ScriptRow({
  script,
  index,
  onChange,
  onRemove,
}: {
  script: ScenarioScript;
  index: number;
  onChange: (fields: Partial<ScenarioScript>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-xs text-secondary">
          Script {index + 1}
        </span>
        <select
          aria-label={`Script ${index + 1} execute`}
          className={cn(textInputClass("w-auto"), "text-text-main")}
          onChange={(event) =>
            onChange({
              execute: event.target.value as ScenarioScript["execute"],
            })
          }
          value={script.execute}
        >
          <option value="before">Before request</option>
          <option value="after">After request</option>
        </select>
        <label className="flex items-center gap-2 text-xs text-text-muted">
          <input
            checked={script.enabled !== false}
            onChange={(event) => onChange({ enabled: event.target.checked })}
            type="checkbox"
          />
          Enabled
        </label>
        <div className="ml-auto">
          <MiniButton onClick={onRemove} tone="danger">
            Remove
          </MiniButton>
        </div>
      </div>
      <div className="mt-2">
        <Field label="Groovy script text">
          <textarea
            aria-label={`Script ${index + 1} text`}
            className={cn(
              textInputClass(),
              "min-h-24 resize-y py-2 font-mono text-xs text-text-main",
            )}
            onChange={(event) => onChange({ scriptText: event.target.value })}
            placeholder="vars.put('token', vars.get('base_token'))"
            spellCheck={false}
            value={script.scriptText ?? ""}
          />
        </Field>
      </div>
    </div>
  );
}

function DataSourceRow({
  dataSource,
  dependencyFiles,
  index,
  onChange,
  onRemove,
}: {
  dataSource: ScenarioDataSource;
  dependencyFiles: DependencyFileSummary[];
  index: number;
  onChange: (fields: Partial<ScenarioDataSource>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/10 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <span className="font-mono text-xs text-secondary">
          Data source {index + 1}
        </span>
        <label className="flex items-center gap-2 text-xs text-text-muted">
          <input
            checked={dataSource.enabled !== false}
            onChange={(event) => onChange({ enabled: event.target.checked })}
            type="checkbox"
          />
          Enabled
        </label>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-[1.2fr_1fr_auto] md:items-end">
        <Field label="CSV Dependency File">
          <select
            aria-label={`Data source ${index + 1} Dependency File`}
            className={cn(textInputClass(), "text-text-main")}
            onChange={(event) => {
              const selected = dependencyFiles.find(
                (item) => item.id === event.target.value,
              );
              onChange({
                dependencyFileId: event.target.value,
                displayName: selected?.filename ?? dataSource.displayName,
              });
            }}
            value={dataSource.dependencyFileId}
          >
            <option value="">Select a CSV file</option>
            {dependencyFiles.map((item) => (
              <option key={item.id} value={item.id}>
                {item.filename}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Display name">
          <input
            aria-label={`Data source ${index + 1} display name`}
            className={cn(textInputClass(), "font-mono")}
            onChange={(event) => onChange({ displayName: event.target.value })}
            value={dataSource.displayName}
          />
        </Field>
        <Field label="Delimiter">
          <select
            aria-label={`Data source ${index + 1} delimiter`}
            className={cn(textInputClass(), "text-text-main")}
            onChange={(event) => onChange({ delimiter: event.target.value })}
            value={dataSource.delimiter ?? ","}
          >
            {DELIMITER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="mt-2 grid gap-2 md:grid-cols-[1fr_1fr_1fr_auto] md:items-end">
        <Field label="Variable names">
          <input
            aria-label={`Data source ${index + 1} variable names`}
            className={cn(textInputClass(), "font-mono")}
            onChange={(event) =>
              onChange({ variableNames: parseCsvNames(event.target.value) })
            }
            placeholder="username, password"
            value={(dataSource.variableNames ?? []).join(", ")}
          />
        </Field>
        <div className="flex flex-wrap gap-4 text-xs text-text-muted">
          <label className="flex items-center gap-2">
            <input
              checked={dataSource.loop !== false}
              onChange={(event) => onChange({ loop: event.target.checked })}
              type="checkbox"
            />
            Loop
          </label>
          <label className="flex items-center gap-2">
            <input
              checked={dataSource.randomOrder === true}
              onChange={(event) =>
                onChange({ randomOrder: event.target.checked })
              }
              type="checkbox"
            />
            Random order
          </label>
        </div>
        <label className="flex items-center gap-2 text-xs text-text-muted">
          Quoted
          <select
            aria-label={`Data source ${index + 1} quoted`}
            className="rounded-lg border border-white/10 bg-black/20 px-2 py-1 text-sm text-text-main"
            onChange={(event) =>
              onChange({ quoted: parseBooleanOverride(event.target.value) })
            }
            value={dataSource.quoted === null ? "" : String(dataSource.quoted)}
          >
            <option value="">Auto</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <MiniButton onClick={onRemove} tone="danger">
          Remove
        </MiniButton>
      </div>
    </div>
  );
}
