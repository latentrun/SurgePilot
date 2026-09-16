import { useMutation, useQuery } from "@tanstack/react-query";
import { FileCode2, Pencil, Plus, Terminal } from "lucide-react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createRun,
  getCsrfToken,
  generateScenarioOpenApiStepDrafts,
  getScenario,
  listDependencyFiles,
  listEnvGroups,
  listLoadNodes,
  listScenarioOpenApiOperations,
  listScenarioOpenApiSpecSources,
  patchScenario,
  parseScenarioCurlImport,
  type ApiError,
  type CurlImportParseResponse,
  type OpenApiOperationRef,
  type OpenApiStepDraftPreviewResponse,
  type ScenarioDetail,
  type ScenarioStep,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { useWorkspaceSwitchGuard } from "../../../app/workspace-switch-guard";
import { IconActionButton } from "../../../components/icon-action";
import { scenarioCopy } from "../copy";
import {
  cloneStep,
  newDataSource,
  newAssertion,
  newExtractor,
  newFormField,
  newNamedValue,
  newScript,
  newStep,
  newUploadFile,
  stepFromCurlImportDraft,
  stepFromOpenApiGeneratedDraft,
  toPatchPayload,
  type ScenarioDataSource,
  type ScenarioAssertion,
  type ScenarioExtractor,
  type ScenarioNamedValue,
  type ScenarioScript,
  type ScenarioVariable,
} from "../model";

function useWriteToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}
function errorMessage(error: unknown, action: "save" | "debug" = "debug") {
  const code = (error as ApiError | undefined)?.body?.code;
  if (code === "SCENARIO_REVISION_CONFLICT")
    return "Scenario changed elsewhere. Reload and try again.";
  if (code === "LOAD_NODE_BUSY")
    return "Selected Load Node is no longer idle. Pick another node.";
  if (code === "VALIDATION_ERROR")
    return action === "save"
      ? "Scenario needs attention before it can be saved."
      : "Scenario needs attention before the Debug Run can start.";
  return "Action failed. Refresh and try again.";
}
function urlPreview(detail: ScenarioDetail, step: ScenarioStep | undefined) {
  if (!step) return detail.baseUrlExpression;
  const query = (step.queryParams ?? [])
    .filter((item) => item.enabled !== false)
    .map((item) => `${item.name}=${item.value}`)
    .join("&");
  return `${detail.baseUrlExpression}${step.path}${query ? `?${query}` : ""}`;
}

function textInputClass(extra = "") {
  return `rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white ${extra}`;
}

function FieldSection({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-black/10 p-4">
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
  children: ReactNode;
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
      className={`rounded-lg border px-3 py-1.5 text-xs disabled:opacity-40 ${toneClass}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
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
function parseCsvNames(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function openApiOperationKey(ref: OpenApiOperationRef) {
  return `${ref.method} ${ref.path} ${ref.operationId ?? ""}`;
}

function openApiRefsEqual(a: OpenApiOperationRef, b: OpenApiOperationRef) {
  return a.method === b.method && a.path === b.path;
}

function hasSensitiveCurlWarning(preview: CurlImportParseResponse | null) {
  return (preview?.warnings ?? []).some((warning) =>
    ["SENSITIVE_HEADER_PRESENT", "SENSITIVE_BODY_FIELD_PRESENT"].includes(
      warning.code,
    ),
  );
}

function dataSourceVariableText(dataSources: ScenarioDetail["dataSources"]) {
  return Object.fromEntries(
    dataSources.map((item) => [item.id, (item.variableNames ?? []).join(", ")]),
  );
}
function scriptsEnabled(detail: ScenarioDetail) {
  return detail.steps.some(
    (step) =>
      step.enabled !== false &&
      (step.scripts ?? []).some((script) => script.enabled !== false),
  );
}

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
const OPENAPI_MAX_OPERATION_SELECTION = 20;
const OPENAPI_QUERY_STALE_TIME_MS = 30_000;
type GlobalConfigTabKey = "settings" | "headers" | "variables" | "dataSources";
const globalConfigTabs: Array<{ key: GlobalConfigTabKey; label: string }> = [
  { key: "settings", label: "Settings" },
  { key: "headers", label: "Headers" },
  { key: "variables", label: "Variables" },
  { key: "dataSources", label: "Data Sources" },
];

export function ScenarioDesignerPage() {
  const { scenarioId = "" } = useParams();
  const navigate = useNavigate();
  const { session } = useAuthSession();
  const getWriteToken = useWriteToken();
  const workspaceId =
    session?.currentWorkspace.id ?? session?.defaultWorkspace.id ?? "";
  const [draft, setDraft] = useState<ScenarioDetail | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [renamingName, setRenamingName] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [activeConfigTab, setActiveConfigTab] =
    useState<GlobalConfigTabKey>("settings");
  const [showCurlImport, setShowCurlImport] = useState(false);
  const [showOpenApiImport, setShowOpenApiImport] = useState(false);
  const [selectedOpenApiSpecId, setSelectedOpenApiSpecId] = useState("");
  const [selectedOpenApiRefs, setSelectedOpenApiRefs] = useState<
    OpenApiOperationRef[]
  >([]);
  const [openApiPreview, setOpenApiPreview] =
    useState<OpenApiStepDraftPreviewResponse | null>(null);
  const [openApiError, setOpenApiError] = useState<string | null>(null);
  const [curlImportText, setCurlImportText] = useState("");
  const [curlImportPreview, setCurlImportPreview] =
    useState<CurlImportParseResponse | null>(null);
  const [curlImportMode, setCurlImportMode] = useState<"append" | "replace">(
    "append",
  );
  const [applyCurlBaseUrl, setApplyCurlBaseUrl] = useState(false);
  const [curlImportError, setCurlImportError] = useState<string | null>(null);
  const [activeStepTab, setActiveStepTab] = useState<StepTabKey>("params");
  const [tagText, setTagText] = useState("");
  const [dataSourceVariableTextById, setDataSourceVariableTextById] = useState<
    Record<string, string>
  >({});
  const [selectedEnvId, setSelectedEnvId] = useState(
    () => window.localStorage.getItem(`surgepilot:scenario:${scenarioId}:env`) ?? "",
  );
  const [selectedNodeId, setSelectedNodeId] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const bypassNavigationBlockRef = useRef(false);
  const dirtyRef = useRef(false);
  const configDraftBackupRef = useRef<ScenarioDetail | null>(null);
  const configDirtyBackupRef = useRef(false);
  const hydratedScenarioIdRef = useRef<string | null>(null);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      !bypassNavigationBlockRef.current &&
      currentLocation.pathname !== nextLocation.pathname,
  );
  const workspaceSwitchGuard = useMemo(
    () => ({
      dirty,
      safePath: "/scenarios",
      onAbandon: () => {
        bypassNavigationBlockRef.current = true;
        window.localStorage.removeItem(`surgepilot:scenario:${scenarioId}:env`);
        setDirty(false);
        setShowDebug(false);
        setActionError(null);
      },
    }),
    [dirty, scenarioId],
  );
  useWorkspaceSwitchGuard(workspaceSwitchGuard);
  const scenarioQuery = useQuery({
    enabled: Boolean(workspaceId && scenarioId),
    queryKey: ["scenario", workspaceId, scenarioId],
    queryFn: () => getScenario(scenarioId, workspaceId),
  });
  const envQuery = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["env-groups", workspaceId, "scenario-picker"],
    queryFn: () => listEnvGroups({ workspaceId, pageSize: 100, sort: "name" }),
  });
  const nodeQuery = useQuery({
    enabled: showDebug && Boolean(workspaceId),
    queryKey: ["load-nodes", workspaceId, "idle-debug"],
    queryFn: () =>
      listLoadNodes({
        workspaceId,
        status: "idle",
        limit: 100,
        offset: 0,
        sort: "host",
      }),
  });
  const dependencyFilesQuery = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["dependency-files", workspaceId, "scenario-editor"],
    queryFn: () =>
      listDependencyFiles({
        workspaceId,
        pageSize: 100,
        sort: "filename",
      }),
  });
  const openApiSpecQuery = useQuery({
    enabled: showOpenApiImport && Boolean(workspaceId && scenarioId),
    queryKey: ["scenario-openapi-specs", workspaceId, scenarioId],
    queryFn: () => listScenarioOpenApiSpecSources(scenarioId, workspaceId),
    staleTime: OPENAPI_QUERY_STALE_TIME_MS,
  });
  const openApiOperationQuery = useQuery({
    enabled:
      showOpenApiImport &&
      Boolean(workspaceId && scenarioId && selectedOpenApiSpecId),
    queryKey: [
      "scenario-openapi-operations",
      workspaceId,
      scenarioId,
      selectedOpenApiSpecId,
    ],
    queryFn: () =>
      listScenarioOpenApiOperations(
        scenarioId,
        selectedOpenApiSpecId,
        workspaceId,
      ),
    staleTime: OPENAPI_QUERY_STALE_TIME_MS,
  });
  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  useEffect(() => {
    if (!scenarioQuery.data) {
      return;
    }
    const isFirstHydrateForScenario =
      hydratedScenarioIdRef.current !== scenarioId;
    if (dirtyRef.current && !isFirstHydrateForScenario) {
      return;
    }
    setDraft(scenarioQuery.data);
    setTagText(scenarioQuery.data.tags.join(", "));
    setDataSourceVariableTextById(
      dataSourceVariableText(scenarioQuery.data.dataSources),
    );
    setSelectedStepId(scenarioQuery.data.steps[0]?.id ?? null);
    hydratedScenarioIdRef.current = scenarioId;
    setDirty(false);
    setRenamingName(false);
  }, [scenarioId, scenarioQuery.data]);
  useEffect(() => {
    if (selectedEnvId)
      window.localStorage.setItem(
        `surgepilot:scenario:${scenarioId}:env`,
        selectedEnvId,
      );
    else window.localStorage.removeItem(`surgepilot:scenario:${scenarioId}:env`);
  }, [scenarioId, selectedEnvId]);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
  const saveMutation = useMutation({
    mutationFn: async (next: ScenarioDetail) =>
      patchScenario(
        next.id,
        toPatchPayload(next, next.revision),
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (updated) => {
      setDraft(updated);
      setTagText(updated.tags.join(", "));
      setDataSourceVariableTextById(
        dataSourceVariableText(updated.dataSources),
      );
      setDirty(false);
      setRenamingName(false);
      setActionError(null);
    },
    onError: (error) => {
      const details = (error as ApiError | undefined)?.body?.details ?? [];
      const fields = details
        .map((detail) =>
          typeof detail === "object" && detail && "field" in detail
            ? String(detail.field)
            : "",
        )
        .filter(Boolean);
      const firstGlobalField = fields.find((field) =>
        /^(baseUrlExpression|defaultSettings|globalHeaders|variables|dataSources)/.test(
          field,
        ),
      );
      if (firstGlobalField) {
        setShowConfig(true);
        if (firstGlobalField.startsWith("globalHeaders"))
          setActiveConfigTab("headers");
        else if (firstGlobalField.startsWith("variables"))
          setActiveConfigTab("variables");
        else if (firstGlobalField.startsWith("dataSources"))
          setActiveConfigTab("dataSources");
        else setActiveConfigTab("settings");
      }
      setActionError(errorMessage(error, "save"));
    },
  });
  const debugMutation = useMutation({
    mutationFn: async (next: ScenarioDetail) =>
      createRun(
        {
          runType: "debug",
          sourceType: "debug_scenario",
          sourceId: next.id,
          expectedSourceRevision: next.revision,
          envGroupId: selectedEnvId || null,
          selectedNodeId,
          confirmHighConcurrency: false,
        },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (run) => navigate(`/runs/${run.id}`),
    onError: (error) => {
      bypassNavigationBlockRef.current = false;
      setActionError(errorMessage(error, "debug"));
      void nodeQuery.refetch();
    },
  });
  const curlImportMutation = useMutation({
    mutationFn: async (rawCurl: string) =>
      parseScenarioCurlImport({ rawCurl }, workspaceId, await getWriteToken()),
    onSuccess: (preview) => {
      setCurlImportPreview(preview);
      setApplyCurlBaseUrl(false);
      setCurlImportError(null);
    },
    onError: (error) => {
      setCurlImportPreview(null);
      setCurlImportError(
        (error as ApiError | undefined)?.body?.code === "VALIDATION_ERROR"
          ? "The cURL command could not be imported. Check the command and try again."
          : "Import preview failed. Refresh and try again.",
      );
    },
  });
  const openApiDraftMutation = useMutation({
    mutationFn: async () =>
      generateScenarioOpenApiStepDrafts(
        scenarioId,
        {
          specId: selectedOpenApiSpecId,
          operationRefs: selectedOpenApiRefs,
          insert: selectedStepId
            ? { mode: "after_step", stepId: selectedStepId }
            : { mode: "append" },
        },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (preview) => {
      setOpenApiPreview(preview);
      setOpenApiError(null);
    },
    onError: () => {
      setOpenApiPreview(null);
      setOpenApiError("OpenAPI preview failed. Refresh and try again.");
    },
  });
  const selectedStep = useMemo(
    () =>
      draft?.steps.find((step) => step.id === selectedStepId) ??
      draft?.steps[0],
    [draft, selectedStepId],
  );
  const enabledStepCount =
    draft?.steps.filter((step) => step.enabled !== false).length ?? 0;
  const selectedEnvName =
    envQuery.data?.items.find((env) => env.id === selectedEnvId)?.name ??
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
  function updateGlobalHeader(
    headerId: string,
    fields: Partial<ScenarioNamedValue>,
  ) {
    updateDraft((current) => ({
      ...current,
      globalHeaders: current.globalHeaders.map((header) =>
        header.id === headerId ? { ...header, ...fields } : header,
      ),
    }));
  }
  function updateScenarioVariable(
    variableId: string,
    fields: Partial<ScenarioVariable>,
  ) {
    updateDraft((current) => ({
      ...current,
      variables: current.variables.map((variable) =>
        variable.id === variableId ? { ...variable, ...fields } : variable,
      ),
    }));
  }
  function cloneScenarioDetail(detail: ScenarioDetail): ScenarioDetail {
    return JSON.parse(JSON.stringify(detail)) as ScenarioDetail;
  }
  function openGlobalConfiguration() {
    if (draft) {
      configDraftBackupRef.current = cloneScenarioDetail(draft);
      configDirtyBackupRef.current = dirty;
    }
    setActiveConfigTab("settings");
    setShowConfig(true);
  }
  function cancelGlobalConfiguration() {
    if (configDraftBackupRef.current) {
      const restored = configDraftBackupRef.current;
      setDraft(restored);
      setTagText(restored.tags.join(", "));
      setDataSourceVariableTextById(
        dataSourceVariableText(restored.dataSources),
      );
      setDirty(configDirtyBackupRef.current);
    }
    configDraftBackupRef.current = null;
    setShowConfig(false);
  }
  function doneGlobalConfiguration() {
    configDraftBackupRef.current = null;
    setShowConfig(false);
  }
  function moveStep(stepId: string, direction: -1 | 1) {
    updateDraft((current) => {
      const index = current.steps.findIndex((step) => step.id === stepId);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.steps.length)
        return current;
      const next = [...current.steps];
      const [moved] = next.splice(index, 1);
      next.splice(target, 0, moved);
      return { ...current, steps: next };
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
  async function startDebug() {
    if (!draft || !selectedNodeId || enabledStepCount < 1) return;
    const saved = dirty ? await saveMutation.mutateAsync(draft) : draft;
    bypassNavigationBlockRef.current = true;
    await debugMutation.mutateAsync(saved);
  }
  function resetOpenApiImportModal() {
    setShowOpenApiImport(false);
    setSelectedOpenApiSpecId("");
    setSelectedOpenApiRefs([]);
    setOpenApiPreview(null);
    setOpenApiError(null);
    openApiDraftMutation.reset();
  }
  function toggleOpenApiOperation(ref: OpenApiOperationRef) {
    setOpenApiPreview(null);
    const isSelected = selectedOpenApiRefs.some((item) =>
      openApiRefsEqual(item, ref),
    );
    if (
      !isSelected &&
      selectedOpenApiRefs.length >= OPENAPI_MAX_OPERATION_SELECTION
    ) {
      setOpenApiError(
        `Select up to ${OPENAPI_MAX_OPERATION_SELECTION} operations at a time.`,
      );
      return;
    }
    setOpenApiError(null);
    setSelectedOpenApiRefs((current) => {
      if (current.some((item) => openApiRefsEqual(item, ref))) {
        return current.filter((item) => !openApiRefsEqual(item, ref));
      }
      return [...current, ref];
    });
  }
  function moveOpenApiOperation(index: number, direction: -1 | 1) {
    setOpenApiPreview(null);
    setSelectedOpenApiRefs((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      const [item] = next.splice(index, 1);
      next.splice(target, 0, item);
      return next;
    });
  }
  function confirmOpenApiImport() {
    if (!openApiPreview) return;
    updateDraft((current) => {
      const selectedIndex = current.steps.findIndex(
        (step) => step.id === selectedStepId,
      );
      const insertAt =
        selectedIndex >= 0 ? selectedIndex + 1 : current.steps.length;
      const importedSteps = openApiPreview.items.map((item) =>
        stepFromOpenApiGeneratedDraft(item.step),
      );
      const nextSteps = [...current.steps];
      nextSteps.splice(insertAt, 0, ...importedSteps);
      setSelectedStepId(importedSteps[0]?.id ?? selectedStepId);
      return { ...current, steps: nextSteps };
    });
    resetOpenApiImportModal();
  }
  function resetCurlImportModal() {
    setShowCurlImport(false);
    setCurlImportText("");
    setCurlImportPreview(null);
    setCurlImportMode("append");
    setApplyCurlBaseUrl(false);
    setCurlImportError(null);
    curlImportMutation.reset();
  }
  function confirmCurlImport() {
    if (!curlImportPreview) return;
    updateDraft((current) => {
      const selectedIndex = current.steps.findIndex(
        (step) => step.id === selectedStepId,
      );
      const shouldReplace = curlImportMode === "replace" && selectedIndex >= 0;
      const importedStep = stepFromCurlImportDraft(
        curlImportPreview.step,
        shouldReplace ? current.steps[selectedIndex].id : undefined,
      );
      const nextSteps = [...current.steps];
      if (shouldReplace) {
        nextSteps[selectedIndex] = importedStep;
      } else {
        const insertAt =
          selectedIndex >= 0 ? selectedIndex + 1 : nextSteps.length;
        nextSteps.splice(insertAt, 0, importedStep);
      }
      setSelectedStepId(importedStep.id);
      return {
        ...current,
        baseUrlExpression:
          applyCurlBaseUrl && curlImportPreview.baseUrlSuggestion
            ? curlImportPreview.baseUrlSuggestion
            : current.baseUrlExpression,
        steps: nextSteps,
      };
    });
    resetCurlImportModal();
  }
  if (scenarioQuery.isLoading || draft === null)
    return <div className="p-8 text-text-muted">Loading Scenario…</div>;
  return (
    <section className="mx-auto max-w-7xl space-y-5">
      <div
        className="flex flex-wrap items-start justify-between gap-4 rounded-3xl border border-white/10 bg-white/[0.05] p-5"
        data-testid="scenario-designer-header"
      >
        <div>
          <div className="flex flex-wrap items-center gap-3">
            {renamingName ? (
              <input
                aria-label={scenarioCopy.renameInputLabel}
                autoFocus
                className="min-w-0 max-w-lg rounded-xl border border-primary/40 bg-black/20 px-3 py-1 font-display text-3xl font-semibold text-white outline-none focus:ring-2 focus:ring-primary/30"
                onBlur={() => setRenamingName(false)}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter") event.currentTarget.blur();
                }}
                value={draft.name}
              />
            ) : (
              <>
                <h1 className="font-display text-3xl font-semibold text-white">
                  {draft.name}
                </h1>
                <IconActionButton
                  Icon={Pencil}
                  label={scenarioCopy.rename}
                  onClick={() => setRenamingName(true)}
                />
              </>
            )}
            <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 font-mono text-[11px] text-secondary">
              Revision {draft.revision}
            </span>
            <span
              className={`rounded-full border px-3 py-1 font-mono text-[11px] ${
                dirty
                  ? "border-warning/30 bg-warning/10 text-warning"
                  : "border-success/30 bg-success/10 text-success"
              }`}
            >
              {dirty ? "Unsaved changes" : "Saved"}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Environment"
            className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-sm text-white"
            value={selectedEnvId}
            onChange={(e) => setSelectedEnvId(e.target.value)}
          >
            <option value="">No environment</option>
            {(envQuery.data?.items ?? []).map((env) => (
              <option key={env.id} value={env.id}>
                {env.name}
              </option>
            ))}
          </select>
          {selectedEnvId ? (
            <button
              className="rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted"
              onClick={() => setSelectedEnvId("")}
              type="button"
            >
              Clear
            </button>
          ) : null}
          <button
            className="rounded-xl border border-primary/30 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary"
            onClick={openGlobalConfiguration}
            type="button"
          >
            Global Config
          </button>
          <button
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white disabled:opacity-40"
            disabled={!dirty}
            onClick={() => draft && saveMutation.mutate(draft)}
            type="button"
          >
            Save
          </button>
          <button
            title={
              dirty
                ? "Unsaved changes will be saved before the debug run."
                : undefined
            }
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-40"
            disabled={enabledStepCount < 1}
            onClick={() => setShowDebug(true)}
            type="button"
          >
            Debug
          </button>
        </div>
      </div>
      {actionError ? (
        <div className="rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
          {actionError}
        </div>
      ) : null}
      <div
        className="rounded-3xl border border-white/10 bg-white/[0.045] p-4"
        data-testid="scenario-designer-summary"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-text-muted">
            Base URL:{" "}
            <code className="font-mono text-primary">
              {draft.baseUrlExpression}
            </code>
          </div>
          <div className="flex flex-wrap gap-2 font-mono text-xs text-secondary">
            <span>
              {
                draft.dataSources.filter((item) => item.enabled !== false)
                  .length
              }{" "}
              data sources
            </span>
            <span>
              {
                draft.globalHeaders.filter((item) => item.enabled !== false)
                  .length
              }{" "}
              global headers
            </span>
            <span>
              {draft.variables.filter((item) => item.enabled !== false).length}{" "}
              variables
            </span>
            <span>
              timeout {Math.round(draft.defaultSettings.timeoutMs / 1000)}s
            </span>
            <span>think-time {draft.defaultSettings.thinkTimeMs}ms</span>
            <span>
              keep-alive {draft.defaultSettings.keepAlive ? "on" : "off"}
            </span>
            <span>
              redirects {draft.defaultSettings.followRedirects ? "on" : "off"}
            </span>
            <span className="text-primary">Global Config</span>
          </div>
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[340px_1fr]">
        <aside className="rounded-3xl border border-white/10 bg-white/[0.045] p-4">
          <div className="mb-3 space-y-2">
            <h2 className="font-semibold text-white">Steps</h2>
            <div className="grid grid-cols-3 gap-2">
              <button
                aria-label="Add Step"
                className="flex items-center justify-center gap-1 rounded-lg bg-primary px-2 py-1.5 text-sm font-semibold text-on-primary"
                onClick={() =>
                  updateDraft((current) => {
                    const step = newStep();
                    setSelectedStepId(step.id);
                    return { ...current, steps: [...current.steps, step] };
                  })
                }
                title="Add a blank HTTP Step"
                type="button"
              >
                <Plus aria-hidden className="h-4 w-4" />
                <span>Add</span>
              </button>
              <button
                aria-label="Import cURL"
                className="flex items-center justify-center gap-1 rounded-lg border border-white/10 px-2 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
                disabled={draft === null}
                onClick={() => setShowCurlImport(true)}
                title="Import one Step from cURL"
                type="button"
              >
                <Terminal aria-hidden className="h-4 w-4" />
                <span>cURL</span>
              </button>
              <button
                aria-label="From OpenAPI"
                className="flex items-center justify-center gap-1 rounded-lg border border-white/10 px-2 py-1.5 text-sm font-semibold text-white disabled:opacity-40"
                disabled={draft === null}
                onClick={() => setShowOpenApiImport(true)}
                title="Generate Step drafts from API Catalog operations"
                type="button"
              >
                <FileCode2 aria-hidden className="h-4 w-4" />
                <span>API</span>
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {draft.steps.map((step, index) => (
              <div
                className={`rounded-2xl border p-2 ${step.id === selectedStep?.id ? "border-primary/50 bg-primary/10" : "border-white/10 bg-black/10"}`}
                key={step.id}
              >
                <button
                  className="w-full px-1 py-1 text-left"
                  onClick={() => setSelectedStepId(step.id)}
                  type="button"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-white">
                      {index + 1}. {step.name}
                    </span>
                    <span className="font-mono text-xs text-primary">
                      {step.method}
                    </span>
                  </div>
                  <p className="mt-1 truncate font-mono text-xs text-text-muted">
                    {step.path}
                  </p>
                </button>
                <div className="mt-2 flex items-center gap-2 border-t border-white/10 pt-2">
                  <button
                    aria-label={`Move ${step.name} up`}
                    className="rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted disabled:opacity-40"
                    disabled={index === 0}
                    onClick={() => moveStep(step.id, -1)}
                    type="button"
                  >
                    ↑
                  </button>
                  <button
                    aria-label={`Move ${step.name} down`}
                    className="rounded-lg border border-white/10 px-2 py-1 text-xs text-text-muted disabled:opacity-40"
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
        <main className="rounded-3xl border border-white/10 bg-white/[0.045] p-5">
          {selectedStep ? (
            <div className="space-y-5">
              <div
                className="sticky top-20 z-10 rounded-2xl border border-white/10 bg-surface-container-low/95 p-3 backdrop-blur-xl"
                data-testid="step-request-bar"
              >
                <div className="grid gap-3 xl:grid-cols-[160px_1fr_auto] xl:items-end">
                  <label className="grid gap-1 text-sm text-text-muted">
                    Method
                    <select
                      className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
                      value={selectedStep.method}
                      onChange={(e) =>
                        updateStep(selectedStep.id, {
                          method: e.target.value as ScenarioStep["method"],
                        })
                      }
                    >
                      {[
                        "GET",
                        "POST",
                        "PUT",
                        "PATCH",
                        "DELETE",
                        "HEAD",
                        "OPTIONS",
                      ].map((method) => (
                        <option key={method}>{method}</option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm text-text-muted">
                    Path
                    <input
                      className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-white"
                      value={selectedStep.path}
                      onChange={(e) =>
                        updateStep(selectedStep.id, { path: e.target.value })
                      }
                    />
                  </label>
                  <div className="flex flex-wrap justify-end gap-2">
                    <button
                      className="rounded-xl border border-white/10 px-3 py-2 text-sm text-white"
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
                      className="rounded-xl border border-white/10 px-3 py-2 text-sm text-white"
                      onClick={() =>
                        updateDraft((current) => ({
                          ...current,
                          steps: [...current.steps, cloneStep(selectedStep)],
                        }))
                      }
                      type="button"
                    >
                      Duplicate
                    </button>
                    <button
                      className="rounded-xl border border-error/30 px-3 py-2 text-sm text-error"
                      onClick={() =>
                        updateDraft((current) => ({
                          ...current,
                          steps: current.steps.filter(
                            (step) => step.id !== selectedStep.id,
                          ),
                        }))
                      }
                      type="button"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
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
                      className={`-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition ${
                        isActive
                          ? "border-primary text-white"
                          : "border-transparent text-text-muted hover:text-white"
                      }`}
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
                  <div className="space-y-2">
                    {(selectedStep.queryParams ?? []).map((item, index) => (
                      <div
                        className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1fr_auto_auto]"
                        key={item.id}
                      >
                        <label className="grid gap-1 text-xs text-text-muted">
                          Query param {index + 1} name
                          <input
                            aria-label={`Query param ${index + 1} name`}
                            className={textInputClass("font-mono")}
                            value={item.name}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                queryParams: (
                                  selectedStep.queryParams ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? { ...current, name: event.target.value }
                                    : current,
                                ),
                              })
                            }
                          />
                        </label>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Query param {index + 1} value
                          <input
                            aria-label={`Query param ${index + 1} value`}
                            className={textInputClass("font-mono")}
                            value={item.value}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                queryParams: (
                                  selectedStep.queryParams ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? { ...current, value: event.target.value }
                                    : current,
                                ),
                              })
                            }
                          />
                        </label>
                        <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                          <input
                            checked={item.enabled !== false}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                queryParams: (
                                  selectedStep.queryParams ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? {
                                        ...current,
                                        enabled: event.target.checked,
                                      }
                                    : current,
                                ),
                              })
                            }
                            type="checkbox"
                          />
                          Enabled
                        </label>
                        <div className="flex items-end">
                          <MiniButton
                            onClick={() =>
                              updateStep(selectedStep.id, {
                                queryParams: (
                                  selectedStep.queryParams ?? []
                                ).filter((current) => current.id !== item.id),
                              })
                            }
                            tone="danger"
                          >
                            Remove
                          </MiniButton>
                        </div>
                      </div>
                    ))}
                    {(selectedStep.queryParams ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No query params.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "headers" ? (
                <FieldSection
                  title="Headers"
                  description="Add request headers for this step."
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
                  <div className="space-y-2">
                    {(selectedStep.headers ?? []).map((item, index) => (
                      <div
                        className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1fr_auto_auto]"
                        key={item.id}
                      >
                        <label className="grid gap-1 text-xs text-text-muted">
                          Header {index + 1} name
                          <input
                            aria-label={`Header ${index + 1} name`}
                            className={textInputClass("font-mono")}
                            value={item.name}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                headers: (selectedStep.headers ?? []).map(
                                  (current) =>
                                    current.id === item.id
                                      ? { ...current, name: event.target.value }
                                      : current,
                                ),
                              })
                            }
                          />
                        </label>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Header {index + 1} value
                          <input
                            aria-label={`Header ${index + 1} value`}
                            className={textInputClass("font-mono")}
                            value={item.value}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                headers: (selectedStep.headers ?? []).map(
                                  (current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          value: event.target.value,
                                        }
                                      : current,
                                ),
                              })
                            }
                          />
                        </label>
                        <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                          <input
                            checked={item.enabled !== false}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                headers: (selectedStep.headers ?? []).map(
                                  (current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          enabled: event.target.checked,
                                        }
                                      : current,
                                ),
                              })
                            }
                            type="checkbox"
                          />
                          Enabled
                        </label>
                        <div className="flex items-end">
                          <MiniButton
                            onClick={() =>
                              updateStep(selectedStep.id, {
                                headers: (selectedStep.headers ?? []).filter(
                                  (current) => current.id !== item.id,
                                ),
                              })
                            }
                            tone="danger"
                          >
                            Remove
                          </MiniButton>
                        </div>
                      </div>
                    ))}
                    {(selectedStep.headers ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">No headers.</p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "body" ? (
                <FieldSection
                  title="Body"
                  description="Choose the request body format for this step."
                >
                  <div className="space-y-3">
                    <label className="grid gap-1 text-sm text-text-muted">
                      Body type
                      <select
                        aria-label="Body type"
                        className={textInputClass()}
                        value={selectedStep.body?.type ?? "none"}
                        onChange={(event) =>
                          updateStep(selectedStep.id, {
                            body: {
                              type: event.target.value as NonNullable<
                                ScenarioStep["body"]
                              >["type"],
                              contentType:
                                event.target.value === "raw"
                                  ? (selectedStep.body?.contentType ?? "")
                                  : null,
                              rawText:
                                event.target.value === "raw"
                                  ? (selectedStep.body?.rawText ?? "")
                                  : null,
                              formFields:
                                event.target.value === "form"
                                  ? (selectedStep.body?.formFields ?? [])
                                  : [],
                            },
                          })
                        }
                      >
                        <option value="none">None</option>
                        <option value="raw">Raw</option>
                        <option value="form">Form</option>
                      </select>
                    </label>
                    {selectedStep.body?.type === "raw" ? (
                      <div className="grid gap-3">
                        <label className="grid gap-1 text-sm text-text-muted">
                          Raw content type
                          <input
                            aria-label="Raw content type"
                            className={textInputClass("font-mono")}
                            value={selectedStep.body.contentType ?? ""}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                body: {
                                  ...(selectedStep.body ?? { type: "raw" }),
                                  type: "raw",
                                  contentType: event.target.value,
                                  formFields: [],
                                },
                              })
                            }
                          />
                        </label>
                        <label className="grid gap-1 text-sm text-text-muted">
                          Raw request body
                          <textarea
                            aria-label="Raw request body"
                            className="min-h-32 rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-sm text-white"
                            value={selectedStep.body.rawText ?? ""}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                body: {
                                  ...(selectedStep.body ?? { type: "raw" }),
                                  type: "raw",
                                  rawText: event.target.value,
                                  formFields: [],
                                },
                              })
                            }
                          />
                        </label>
                      </div>
                    ) : null}
                    {selectedStep.body?.type === "form" ? (
                      <div className="space-y-2">
                        <MiniButton
                          onClick={() =>
                            updateStep(selectedStep.id, {
                              body: {
                                ...(selectedStep.body ?? { type: "form" }),
                                type: "form",
                                contentType: null,
                                rawText: null,
                                formFields: [
                                  ...(selectedStep.body?.formFields ?? []),
                                  newFormField(),
                                ],
                              },
                            })
                          }
                          tone="primary"
                        >
                          Add form field
                        </MiniButton>
                        {(selectedStep.body.formFields ?? []).map(
                          (item, index) => (
                            <div
                              className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1fr_auto_auto]"
                              key={item.id}
                            >
                              <label className="grid gap-1 text-xs text-text-muted">
                                Form field {index + 1} name
                                <input
                                  aria-label={`Form field ${index + 1} name`}
                                  className={textInputClass("font-mono")}
                                  value={item.name}
                                  onChange={(event) =>
                                    updateStep(selectedStep.id, {
                                      body: {
                                        ...selectedStep.body,
                                        type: "form",
                                        formFields: (
                                          selectedStep.body?.formFields ?? []
                                        ).map((current) =>
                                          current.id === item.id
                                            ? {
                                                ...current,
                                                name: event.target.value,
                                              }
                                            : current,
                                        ),
                                      },
                                    })
                                  }
                                />
                              </label>
                              <label className="grid gap-1 text-xs text-text-muted">
                                Form field {index + 1} value
                                <input
                                  aria-label={`Form field ${index + 1} value`}
                                  className={textInputClass("font-mono")}
                                  value={item.value}
                                  onChange={(event) =>
                                    updateStep(selectedStep.id, {
                                      body: {
                                        ...selectedStep.body,
                                        type: "form",
                                        formFields: (
                                          selectedStep.body?.formFields ?? []
                                        ).map((current) =>
                                          current.id === item.id
                                            ? {
                                                ...current,
                                                value: event.target.value,
                                              }
                                            : current,
                                        ),
                                      },
                                    })
                                  }
                                />
                              </label>
                              <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                                <input
                                  checked={item.enabled !== false}
                                  onChange={(event) =>
                                    updateStep(selectedStep.id, {
                                      body: {
                                        ...selectedStep.body,
                                        type: "form",
                                        formFields: (
                                          selectedStep.body?.formFields ?? []
                                        ).map((current) =>
                                          current.id === item.id
                                            ? {
                                                ...current,
                                                enabled: event.target.checked,
                                              }
                                            : current,
                                        ),
                                      },
                                    })
                                  }
                                  type="checkbox"
                                />
                                Enabled
                              </label>
                              <div className="flex items-end">
                                <MiniButton
                                  onClick={() =>
                                    updateStep(selectedStep.id, {
                                      body: {
                                        ...selectedStep.body,
                                        type: "form",
                                        formFields: (
                                          selectedStep.body?.formFields ?? []
                                        ).filter(
                                          (current) => current.id !== item.id,
                                        ),
                                      },
                                    })
                                  }
                                  tone="danger"
                                >
                                  Remove
                                </MiniButton>
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "files" ? (
                <FieldSection
                  title="Upload Files"
                  description="Attach files from Dependency Files to this request."
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
                      Add upload file
                    </MiniButton>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.uploadFiles ?? []).map((item, index) => (
                      <div
                        className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 lg:grid-cols-[1fr_1.4fr_1fr_auto_auto]"
                        key={item.id}
                      >
                        <label className="grid gap-1 text-xs text-text-muted">
                          Upload file {index + 1} field name
                          <input
                            aria-label={`Upload file ${index + 1} field name`}
                            className={textInputClass("font-mono")}
                            value={item.fieldName}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                uploadFiles: (
                                  selectedStep.uploadFiles ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? {
                                        ...current,
                                        fieldName: event.target.value,
                                      }
                                    : current,
                                ),
                              })
                            }
                          />
                        </label>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Upload file {index + 1} dependency file
                          <select
                            aria-label={`Upload file ${index + 1} dependency file`}
                            className={textInputClass()}
                            value={item.dependencyFileId}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                uploadFiles: (
                                  selectedStep.uploadFiles ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? {
                                        ...current,
                                        dependencyFileId: event.target.value,
                                      }
                                    : current,
                                ),
                              })
                            }
                          >
                            <option value="">Select a Dependency File</option>
                            {(dependencyFilesQuery.data?.items ?? []).map(
                              (file) => (
                                <option key={file.id} value={file.id}>
                                  {file.filename}
                                </option>
                              ),
                            )}
                          </select>
                        </label>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Upload file {index + 1} MIME type
                          <input
                            aria-label={`Upload file ${index + 1} MIME type`}
                            className={textInputClass("font-mono")}
                            value={item.mimeType ?? ""}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                uploadFiles: (
                                  selectedStep.uploadFiles ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? {
                                        ...current,
                                        mimeType: event.target.value || null,
                                      }
                                    : current,
                                ),
                              })
                            }
                          />
                        </label>
                        <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                          <input
                            checked={item.enabled !== false}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                uploadFiles: (
                                  selectedStep.uploadFiles ?? []
                                ).map((current) =>
                                  current.id === item.id
                                    ? {
                                        ...current,
                                        enabled: event.target.checked,
                                      }
                                    : current,
                                ),
                              })
                            }
                            type="checkbox"
                          />
                          Enabled
                        </label>
                        <div className="flex items-end">
                          <MiniButton
                            onClick={() =>
                              updateStep(selectedStep.id, {
                                uploadFiles: (
                                  selectedStep.uploadFiles ?? []
                                ).filter((current) => current.id !== item.id),
                              })
                            }
                            tone="danger"
                          >
                            Remove
                          </MiniButton>
                        </div>
                      </div>
                    ))}
                    {(selectedStep.uploadFiles ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        No upload files.
                      </p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "extractors" ? (
                <FieldSection
                  title="Extractors"
                  description="Capture values from the response for later steps."
                  action={
                    <div className="flex flex-wrap gap-2">
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
                        Add JSONPath extractor
                      </MiniButton>
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            extractors: [
                              ...(selectedStep.extractors ?? []),
                              newExtractor("regexp"),
                            ],
                          })
                        }
                        tone="primary"
                      >
                        Add Regexp extractor
                      </MiniButton>
                    </div>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.extractors ?? []).map((item, index) => (
                      <div
                        className="space-y-3 rounded-xl border border-white/10 bg-white/[0.03] p-3"
                        key={item.id}
                      >
                        <div className="grid gap-2 lg:grid-cols-[0.9fr_1fr_1.6fr_0.7fr_auto_auto]">
                          <label className="grid gap-1 text-xs text-text-muted">
                            Extractor {index + 1} type
                            <select
                              className={textInputClass()}
                              value={item.type}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          type: event.target
                                            .value as ScenarioExtractor["type"],
                                          template:
                                            event.target.value === "regexp"
                                              ? (current.template ?? "1")
                                              : null,
                                        }
                                      : current,
                                  ),
                                })
                              }
                            >
                              <option value="jsonpath">JSONPath</option>
                              <option value="regexp">Regexp</option>
                            </select>
                          </label>
                          <label className="grid gap-1 text-xs text-text-muted">
                            Extractor {index + 1} variable name
                            <input
                              aria-label={`Extractor ${index + 1} variable name`}
                              className={textInputClass("font-mono")}
                              value={item.variableName}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          variableName: event.target.value,
                                        }
                                      : current,
                                  ),
                                })
                              }
                            />
                          </label>
                          <label className="grid gap-1 text-xs text-text-muted">
                            Extractor {index + 1} expression
                            <input
                              aria-label={`Extractor ${index + 1} expression`}
                              className={textInputClass("font-mono")}
                              value={item.expression}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          expression: event.target.value,
                                        }
                                      : current,
                                  ),
                                })
                              }
                            />
                          </label>
                          <label className="grid gap-1 text-xs text-text-muted">
                            Match no
                            <input
                              className={textInputClass("font-mono")}
                              type="number"
                              value={item.matchNo}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          matchNo: Number(event.target.value),
                                        }
                                      : current,
                                  ),
                                })
                              }
                            />
                          </label>
                          <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                            <input
                              checked={item.enabled !== false}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          enabled: event.target.checked,
                                        }
                                      : current,
                                  ),
                                })
                              }
                              type="checkbox"
                            />
                            Enabled
                          </label>
                          <div className="flex items-end">
                            <MiniButton
                              onClick={() =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).filter((current) => current.id !== item.id),
                                })
                              }
                              tone="danger"
                            >
                              Remove
                            </MiniButton>
                          </div>
                        </div>
                        <div className="grid gap-2 md:grid-cols-3">
                          <label className="grid gap-1 text-xs text-text-muted">
                            Default value
                            <input
                              className={textInputClass("font-mono")}
                              value={item.defaultValue ?? ""}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          defaultValue: event.target.value,
                                        }
                                      : current,
                                  ),
                                })
                              }
                            />
                          </label>
                          <label className="grid gap-1 text-xs text-text-muted">
                            Subject
                            <select
                              className={textInputClass()}
                              value={item.subject ?? "body"}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  extractors: (
                                    selectedStep.extractors ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          subject: event.target.value,
                                        }
                                      : current,
                                  ),
                                })
                              }
                            >
                              <option value="body">body</option>
                              <option value="body-unescaped">
                                body-unescaped
                              </option>
                              <option value="body-as-document">
                                body-as-document
                              </option>
                              <option value="response-headers">
                                response-headers
                              </option>
                              <option value="request-headers">
                                request-headers
                              </option>
                              <option value="url">url</option>
                              <option value="code">code</option>
                              <option value="message">message</option>
                            </select>
                          </label>
                          {item.type === "regexp" ? (
                            <label className="grid gap-1 text-xs text-text-muted">
                              Extractor {index + 1} template
                              <input
                                aria-label={`Extractor ${index + 1} template`}
                                className={textInputClass("font-mono")}
                                value={item.template ?? ""}
                                onChange={(event) =>
                                  updateStep(selectedStep.id, {
                                    extractors: (
                                      selectedStep.extractors ?? []
                                    ).map((current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            template: event.target.value,
                                          }
                                        : current,
                                    ),
                                  })
                                }
                              />
                            </label>
                          ) : null}
                        </div>
                      </div>
                    ))}
                    {(selectedStep.extractors ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">No extractors.</p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "assertions" ? (
                <FieldSection
                  title="Assertions"
                  description="Check the response before the step is considered successful."
                  action={
                    <div className="flex flex-wrap gap-2">
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            assertions: [
                              ...(selectedStep.assertions ?? []),
                              newAssertion("status_code"),
                            ],
                          })
                        }
                        tone="primary"
                      >
                        Add Status Code assertion
                      </MiniButton>
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            assertions: [
                              ...(selectedStep.assertions ?? []),
                              newAssertion("body_contains"),
                            ],
                          })
                        }
                        tone="primary"
                      >
                        Add Body Contains assertion
                      </MiniButton>
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            assertions: [
                              ...(selectedStep.assertions ?? []),
                              newAssertion("jsonpath_exists"),
                            ],
                          })
                        }
                        tone="primary"
                      >
                        Add JSONPath Exists assertion
                      </MiniButton>
                      <MiniButton
                        onClick={() =>
                          updateStep(selectedStep.id, {
                            assertions: [
                              ...(selectedStep.assertions ?? []),
                              newAssertion("jsonpath_equals"),
                            ],
                          })
                        }
                        tone="primary"
                      >
                        Add JSONPath Equals assertion
                      </MiniButton>
                    </div>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.assertions ?? []).map((item, index) => (
                      <div
                        className="space-y-3 rounded-xl border border-white/10 bg-white/[0.03] p-3"
                        key={item.id}
                      >
                        <div className="grid gap-2 lg:grid-cols-[1fr_1fr_auto_auto]">
                          <label className="grid gap-1 text-xs text-text-muted">
                            Assertion {index + 1} type
                            <select
                              className={textInputClass()}
                              value={item.type}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  assertions: (
                                    selectedStep.assertions ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...newAssertion(
                                            event.target
                                              .value as ScenarioAssertion["type"],
                                          ),
                                          id: current.id,
                                          enabled: current.enabled,
                                        }
                                      : current,
                                  ),
                                })
                              }
                            >
                              <option value="status_code">Status Code</option>
                              <option value="body_contains">
                                Body Contains
                              </option>
                              <option value="jsonpath_exists">
                                JSONPath Exists
                              </option>
                              <option value="jsonpath_equals">
                                JSONPath Equals
                              </option>
                            </select>
                          </label>
                          {item.type === "status_code" ? (
                            <label className="grid gap-1 text-xs text-text-muted">
                              Assertion {index + 1} expected status
                              <input
                                aria-label={`Assertion ${index + 1} expected status`}
                                className={textInputClass("font-mono")}
                                type="number"
                                value={item.expectedStatus ?? 200}
                                onChange={(event) =>
                                  updateStep(selectedStep.id, {
                                    assertions: (
                                      selectedStep.assertions ?? []
                                    ).map((current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            expectedStatus: Number(
                                              event.target.value,
                                            ),
                                          }
                                        : current,
                                    ),
                                  })
                                }
                              />
                            </label>
                          ) : null}
                          {item.type === "body_contains" ? (
                            <label className="grid gap-1 text-xs text-text-muted">
                              Assertion {index + 1} contains
                              <input
                                aria-label={`Assertion ${index + 1} contains`}
                                className={textInputClass("font-mono")}
                                value={item.contains ?? ""}
                                onChange={(event) =>
                                  updateStep(selectedStep.id, {
                                    assertions: (
                                      selectedStep.assertions ?? []
                                    ).map((current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            contains: event.target.value,
                                          }
                                        : current,
                                    ),
                                  })
                                }
                              />
                            </label>
                          ) : null}
                          {item.type === "jsonpath_exists" ||
                          item.type === "jsonpath_equals" ? (
                            <label className="grid gap-1 text-xs text-text-muted">
                              Assertion {index + 1} JSONPath
                              <input
                                aria-label={`Assertion ${index + 1} JSONPath`}
                                className={textInputClass("font-mono")}
                                value={item.jsonpath ?? ""}
                                onChange={(event) =>
                                  updateStep(selectedStep.id, {
                                    assertions: (
                                      selectedStep.assertions ?? []
                                    ).map((current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            jsonpath: event.target.value,
                                          }
                                        : current,
                                    ),
                                  })
                                }
                              />
                            </label>
                          ) : null}
                          {item.type === "jsonpath_equals" ? (
                            <label className="grid gap-1 text-xs text-text-muted">
                              Assertion {index + 1} expected value
                              <input
                                aria-label={`Assertion ${index + 1} expected value`}
                                className={textInputClass("font-mono")}
                                value={item.expectedValue ?? ""}
                                onChange={(event) =>
                                  updateStep(selectedStep.id, {
                                    assertions: (
                                      selectedStep.assertions ?? []
                                    ).map((current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            expectedValue: event.target.value,
                                          }
                                        : current,
                                    ),
                                  })
                                }
                              />
                            </label>
                          ) : null}
                          <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                            <input
                              checked={item.enabled !== false}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  assertions: (
                                    selectedStep.assertions ?? []
                                  ).map((current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          enabled: event.target.checked,
                                        }
                                      : current,
                                  ),
                                })
                              }
                              type="checkbox"
                            />
                            Enabled
                          </label>
                          <div className="flex items-end">
                            <MiniButton
                              onClick={() =>
                                updateStep(selectedStep.id, {
                                  assertions: (
                                    selectedStep.assertions ?? []
                                  ).filter((current) => current.id !== item.id),
                                })
                              }
                              tone="danger"
                            >
                              Remove
                            </MiniButton>
                          </div>
                        </div>
                        {item.type === "body_contains" ||
                        item.type === "jsonpath_equals" ? (
                          <div className="flex flex-wrap gap-4 text-xs text-text-muted">
                            <label className="flex items-center gap-2">
                              <input
                                checked={item.regexp}
                                onChange={(event) =>
                                  updateStep(selectedStep.id, {
                                    assertions: (
                                      selectedStep.assertions ?? []
                                    ).map((current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            regexp: event.target.checked,
                                          }
                                        : current,
                                    ),
                                  })
                                }
                                type="checkbox"
                              />
                              Regexp
                            </label>
                            {item.type === "body_contains" ? (
                              <label className="flex items-center gap-2">
                                <input
                                  checked={item.not}
                                  onChange={(event) =>
                                    updateStep(selectedStep.id, {
                                      assertions: (
                                        selectedStep.assertions ?? []
                                      ).map((current) =>
                                        current.id === item.id
                                          ? {
                                              ...current,
                                              not: event.target.checked,
                                            }
                                          : current,
                                      ),
                                    })
                                  }
                                  type="checkbox"
                                />
                                Not
                              </label>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    ))}
                    {(selectedStep.assertions ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">No assertions.</p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "scripts" ? (
                <FieldSection
                  title="Scripts"
                  description="Request-level Groovy JSR223 scripts execute on the selected Load Node."
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
                        tone="primary"
                      >
                        Add Groovy after script
                      </MiniButton>
                    </div>
                  }
                >
                  <div className="space-y-2">
                    {(selectedStep.scripts ?? []).map((item, index) => (
                      <div
                        className="space-y-3 rounded-xl border border-warning/20 bg-warning/5 p-3"
                        key={item.id}
                      >
                        <div className="grid gap-2 md:grid-cols-[1fr_auto_auto]">
                          <label className="grid gap-1 text-xs text-text-muted">
                            Execute
                            <select
                              className={textInputClass()}
                              value={item.execute}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  scripts: (selectedStep.scripts ?? []).map(
                                    (current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            execute: event.target
                                              .value as ScenarioScript["execute"],
                                          }
                                        : current,
                                  ),
                                })
                              }
                            >
                              <option value="before">Before request</option>
                              <option value="after">After request</option>
                            </select>
                          </label>
                          <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                            <input
                              checked={item.enabled !== false}
                              onChange={(event) =>
                                updateStep(selectedStep.id, {
                                  scripts: (selectedStep.scripts ?? []).map(
                                    (current) =>
                                      current.id === item.id
                                        ? {
                                            ...current,
                                            enabled: event.target.checked,
                                          }
                                        : current,
                                  ),
                                })
                              }
                              type="checkbox"
                            />
                            Enabled
                          </label>
                          <div className="flex items-end">
                            <MiniButton
                              onClick={() =>
                                updateStep(selectedStep.id, {
                                  scripts: (selectedStep.scripts ?? []).filter(
                                    (current) => current.id !== item.id,
                                  ),
                                })
                              }
                              tone="danger"
                            >
                              Remove
                            </MiniButton>
                          </div>
                        </div>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Script {index + 1} Groovy file
                          <select
                            aria-label={`Script ${index + 1} Groovy file`}
                            className={textInputClass()}
                            value={item.dependencyFileId ?? ""}
                            onChange={(event) =>
                              updateStep(selectedStep.id, {
                                scripts: (selectedStep.scripts ?? []).map(
                                  (current) =>
                                    current.id === item.id
                                      ? {
                                          ...current,
                                          dependencyFileId: event.target.value,
                                        }
                                      : current,
                                ),
                              })
                            }
                          >
                            <option value="">
                              Select a Groovy Dependency File
                            </option>
                            {(dependencyFilesQuery.data?.items ?? []).map(
                              (file) => {
                                const isGroovy = file.filename
                                  .toLowerCase()
                                  .endsWith(".groovy");
                                return (
                                  <option
                                    disabled={!isGroovy}
                                    key={file.id}
                                    value={file.id}
                                  >
                                    {file.filename}
                                    {isGroovy ? "" : " (not .groovy)"}
                                  </option>
                                );
                              },
                            )}
                          </select>
                          <span className="text-[11px] text-text-muted">
                            Upload Groovy scripts in Assets → Dependency Files,
                            then select them here. Enabled scripts are validated
                            by the API.
                          </span>
                        </label>
                      </div>
                    ))}
                    {(selectedStep.scripts ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">No scripts.</p>
                    ) : null}
                  </div>
                </FieldSection>
              ) : null}
              {activeStepTab === "settings" ? (
                <FieldSection
                  title="Step Settings"
                  description="Optional request-level overrides. Blank values inherit Scenario defaults."
                >
                  <div
                    className="grid gap-3"
                    data-testid="step-settings-fields"
                  >
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step think time override (ms)
                      <input
                        aria-label="Step think time override (ms)"
                        className={textInputClass("font-mono")}
                        type="number"
                        value={selectedStep.settings?.thinkTimeMs ?? ""}
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
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step timeout override (ms)
                      <input
                        aria-label="Step timeout override (ms)"
                        className={textInputClass("font-mono")}
                        type="number"
                        value={selectedStep.settings?.timeoutMs ?? ""}
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
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-text-muted md:grid-cols-[260px_1fr] md:items-center">
                      Step follow redirects override
                      <select
                        aria-label="Step follow redirects override"
                        className={textInputClass()}
                        value={booleanOverrideValue(
                          selectedStep.settings?.followRedirects,
                        )}
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
                        value={booleanOverrideValue(
                          selectedStep.settings?.keepAlive,
                        )}
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
              <h2 className="text-xl font-semibold text-white">
                No Step selected
              </h2>
              <button
                className="mt-4 rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary"
                onClick={() =>
                  updateDraft((current) => {
                    const step = newStep();
                    setSelectedStepId(step.id);
                    return { ...current, steps: [...current.steps, step] };
                  })
                }
                type="button"
              >
                Add Step
              </button>
            </div>
          )}
        </main>
      </div>
      {blocker.state === "blocked" ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <h2 className="text-xl font-semibold text-white">
              Leave without saving?
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              This Scenario has unsaved changes. Save before leaving or discard
              the draft.
            </p>
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white"
                onClick={() => blocker.reset()}
                type="button"
              >
                Stay
              </button>
              <button
                className="rounded-xl border border-error/30 px-4 py-2 text-sm text-error"
                onClick={() => blocker.proceed()}
                type="button"
              >
                Discard and leave
              </button>
            </div>
          </div>
        </div>
      ) : null}
      {showCurlImport ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  {scenarioCopy.curlImportTitle}
                </h2>
                <p className="mt-1 max-w-2xl text-sm text-text-muted">
                  {scenarioCopy.curlImportDescription}
                </p>
              </div>
              <button
                className="text-sm text-text-muted"
                onClick={resetCurlImportModal}
                type="button"
              >
                Close
              </button>
            </div>
            <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
              <div className="space-y-3">
                <label className="grid gap-1 text-sm text-text-muted">
                  cURL command
                  <textarea
                    aria-label="cURL command"
                    className="min-h-44 rounded-2xl border border-white/10 bg-black/30 px-3 py-2 font-mono text-sm text-white"
                    placeholder="curl -X POST https://api.example.test/v1/orders"
                    value={curlImportText}
                    onChange={(event) => setCurlImportText(event.target.value)}
                  />
                </label>
                {curlImportError ? (
                  <div className="rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
                    {curlImportError}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <button
                    className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-40"
                    disabled={
                      curlImportMutation.isPending || !curlImportText.trim()
                    }
                    onClick={() => curlImportMutation.mutate(curlImportText)}
                    type="button"
                  >
                    {curlImportMutation.isPending
                      ? "Previewing…"
                      : "Preview import"}
                  </button>
                  <button
                    className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white"
                    onClick={() => {
                      setCurlImportPreview(null);
                      setCurlImportError(null);
                    }}
                    type="button"
                  >
                    Reset preview
                  </button>
                </div>
              </div>
              <div className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                {curlImportPreview ? (
                  <>
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
                        Step preview
                      </p>
                      <p className="mt-2 font-mono text-lg font-semibold text-primary">
                        {curlImportPreview.step.method}{" "}
                        {curlImportPreview.step.path}
                      </p>
                    </div>
                    {curlImportPreview.baseUrlSuggestion ? (
                      <div className="rounded-xl border border-primary/20 bg-primary/10 p-3">
                        <p className="text-sm font-medium text-white">
                          Base URL suggestion
                        </p>
                        <code className="mt-1 block break-all text-sm text-primary">
                          {curlImportPreview.baseUrlSuggestion}
                        </code>
                        <label className="mt-2 flex items-center gap-2 text-sm text-text-muted">
                          <input
                            checked={applyCurlBaseUrl}
                            onChange={(event) =>
                              setApplyCurlBaseUrl(event.target.checked)
                            }
                            type="checkbox"
                          />
                          Apply to Global Config
                        </label>
                      </div>
                    ) : null}
                    <div className="grid gap-2 text-sm">
                      <div>
                        <p className="text-text-muted">Query params</p>
                        {(curlImportPreview.step.queryParams ?? []).length >
                        0 ? (
                          <div className="mt-1 flex flex-wrap gap-2">
                            {(curlImportPreview.step.queryParams ?? []).map(
                              (item, index) => (
                                <span
                                  className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 font-mono text-xs text-white"
                                  key={`${item.name}-${index}`}
                                >
                                  {item.name}={item.value}
                                </span>
                              ),
                            )}
                          </div>
                        ) : (
                          <p className="mt-1 text-text-muted">None</p>
                        )}
                      </div>
                      <div>
                        <p className="text-text-muted">Headers</p>
                        {(curlImportPreview.step.headers ?? []).length > 0 ? (
                          <div className="mt-1 flex flex-wrap gap-2">
                            {(curlImportPreview.step.headers ?? []).map(
                              (item, index) => (
                                <span
                                  className="rounded-lg border border-white/10 bg-white/5 px-2 py-1 font-mono text-xs text-white"
                                  key={`${item.name}-${index}`}
                                >
                                  {item.name}
                                </span>
                              ),
                            )}
                          </div>
                        ) : (
                          <p className="mt-1 text-text-muted">None</p>
                        )}
                      </div>
                      <div>
                        <p className="text-text-muted">Body</p>
                        <p className="mt-1 break-all font-mono text-xs text-white">
                          {curlImportPreview.step.body?.type === "raw"
                            ? `${curlImportPreview.step.body.contentType ?? "raw"} · ${
                                curlImportPreview.step.body.rawText?.length ?? 0
                              } chars`
                            : curlImportPreview.step.body?.type === "form"
                              ? `${curlImportPreview.step.body.formFields?.length ?? 0} form fields`
                              : "None"}
                        </p>
                      </div>
                    </div>
                    {hasSensitiveCurlWarning(curlImportPreview) ? (
                      <div className="rounded-xl border border-warning/30 bg-warning/10 p-3">
                        <p className="font-semibold text-warning">
                          Sensitive information warning
                        </p>
                        <p className="mt-1 text-sm text-text-muted">
                          {scenarioCopy.curlImportSensitiveWarning}
                        </p>
                      </div>
                    ) : null}
                    {(curlImportPreview.warnings ?? []).length > 0 ? (
                      <div>
                        <p className="text-sm font-medium text-white">
                          Warnings
                        </p>
                        <ul className="mt-1 space-y-1 text-sm text-text-muted">
                          {curlImportPreview.warnings.map((warning, index) => (
                            <li key={`${warning.code}-${index}`}>
                              {warning.message}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {(curlImportPreview.unsupportedOptions ?? []).length > 0 ? (
                      <div>
                        <p className="text-sm font-medium text-white">
                          Not imported
                        </p>
                        <div className="mt-1 flex flex-wrap gap-2">
                          {curlImportPreview.unsupportedOptions.map((item) => (
                            <span
                              className="rounded-lg border border-warning/20 bg-warning/10 px-2 py-1 font-mono text-xs text-warning"
                              key={`${item.option}-${item.reasonCode}`}
                            >
                              {item.option}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <div className="grid gap-2 rounded-xl border border-white/10 p-3">
                      <label className="flex items-center gap-2 text-sm text-white">
                        <input
                          checked={curlImportMode === "append"}
                          onChange={() => setCurlImportMode("append")}
                          type="radio"
                        />
                        Append after selected Step
                      </label>
                      <label className="flex items-center gap-2 text-sm text-white">
                        <input
                          checked={curlImportMode === "replace"}
                          onChange={() => setCurlImportMode("replace")}
                          type="radio"
                        />
                        Replace selected Step
                      </label>
                    </div>
                    <button
                      className="w-full rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
                      onClick={confirmCurlImport}
                      type="button"
                    >
                      Import Step
                    </button>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-white/15 p-6 text-center text-sm text-text-muted">
                    Preview appears here before anything is added to the
                    Scenario draft.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {showOpenApiImport ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div
            aria-labelledby="openapi-import-title"
            className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-3xl border border-white/10 bg-surface-container-low p-6 shadow-2xl"
            role="dialog"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2
                  className="text-xl font-semibold text-white"
                  id="openapi-import-title"
                >
                  {scenarioCopy.openApiImportTitle}
                </h2>
                <p className="mt-1 max-w-3xl text-sm text-text-muted">
                  {scenarioCopy.openApiImportDescription}
                </p>
              </div>
              <button
                className="text-sm text-text-muted"
                onClick={resetOpenApiImportModal}
                type="button"
              >
                Close
              </button>
            </div>
            <div className="mt-5 grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
              <div className="space-y-4">
                <label className="grid gap-1 text-sm text-text-muted">
                  API Catalog spec
                  <select
                    aria-label="API Catalog spec"
                    className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-white"
                    disabled={openApiSpecQuery.isFetching}
                    onChange={(event) => {
                      setSelectedOpenApiSpecId(event.target.value);
                      setSelectedOpenApiRefs([]);
                      setOpenApiPreview(null);
                      setOpenApiError(null);
                    }}
                    value={selectedOpenApiSpecId}
                  >
                    <option value="">
                      {openApiSpecQuery.isFetching
                        ? "Loading API Catalog specs…"
                        : "Select a spec"}
                    </option>
                    {(openApiSpecQuery.data?.items ?? []).map((spec) => (
                      <option key={spec.id} value={spec.id}>
                        {spec.name} · {spec.documentVersion}
                      </option>
                    ))}
                  </select>
                </label>
                {openApiSpecQuery.isSuccess &&
                (openApiSpecQuery.data?.items ?? []).length === 0 ? (
                  <div className="rounded-xl border border-dashed border-white/15 p-4 text-sm text-text-muted">
                    No API Catalog specs are available in this Workspace.
                  </div>
                ) : null}
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">Operations</p>
                      <p className="text-sm text-text-muted">
                        Select one or more supported operations.
                      </p>
                    </div>
                    {openApiOperationQuery.isFetching ? (
                      <span className="text-xs text-text-muted">
                        Loading operations…
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
                    {(openApiOperationQuery.data?.items ?? []).map(
                      (operation) => {
                        const checked = selectedOpenApiRefs.some((ref) =>
                          openApiRefsEqual(ref, operation.ref),
                        );
                        return (
                          <label
                            className={`flex items-start gap-3 rounded-xl border p-3 text-sm ${
                              operation.supportedForGeneration
                                ? "border-white/10 bg-white/5"
                                : "border-warning/20 bg-warning/10 opacity-70"
                            }`}
                            key={openApiOperationKey(operation.ref)}
                          >
                            <input
                              checked={checked}
                              className="mt-1"
                              disabled={
                                openApiOperationQuery.isFetching ||
                                !operation.supportedForGeneration ||
                                (!checked &&
                                  selectedOpenApiRefs.length >=
                                    OPENAPI_MAX_OPERATION_SELECTION)
                              }
                              onChange={() =>
                                toggleOpenApiOperation(operation.ref)
                              }
                              type="checkbox"
                            />
                            <span>
                              <span className="block font-medium text-white">
                                {operation.displayName}
                              </span>
                              <span className="mt-1 block font-mono text-xs text-text-muted">
                                {operation.method} {operation.path}
                              </span>
                            </span>
                          </label>
                        );
                      },
                    )}
                    {selectedOpenApiSpecId &&
                    openApiOperationQuery.isSuccess &&
                    (openApiOperationQuery.data?.items ?? []).length === 0 ? (
                      <p className="text-sm text-text-muted">
                        This spec does not contain supported operations.
                      </p>
                    ) : null}
                  </div>
                </div>
                {selectedOpenApiRefs.length > 0 ? (
                  <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="font-medium text-white">Generation order</p>
                    <p className="mt-1 text-xs text-text-muted">
                      {selectedOpenApiRefs.length} /{" "}
                      {OPENAPI_MAX_OPERATION_SELECTION} operations selected.
                    </p>
                    <div className="mt-3 space-y-2">
                      {selectedOpenApiRefs.map((ref, index) => (
                        <div
                          className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2"
                          key={openApiOperationKey(ref)}
                        >
                          <span className="font-mono text-xs text-white">
                            {index + 1}. {ref.method} {ref.path}
                          </span>
                          <span className="flex gap-1">
                            <MiniButton
                              disabled={index === 0}
                              onClick={() => moveOpenApiOperation(index, -1)}
                            >
                              Up
                            </MiniButton>
                            <MiniButton
                              disabled={
                                index === selectedOpenApiRefs.length - 1
                              }
                              onClick={() => moveOpenApiOperation(index, 1)}
                            >
                              Down
                            </MiniButton>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {openApiError ? (
                  <div className="rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
                    {openApiError}
                  </div>
                ) : null}
                <button
                  className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary disabled:opacity-40"
                  disabled={
                    openApiDraftMutation.isPending ||
                    openApiOperationQuery.isFetching ||
                    !selectedOpenApiSpecId ||
                    selectedOpenApiRefs.length === 0
                  }
                  onClick={() => openApiDraftMutation.mutate()}
                  type="button"
                >
                  {openApiDraftMutation.isPending
                    ? "Generating…"
                    : "Preview Step drafts"}
                </button>
              </div>
              <div className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                {openApiPreview ? (
                  <>
                    <div>
                      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
                        Draft preview
                      </p>
                      <p className="mt-2 text-sm text-text-muted">
                        These Steps are editable and are not saved until you
                        save the Scenario.
                      </p>
                    </div>
                    <div className="space-y-3">
                      {openApiPreview.items.map((item, index) => (
                        <div
                          className="rounded-xl border border-white/10 bg-white/5 p-3"
                          key={`${openApiOperationKey(item.operationRef)}-${index}`}
                        >
                          <p className="font-mono text-sm font-semibold text-primary">
                            {index + 1}. {item.step.method} {item.step.path}
                          </p>
                          <p className="mt-1 text-sm text-white">
                            {item.step.name}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-muted">
                            <span>
                              {(item.step.queryParams ?? []).length} params
                            </span>
                            <span>
                              {(item.step.headers ?? []).length} headers
                            </span>
                            <span>
                              {item.step.body?.type === "raw"
                                ? `${item.step.body.contentType ?? "raw"} body`
                                : "no body"}
                            </span>
                          </div>
                          {(item.warnings ?? []).length > 0 ? (
                            <ul className="mt-2 space-y-1 text-sm text-warning">
                              {item.warnings.map((warning, warningIndex) => (
                                <li key={`${warning.code}-${warningIndex}`}>
                                  {warning.message}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      ))}
                    </div>
                    <button
                      className="w-full rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
                      onClick={confirmOpenApiImport}
                      type="button"
                    >
                      Insert Step drafts
                    </button>
                  </>
                ) : (
                  <div className="rounded-xl border border-dashed border-white/15 p-6 text-center text-sm text-text-muted">
                    Preview appears here before anything is added to the
                    Scenario draft.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {showConfig ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div
            aria-label="Global Configuration"
            className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-3xl border border-white/10 bg-surface-container-low p-6"
            role="dialog"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Global Configuration
                </h2>
                <p className="mt-1 text-sm text-text-muted">
                  Configure Scenario defaults, global headers, non-secret
                  variables, and CSV data sources for generated JMeter runs.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white"
                  onClick={cancelGlobalConfiguration}
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary"
                  onClick={doneGlobalConfiguration}
                  type="button"
                >
                  Done
                </button>
              </div>
            </div>
            <div
              aria-label="Global Configuration tabs"
              className="mt-5 flex flex-wrap gap-2 border-b border-white/10"
              role="tablist"
            >
              {globalConfigTabs.map((tab) => {
                const isActive = activeConfigTab === tab.key;
                const count =
                  tab.key === "headers"
                    ? draft.globalHeaders.length
                    : tab.key === "variables"
                      ? draft.variables.length
                      : tab.key === "dataSources"
                        ? draft.dataSources.length
                        : 0;
                return (
                  <button
                    aria-selected={isActive}
                    className={`-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition ${
                      isActive
                        ? "border-primary text-white"
                        : "border-transparent text-text-muted hover:text-white"
                    }`}
                    key={tab.key}
                    onClick={() => setActiveConfigTab(tab.key)}
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
            {activeConfigTab === "settings" ? (
              <div className="mt-5 space-y-4">
                <label className="grid gap-1 text-sm text-text-muted">
                  Scenario name
                  <input
                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                    value={draft.name}
                    onChange={(e) =>
                      updateDraft((current) => ({
                        ...current,
                        name: e.target.value,
                      }))
                    }
                  />
                </label>
                <label className="grid gap-1 text-sm text-text-muted">
                  Base URL expression
                  <input
                    className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-white"
                    value={draft.baseUrlExpression}
                    onChange={(e) =>
                      updateDraft((current) => ({
                        ...current,
                        baseUrlExpression: e.target.value,
                      }))
                    }
                  />
                </label>
                <div className="grid gap-3 sm:grid-cols-[1.5fr_1fr]">
                  <label className="grid gap-1 text-sm text-text-muted">
                    Scenario description
                    <textarea
                      aria-label="Scenario description"
                      className="min-h-24 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                      value={draft.description ?? ""}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          description: event.target.value || null,
                        }))
                      }
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-text-muted">
                    Tags
                    <input
                      aria-label="Tags"
                      className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 font-mono text-white"
                      placeholder="checkout, smoke"
                      value={tagText}
                      onChange={(event) => {
                        setTagText(event.target.value);
                        updateDraft((current) => ({
                          ...current,
                          tags: parseCsvNames(event.target.value),
                        }));
                      }}
                    />
                  </label>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="grid gap-1 text-sm text-text-muted">
                    Think time (ms)
                    <input
                      className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                      type="number"
                      value={draft.defaultSettings.thinkTimeMs}
                      onChange={(e) =>
                        updateDraft((current) => ({
                          ...current,
                          defaultSettings: {
                            ...current.defaultSettings,
                            thinkTimeMs: Number(e.target.value),
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="grid gap-1 text-sm text-text-muted">
                    Timeout (ms)
                    <input
                      className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                      type="number"
                      value={draft.defaultSettings.timeoutMs}
                      onChange={(e) =>
                        updateDraft((current) => ({
                          ...current,
                          defaultSettings: {
                            ...current.defaultSettings,
                            timeoutMs: Number(e.target.value),
                          },
                        }))
                      }
                    />
                  </label>
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
                            key as keyof typeof draft.defaultSettings
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
            {activeConfigTab === "headers" ? (
              <FieldSection
                title="Global Headers"
                description="Apply HTTP headers to every enabled request. Step headers with the same name override these values."
                action={
                  <MiniButton
                    onClick={() =>
                      updateDraft((current) => ({
                        ...current,
                        globalHeaders: [
                          ...current.globalHeaders,
                          newNamedValue(),
                        ],
                      }))
                    }
                    tone="primary"
                  >
                    Add global header
                  </MiniButton>
                }
              >
                <div className="space-y-2">
                  {draft.globalHeaders.map((item, index) => (
                    <div
                      className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1fr_auto_auto]"
                      key={item.id}
                    >
                      <label className="grid gap-1 text-xs text-text-muted">
                        Global header {index + 1} name
                        <input
                          aria-label={`Global header ${index + 1} name`}
                          className={textInputClass("font-mono")}
                          value={item.name}
                          onChange={(event) =>
                            updateGlobalHeader(item.id, {
                              name: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="grid gap-1 text-xs text-text-muted">
                        Global header {index + 1} value
                        <input
                          aria-label={`Global header ${index + 1} value`}
                          className={textInputClass("font-mono")}
                          value={item.value}
                          onChange={(event) =>
                            updateGlobalHeader(item.id, {
                              value: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                        <input
                          checked={item.enabled !== false}
                          onChange={(event) =>
                            updateGlobalHeader(item.id, {
                              enabled: event.target.checked,
                            })
                          }
                          type="checkbox"
                        />
                        Enabled
                      </label>
                      <div className="flex items-end">
                        <MiniButton
                          onClick={() =>
                            updateDraft((current) => ({
                              ...current,
                              globalHeaders: current.globalHeaders.filter(
                                (header) => header.id !== item.id,
                              ),
                            }))
                          }
                          tone="danger"
                        >
                          Remove
                        </MiniButton>
                      </div>
                    </div>
                  ))}
                  {draft.globalHeaders.length === 0 ? (
                    <p className="text-sm text-text-muted">
                      No global headers.
                    </p>
                  ) : null}
                </div>
              </FieldSection>
            ) : null}
            {activeConfigTab === "variables" ? (
              <FieldSection
                title="Scenario Variables"
                description="Values are ordinary non-secret Scenario defaults. Env Group variables override duplicate names during execution."
                action={
                  <MiniButton
                    onClick={() =>
                      updateDraft((current) => ({
                        ...current,
                        variables: [...current.variables, newNamedValue()],
                      }))
                    }
                    tone="primary"
                  >
                    Add variable
                  </MiniButton>
                }
              >
                <div className="space-y-2">
                  {draft.variables.map((item, index) => (
                    <div
                      className="grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-3 md:grid-cols-[1fr_1fr_auto_auto]"
                      key={item.id}
                    >
                      <label className="grid gap-1 text-xs text-text-muted">
                        Scenario variable {index + 1} name
                        <input
                          aria-label={`Scenario variable ${index + 1} name`}
                          className={textInputClass("font-mono")}
                          value={item.name}
                          onChange={(event) =>
                            updateScenarioVariable(item.id, {
                              name: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="grid gap-1 text-xs text-text-muted">
                        Scenario variable {index + 1} value
                        <input
                          aria-label={`Scenario variable ${index + 1} value`}
                          className={textInputClass("font-mono")}
                          value={item.value}
                          onChange={(event) =>
                            updateScenarioVariable(item.id, {
                              value: event.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="flex items-end gap-2 pb-2 text-xs text-text-muted">
                        <input
                          checked={item.enabled !== false}
                          onChange={(event) =>
                            updateScenarioVariable(item.id, {
                              enabled: event.target.checked,
                            })
                          }
                          type="checkbox"
                        />
                        Enabled
                      </label>
                      <div className="flex items-end">
                        <MiniButton
                          onClick={() =>
                            updateDraft((current) => ({
                              ...current,
                              variables: current.variables.filter(
                                (variable) => variable.id !== item.id,
                              ),
                            }))
                          }
                          tone="danger"
                        >
                          Remove
                        </MiniButton>
                      </div>
                    </div>
                  ))}
                  {draft.variables.length === 0 ? (
                    <p className="text-sm text-text-muted">
                      No scenario variables.
                    </p>
                  ) : null}
                </div>
              </FieldSection>
            ) : null}
            {activeConfigTab === "dataSources" ? (
              <FieldSection
                title="CSV Data Sources"
                description="Attach CSV files from Dependency Files for variables used by Steps."
                action={
                  <MiniButton
                    onClick={() =>
                      updateDraft((current) => ({
                        ...current,
                        dataSources: [...current.dataSources, newDataSource()],
                      }))
                    }
                    tone="primary"
                  >
                    Add CSV data source
                  </MiniButton>
                }
              >
                <div className="space-y-3">
                  {draft.dataSources.map((item, index) => (
                    <div
                      className="space-y-3 rounded-xl border border-white/10 bg-white/[0.03] p-3"
                      key={item.id}
                    >
                      <div className="grid gap-3 lg:grid-cols-[1.5fr_1fr_0.7fr_auto]">
                        <label className="grid gap-1 text-xs text-text-muted">
                          Data source {index + 1} dependency file
                          <select
                            aria-label={`Data source ${index + 1} dependency file`}
                            className={textInputClass()}
                            value={item.dependencyFileId}
                            onChange={(event) => {
                              const file =
                                dependencyFilesQuery.data?.items.find(
                                  (candidate) =>
                                    candidate.id === event.target.value,
                                );
                              updateDataSource(item.id, {
                                dependencyFileId: event.target.value,
                                displayName:
                                  item.displayName || file?.filename || "",
                              });
                            }}
                          >
                            <option value="">Select a Dependency File</option>
                            {(dependencyFilesQuery.data?.items ?? []).map(
                              (file) => (
                                <option key={file.id} value={file.id}>
                                  {file.filename}
                                </option>
                              ),
                            )}
                          </select>
                        </label>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Data source {index + 1} display name
                          <input
                            aria-label={`Data source ${index + 1} display name`}
                            className={textInputClass()}
                            value={item.displayName}
                            onChange={(event) =>
                              updateDataSource(item.id, {
                                displayName: event.target.value,
                              })
                            }
                          />
                        </label>
                        <label className="grid gap-1 text-xs text-text-muted">
                          Delimiter
                          <input
                            aria-label={`Data source ${index + 1} delimiter`}
                            className={textInputClass("font-mono")}
                            value={item.delimiter ?? ""}
                            onChange={(event) =>
                              updateDataSource(item.id, {
                                delimiter: event.target.value || null,
                              })
                            }
                          />
                        </label>
                        <div className="flex items-end">
                          <MiniButton
                            onClick={() =>
                              updateDraft((current) => ({
                                ...current,
                                dataSources: current.dataSources.filter(
                                  (currentItem) => currentItem.id !== item.id,
                                ),
                              }))
                            }
                            tone="danger"
                          >
                            Remove
                          </MiniButton>
                        </div>
                      </div>
                      <label className="grid gap-1 text-xs text-text-muted">
                        Data source {index + 1} variable names
                        <input
                          aria-label={`Data source ${index + 1} variable names`}
                          className={textInputClass("font-mono")}
                          placeholder="user_id, token"
                          value={
                            dataSourceVariableTextById[item.id] ??
                            (item.variableNames ?? []).join(", ")
                          }
                          onChange={(event) => {
                            setDataSourceVariableTextById((current) => ({
                              ...current,
                              [item.id]: event.target.value,
                            }));
                            updateDataSource(item.id, {
                              variableNames: parseCsvNames(event.target.value),
                            });
                          }}
                        />
                      </label>
                      <div className="flex flex-wrap gap-4 text-xs text-text-muted">
                        <label className="flex items-center gap-2">
                          <input
                            checked={item.enabled !== false}
                            onChange={(event) =>
                              updateDataSource(item.id, {
                                enabled: event.target.checked,
                              })
                            }
                            type="checkbox"
                          />
                          Enabled
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            checked={item.loop}
                            onChange={(event) =>
                              updateDataSource(item.id, {
                                loop: event.target.checked,
                              })
                            }
                            type="checkbox"
                          />
                          Loop
                        </label>
                        <label className="flex items-center gap-2">
                          <input
                            checked={item.randomOrder}
                            onChange={(event) =>
                              updateDataSource(item.id, {
                                randomOrder: event.target.checked,
                              })
                            }
                            type="checkbox"
                          />
                          Random order
                        </label>
                        <label className="flex items-center gap-2">
                          Quoted
                          <select
                            aria-label={`Data source ${index + 1} quoted`}
                            className="rounded-lg border border-white/10 bg-black/20 px-2 py-1 text-white"
                            value={
                              item.quoted === null ? "" : String(item.quoted)
                            }
                            onChange={(event) =>
                              updateDataSource(item.id, {
                                quoted: parseBooleanOverride(
                                  event.target.value,
                                ),
                              })
                            }
                          >
                            <option value="">Auto</option>
                            <option value="true">Yes</option>
                            <option value="false">No</option>
                          </select>
                        </label>
                      </div>
                    </div>
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
        </div>
      ) : null}
      {showDebug ? (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md border-l border-white/10 bg-surface-container-low p-6 shadow-2xl">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Debug Run</h2>
              <p className="mt-1 text-sm text-text-muted">
                1 virtual user · 1 iteration
              </p>
            </div>
            <button
              className="text-text-muted"
              onClick={() => setShowDebug(false)}
              type="button"
            >
              Close
            </button>
          </div>
          <div className="mt-6 space-y-4">
            <div className="rounded-2xl border border-white/10 p-4">
              <p className="text-sm text-text-muted">Environment</p>
              <p className="mt-1 text-white">{selectedEnvName}</p>
              <select
                aria-label="Debug Environment"
                className="mt-3 w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                value={selectedEnvId}
                onChange={(event) => setSelectedEnvId(event.target.value)}
              >
                <option value="">No environment</option>
                {(envQuery.data?.items ?? []).map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name}
                  </option>
                ))}
              </select>
            </div>
            <label className="grid gap-1 text-sm text-text-muted">
              Load Node
              <select
                className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                value={selectedNodeId}
                onChange={(e) => setSelectedNodeId(e.target.value)}
              >
                <option value="">Select an idle node</option>
                {(nodeQuery.data?.items ?? []).map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.host}
                  </option>
                ))}
              </select>
            </label>
            {nodeQuery.data?.items.length === 0 ? (
              <p className="text-sm text-warning">
                {scenarioCopy.noNodes}{" "}
                <Link className="text-primary" to="/resources/load-nodes">
                  Open Load Nodes
                </Link>
              </p>
            ) : null}
            {scriptsEnabled(draft) ? (
              <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
                This Scenario contains custom scripts.
              </p>
            ) : null}
            <button
              className="w-full rounded-xl bg-primary px-4 py-3 font-semibold text-on-primary disabled:opacity-40"
              disabled={
                !selectedNodeId ||
                debugMutation.isPending ||
                saveMutation.isPending
              }
              onClick={() => void startDebug()}
              type="button"
            >
              Start Debug Run
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
