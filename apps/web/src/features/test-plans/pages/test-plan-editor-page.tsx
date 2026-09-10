import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createRun,
  getCsrfToken,
  getTestPlan,
  listEnvGroups,
  listLoadNodes,
  listScenarios,
  patchTestPlan,
  type EnvGroupSummary,
  type LoadNodeSummary,
  type ScenarioSummary,
  type TestPlanDetail,
  type TestPlanSlaRule,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { useWorkspaceSwitchGuard } from "../../../app/workspace-switch-guard";
import { testPlanCopy } from "../copy";
import {
  canDebugSavedPlan,
  canRunDraft,
  defaultLoadSettings,
  expectedConcurrency,
  isSupportedResponseCodePattern,
  loadSettingsProblem,
  newScenarioItem,
  newSlaRule,
  needsEnabledStateMigration,
  tagText,
  tagsFromText,
  toPatchPayload,
  validateTestPlanDraft,
  type LoadSettingsProblemKey,
} from "../model";

function currentTestPlanId() {
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

function inputClass(hasError: boolean) {
  return cn(
    "h-10 w-full rounded-lg border bg-surface-container px-3 text-sm text-text-main outline-none transition focus:border-primary/50",
    hasError ? "border-error/60" : "border-white/10",
  );
}

function textInputClass(extra = "") {
  return cn(
    "w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-text-main outline-none transition focus:border-primary/50",
    extra,
  );
}

function navigateTo(path: string) {
  window.history.replaceState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function errorMessage(error: unknown) {
  const code = (error as ApiError | undefined)?.body?.code;
  if (code === "TEST_PLAN_REVISION_CONFLICT") {
    return testPlanCopy.staleRevision;
  }
  if (code === "LOAD_NODE_BUSY") {
    return testPlanCopy.nodeBusy;
  }
  if (code === "TEST_PLAN_NOT_RUNNABLE") {
    return testPlanCopy.notRunnable;
  }
  if (code === "VALIDATION_ERROR") {
    return testPlanCopy.validationError;
  }
  if (code === "RESOURCE_NOT_FOUND") {
    return "The Test Plan does not exist or is no longer visible.";
  }
  return testPlanCopy.actionFailed;
}

function isRevisionConflict(error: unknown) {
  return (
    (error as ApiError | undefined)?.body?.code ===
    "TEST_PLAN_REVISION_CONFLICT"
  );
}

function parseOptionalNumber(value: string) {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function navigateToLoadNodes() {
  window.history.replaceState({}, "", "/resources/load-nodes");
  window.dispatchEvent(new PopStateEvent("popstate"));
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

const LOAD_SETTING_LABELS: Array<[string, keyof typeof defaultLoadSettings]> =
  [
    ["Concurrency / Node", "concurrencyPerNode"],
    ["Ramp-up", "rampUpSeconds"],
    ["Hold-for", "holdForSeconds"],
    ["Iterations", "iterations"],
    ["Target RPS", "targetRps"],
    ["Steps", "steps"],
    ["Delay", "delaySeconds"],
  ];

const NULLABLE_LOAD_SETTING_KEYS = new Set([
  "holdForSeconds",
  "iterations",
  "targetRps",
  "steps",
]);

const loadProblemCopy: Record<LoadSettingsProblemKey, string> = {
  termination: "Choose hold-for or iterations for this Scenario item.",
  stepsRequireRampUp: "Steps require ramp-up for this Scenario item.",
  targetRpsRequiresHoldFor:
    "Target RPS requires hold-for for this Scenario item.",
};

const slaMetricOptions = [
  {
    value: "avg_rt",
    label: "Average response time",
    defaultCondition: "gt",
    defaultThreshold: 500,
    defaultUnit: "ms",
    units: ["ms", "s"],
  },
  {
    value: "p90",
    label: "P90 response time",
    defaultCondition: "gt",
    defaultThreshold: 500,
    defaultUnit: "ms",
    units: ["ms", "s"],
  },
  {
    value: "p95",
    label: "P95 response time",
    defaultCondition: "gt",
    defaultThreshold: 500,
    defaultUnit: "ms",
    units: ["ms", "s"],
  },
  {
    value: "p99",
    label: "P99 response time",
    defaultCondition: "gt",
    defaultThreshold: 500,
    defaultUnit: "ms",
    units: ["ms", "s"],
  },
  {
    value: "fail",
    label: "Failed requests",
    defaultCondition: "gt",
    defaultThreshold: 1,
    defaultUnit: "percent",
    units: ["percent"],
  },
  {
    value: "succ",
    label: "Successful requests",
    defaultCondition: "lt",
    defaultThreshold: 99,
    defaultUnit: "percent",
    units: ["percent"],
  },
  {
    value: "hits",
    label: "Hits",
    defaultCondition: "lt",
    defaultThreshold: 1,
    defaultUnit: "count",
    units: ["count"],
  },
  {
    value: "bytes",
    label: "Bytes",
    defaultCondition: "gt",
    defaultThreshold: 1,
    defaultUnit: "mb",
    units: ["b", "kb", "mb"],
  },
  {
    value: "rc",
    label: "Response code rate",
    defaultCondition: "gt",
    defaultThreshold: 0,
    defaultUnit: "percent",
    units: ["percent", "count"],
  },
] as const;

type SlaMetricValue = (typeof slaMetricOptions)[number]["value"];
type SlaThresholdUnit = TestPlanSlaRule["threshold"]["unit"];

const unitLabels: Record<SlaThresholdUnit, string> = {
  ms: "ms",
  s: "s",
  percent: "percent",
  count: "count",
  b: "B",
  kb: "kB",
  mb: "MB",
};

function metricValueForSubject(subject: string): SlaMetricValue {
  return subject.startsWith("rc")
    ? "rc"
    : slaMetricOptions.some((option) => option.value === subject)
      ? (subject as SlaMetricValue)
      : "p95";
}

function responseCodePattern(subject: string) {
  return subject.startsWith("rc") ? subject.slice(2) : "500";
}

function metricOption(value: SlaMetricValue) {
  return (
    slaMetricOptions.find((option) => option.value === value) ??
    slaMetricOptions[2]
  );
}

function isValidUnitForMetric(metric: SlaMetricValue, unit: SlaThresholdUnit) {
  return (metricOption(metric).units as readonly SlaThresholdUnit[]).includes(
    unit,
  );
}

function subjectForMetric(metric: SlaMetricValue, pattern = "500") {
  if (metric !== "rc") return metric;
  const normalized = pattern.trim() || "*";
  return `rc${normalized}`;
}

export function TestPlanEditorPage() {
  const { session } = useAuthSession();
  const getWriteToken = useCsrfToken();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const planId = currentTestPlanId();

  const [draft, setDraft] = useState<TestPlanDetail | null>(null);
  const [tagTextState, setTagTextState] = useState("");
  const [dirty, setDirty] = useState(false);
  const [renamingName, setRenamingName] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isReloading, setIsReloading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [needsReload, setNeedsReload] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [runningType, setRunningType] = useState<"debug" | "standard" | null>(
    null,
  );
  const [pendingConfirmation, setPendingConfirmation] = useState<
    "standard" | null
  >(null);

  const [envGroups, setEnvGroups] = useState<EnvGroupSummary[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [nodes, setNodes] = useState<LoadNodeSummary[]>([]);
  const [isLoadingNodes, setIsLoadingNodes] = useState(false);

  const fetchPlan = useMemo(
    () => async () => {
      if (!workspaceId || !planId) return;
      setIsLoading(true);
      setLoadError(null);
      try {
        const data = await getTestPlan(planId, workspaceId);
        const migrated = needsEnabledStateMigration(data);
        const normalized = normalizeDetail(data);
        setDraft(normalized);
        setTagTextState(tagText(normalized.tags));
        setDirty(migrated);
        setRenamingName(false);
        setActionError(null);
        setNeedsReload(false);
      } catch (error) {
        setLoadError(errorMessage(error));
      } finally {
        setIsLoading(false);
      }
    },
    [planId, workspaceId],
  );

  useEffect(() => {
    if (session !== null) {
      void fetchPlan();
    }
  }, [session, fetchPlan]);

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
    listScenarios({ workspaceId, pageSize: 100, sort: "name" })
      .then((data) => {
        if (active) setScenarios(data.items);
      })
      .catch(() => {
        if (active) setScenarios([]);
      });
    return () => {
      active = false;
    };
  }, [workspaceId]);

  const fetchNodes = useMemo(
    () => async () => {
      if (!workspaceId) return;
      setIsLoadingNodes(true);
      try {
        const data = await listLoadNodes({
          workspaceId,
          limit: 100,
          offset: 0,
          sort: "host",
        });
        setNodes(data.items);
      } catch {
        setNodes([]);
      } finally {
        setIsLoadingNodes(false);
      }
    },
    [workspaceId],
  );

  useEffect(() => {
    if (workspaceId) {
      void fetchNodes();
    }
  }, [workspaceId, fetchNodes]);

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
      safePath: "/test-plans",
      onAbandon: () => {
        setDirty(false);
        setActionError(null);
        setNeedsReload(false);
        setPendingConfirmation(null);
      },
    }),
    [dirty],
  );
  useWorkspaceSwitchGuard(workspaceSwitchGuard);

  function normalizeDetail(detail: TestPlanDetail): TestPlanDetail {
    return {
      ...detail,
      scenarioItems: detail.scenarioItems.map((item, index) => ({
        ...item,
        enabled: true,
        order: index,
        loadSettings: item.loadSettings ?? { ...defaultLoadSettings },
      })),
      slaRules: detail.slaRules.map((rule) => ({ ...rule, enabled: true })),
    };
  }

  function updateDraft(updater: (current: TestPlanDetail) => TestPlanDetail) {
    setDraft((current) => {
      if (!current) return current;
      return normalizeDetail(updater(current));
    });
    setDirty(true);
    setNeedsReload(false);
  }

  const validationErrors = useMemo(
    () => validateTestPlanDraft(draft),
    [draft],
  );
  const localExpectedConcurrency = expectedConcurrency(draft);
  const canSave =
    dirty && !isSaving && validationErrors.length === 0 && draft !== null;

  const draftCanDebug =
    draft !== null &&
    (dirty ? canRunDraft(draft) : canDebugSavedPlan(draft));
  const draftCanRunStandard =
    draft !== null && (dirty ? canRunDraft(draft) : draft.runnable);

  const poolType = draft?.resource.poolType ?? null;
  const resourceMode = draft?.resource.mode ?? "manual";
  const selectedNodeIds = draft?.resource.selectedNodeIds?.length
    ? draft.resource.selectedNodeIds
    : draft?.resource.selectedNodeId
      ? [draft.resource.selectedNodeId]
      : [];
  const idleCandidates = useMemo(() => {
    const pool = poolType;
    return nodes.filter((node) => {
      if (node.status !== "idle") return false;
      if (pool === "public") return node.scope === "public";
      if (pool === "private") return node.scope === "workspace";
      return false;
    });
  }, [poolType, nodes]);
  function standardResourceRequest(current: TestPlanDetail) {
    const mode = current.resource.mode ?? "manual";
    return mode === "auto"
      ? {
          mode: "auto" as const,
          nodeCount: current.resource.nodeCount ?? 1,
          concurrencyPerNode: expectedConcurrency(current) || null,
        }
      : {
          mode: "manual" as const,
          selectedNodeIds: current.resource.selectedNodeIds?.length
            ? current.resource.selectedNodeIds
            : current.resource.selectedNodeId
              ? [current.resource.selectedNodeId]
              : [],
          concurrencyPerNode: expectedConcurrency(current) || null,
        };
  }

  async function handleSave(): Promise<TestPlanDetail | null> {
    if (!draft) return null;
    if (validationErrors.length > 0) {
      setActionError(testPlanCopy.validationError);
      return null;
    }
    setIsSaving(true);
    setActionError(null);
    setNeedsReload(false);
    try {
      const token = await getWriteToken();
      const updated = await patchTestPlan(
        draft.id,
        toPatchPayload(draft),
        workspaceId,
        token,
      );
      const normalized = normalizeDetail(updated);
      setDraft(normalized);
      setTagTextState(tagText(normalized.tags));
      setDirty(false);
      setRenamingName(false);
      return normalized;
    } catch (error) {
      setActionError(errorMessage(error));
      if (isRevisionConflict(error)) {
        setNeedsReload(true);
      }
      return null;
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRun(
    runType: "debug" | "standard",
    confirmHighConcurrency = false,
  ) {
    if (!draft) return;
    if (validationErrors.length > 0) {
      setActionError(testPlanCopy.validationError);
      return;
    }
    setRunningType(runType);
    setActionError(null);
    setNeedsReload(false);
    try {
      const saved = dirty ? await handleSave() : draft;
      if (!saved) return;
      if (runType === "standard" ? !saved.runnable : !canDebugSavedPlan(saved)) {
        setActionError(testPlanCopy.notRunnable);
        return;
      }
      const token = await getWriteToken();
      const run = await createRun(
        {
          runType,
          sourceType: "test_plan",
          sourceId: saved.id,
          expectedSourceRevision: saved.revision,
          confirmHighConcurrency,
          resourceRequest:
            runType === "standard" ? standardResourceRequest(saved) : undefined,
        },
        workspaceId,
        token,
      );
      setDirty(false);
      navigateTo(`/runs/${run.id}`);
    } catch (error) {
      const code = (error as ApiError | undefined)?.body?.code;
      if (
        code === "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED" &&
        runType === "standard"
      ) {
        setPendingConfirmation("standard");
        return;
      }
      if (code === "LOAD_NODE_BUSY") {
        void fetchNodes();
      }
      setActionError(errorMessage(error));
      if (isRevisionConflict(error)) {
        setNeedsReload(true);
      }
    } finally {
      setRunningType(null);
    }
  }

  async function handleReload() {
    setIsReloading(true);
    setActionError(null);
    setNeedsReload(false);
    try {
      await fetchPlan();
    } finally {
      setIsReloading(false);
    }
  }

  function addScenario() {
    const scenario = scenarios[0];
    if (!scenario || !draft) return;
    updateDraft((current) => ({
      ...current,
      scenarioItems: [
        ...current.scenarioItems,
        newScenarioItem(scenario),
      ],
    }));
  }

  function changeScenarioItemScenario(itemId: string, scenarioId: string) {
    const scenario = scenarios.find((row) => row.id === scenarioId);
    if (!scenario) return;
    updateDraft((current) => ({
      ...current,
      scenarioItems: current.scenarioItems.map((row) =>
        row.id === itemId
          ? {
              ...row,
              scenarioId: scenario.id,
              scenarioName: scenario.name,
              scenarioRevision: scenario.revision,
              enabledStepCount: scenario.enabledStepCount,
              updatedAt: scenario.updatedAt,
            }
          : row,
      ),
    }));
  }

  function moveScenarioItem(itemId: string, direction: -1 | 1) {
    updateDraft((current) => {
      const rows = [...current.scenarioItems];
      const index = rows.findIndex((row) => row.id === itemId);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= rows.length) {
        return current;
      }
      [rows[index], rows[target]] = [rows[target], rows[index]];
      return { ...current, scenarioItems: rows };
    });
  }

  function removeScenarioItem(itemId: string) {
    updateDraft((current) => ({
      ...current,
      scenarioItems: current.scenarioItems.filter((row) => row.id !== itemId),
    }));
  }

  function updateLoadSettings(
    itemId: string,
    key: keyof typeof defaultLoadSettings,
    value: string,
  ) {
    updateDraft((current) => ({
      ...current,
      scenarioItems: current.scenarioItems.map((row) =>
        row.id === itemId
          ? {
              ...row,
              loadSettings: {
                ...(row.loadSettings ?? defaultLoadSettings),
                [key]: NULLABLE_LOAD_SETTING_KEYS.has(key)
                  ? parseOptionalNumber(value)
                  : Number(value),
              },
            }
          : row,
      ),
    }));
  }

  function addSlaRule() {
    updateDraft((current) => ({
      ...current,
      slaRules: [...current.slaRules, newSlaRule()],
    }));
  }

  function removeSlaRule(ruleId: string) {
    updateDraft((current) => ({
      ...current,
      slaRules: current.slaRules.filter((rule) => rule.id !== ruleId),
    }));
  }

  function updateSlaRule(ruleId: string, fields: Partial<TestPlanSlaRule>) {
    updateDraft((current) => ({
      ...current,
      slaRules: current.slaRules.map((rule) =>
        rule.id === ruleId ? { ...rule, ...fields } : rule,
      ),
    }));
  }

  function changeSlaMetric(rule: TestPlanSlaRule, metric: SlaMetricValue) {
    const option = metricOption(metric);
    updateSlaRule(rule.id, {
      subject: subjectForMetric(metric, responseCodePattern(rule.subject)),
      condition: option.defaultCondition,
      threshold: {
        value: option.defaultThreshold,
        unit: option.defaultUnit,
      },
    });
  }

  if (session === null) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-container-max p-8 text-sm text-text-muted">
        {testPlanCopy.loadingDetail}
      </div>
    );
  }

  if (loadError || draft === null) {
    return (
      <div className="mx-auto max-w-container-max rounded-xl border border-error/30 bg-error-container p-6">
        <p className="text-sm text-on-error-container">
          {loadError ?? testPlanCopy.detailLoadError}
        </p>
        <div className="mt-4 flex gap-3">
          <a
            className="inline-flex items-center rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
            href="/test-plans"
          >
            {testPlanCopy.backToList}
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
            <a
              className="inline-flex text-sm text-primary transition hover:brightness-110"
              href="/test-plans"
            >
              {testPlanCopy.backToList}
            </a>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              {renamingName ? (
                <input
                  aria-label={testPlanCopy.renameInputLabel}
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
                    {draft.name || testPlanCopy.untitled}
                  </h1>
                  <button
                    aria-label={testPlanCopy.rename}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 text-text-muted transition hover:border-primary/30 hover:bg-white/5 hover:text-white"
                    onClick={() => setRenamingName(true)}
                    title={testPlanCopy.rename}
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
                {dirty ? testPlanCopy.unsaved : testPlanCopy.saved}
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-text-muted">
              <span>Updated {formatDate(draft.updatedAt)}</span>
              <span>{testPlanCopy.actionsHelp}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={!canSave}
              onClick={() => void handleSave()}
              type="button"
            >
              {isSaving ? testPlanCopy.saving : testPlanCopy.save}
            </button>
            <button
              className="rounded-lg border border-primary/40 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={
                runningType !== null ||
                validationErrors.length > 0 ||
                !draftCanDebug
              }
              onClick={() => void handleRun("debug")}
              title={
                dirty
                  ? "Unsaved changes will be saved before the debug run."
                  : undefined
              }
              type="button"
            >
              {runningType === "debug"
                ? testPlanCopy.startingDebug
                : dirty
                  ? testPlanCopy.saveAndDebug
                  : testPlanCopy.debug}
            </button>
            <button
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              disabled={
                runningType !== null ||
                validationErrors.length > 0 ||
                !draftCanRunStandard
              }
              onClick={() => void handleRun("standard")}
              title={
                dirty
                  ? "Unsaved changes will be saved before the run."
                  : undefined
              }
              type="button"
            >
              {runningType === "standard"
                ? testPlanCopy.startingRun
                : dirty
                  ? testPlanCopy.saveAndRunNow
                  : testPlanCopy.runNow}
            </button>
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
        {validationErrors.length > 0 ? (
          <div className="mt-4 rounded-xl border border-warning/30 bg-warning-container px-4 py-3 text-sm text-on-warning-container">
            {validationErrors.join(" ")}
          </div>
        ) : null}
      </section>

      <FieldSection
        title={testPlanCopy.basicInfo}
        description="Name, description, tags, revision and save status."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Test Plan name">
            <input
              aria-label="Test Plan name"
              className={textInputClass()}
              onChange={(event) =>
                updateDraft((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
              value={draft.name}
            />
          </Field>
          <Field label="Tags">
            <input
              aria-label="Tags"
              className={textInputClass("font-mono")}
              onChange={(event) => {
                setTagTextState(event.target.value);
                updateDraft((current) => ({
                  ...current,
                  tags: tagsFromText(event.target.value),
                }));
              }}
              placeholder={testPlanCopy.tagsPlaceholder}
              value={tagTextState}
            />
          </Field>
          <Field label="Description">
            <textarea
              aria-label="Description"
              className={cn(textInputClass(), "min-h-20 resize-y")}
              onChange={(event) =>
                updateDraft((current) => ({
                  ...current,
                  description: event.target.value || null,
                }))
              }
              value={draft.description ?? ""}
            />
          </Field>
        </div>
      </FieldSection>

      <div className="grid items-start gap-5 xl:grid-cols-2">
        <FieldSection title={testPlanCopy.globalContext}>
          <div className="space-y-4">
            <Field label="Env Group">
              <select
                aria-label="Env Group"
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    envGroupId: event.target.value || null,
                  }))
                }
                value={draft.envGroupId ?? ""}
              >
                <option value="">{testPlanCopy.noEnvironment}</option>
                {envGroups.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Run Mode">
              <select
                aria-label="Run Mode"
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    runMode: event.target.value as TestPlanDetail["runMode"],
                  }))
                }
                value={draft.runMode}
              >
                <option value="sequential">Sequential</option>
                <option value="parallel">Parallel</option>
              </select>
            </Field>
            <p className="text-xs leading-5 text-text-muted">
              Parallel mode sums per-item concurrency; sequential mode uses the
              highest per-item concurrency as the single-node expectation.
            </p>
          </div>
        </FieldSection>

        <FieldSection title={testPlanCopy.resourceConfiguration}>
          <div className="space-y-4">
            <div className="rounded-xl border border-white/10 bg-black/10 px-4 py-3">
              <p className="text-sm text-text-muted">
                {testPlanCopy.expectedConcurrency(
                  localExpectedConcurrency,
                  draft.runGuard.softConcurrencyPerNodeLimit,
                )}
              </p>
              <p className="mt-1 font-mono text-[11px] text-text-muted">
                Hard limit{" "}
                {draft.runGuard.hardConcurrencyPerNodeLimit} · Debug always
                uses a fixed low-risk profile.
              </p>
            </div>
            <Field label="Resource Mode">
              <select
                aria-label="Resource Mode"
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    resource: {
                      ...current.resource,
                      mode: event.target.value as "manual" | "auto",
                      selectedNodeId: null,
                      selectedNodeIds: [],
                      nodeCount:
                        event.target.value === "auto"
                          ? current.resource.nodeCount ?? 2
                          : null,
                    },
                  }))
                }
                value={resourceMode}
              >
                <option value="manual">Manual selected nodes</option>
                <option value="auto">Auto node count</option>
              </select>
            </Field>
            <Field label="Pool Type">
              <select
                aria-label="Pool Type"
                className={cn(inputClass(false), "text-text-main")}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    resource: {
                      ...current.resource,
                      poolType:
                        (event.target.value as "public" | "private" | "") ||
                        null,
                      selectedNodeId: null,
                      selectedNodeIds: [],
                    },
                  }))
                }
                value={poolType ?? ""}
              >
                <option value="">{testPlanCopy.selectPool}</option>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </select>
            </Field>
            {poolType && resourceMode === "auto" ? (
              <Field label="Node Count">
                <input
                  aria-label="Node Count"
                  className={textInputClass()}
                  min={1}
                  max={10}
                  onChange={(event) =>
                    updateDraft((current) => ({
                      ...current,
                      resource: {
                        ...current.resource,
                        nodeCount: Math.max(1, Number(event.target.value) || 1),
                        selectedNodeId: null,
                        selectedNodeIds: [],
                      },
                    }))
                  }
                  type="number"
                  value={draft.resource.nodeCount ?? 2}
                />
                <small>SurgePilot allocates this many idle nodes.</small>
              </Field>
            ) : null}
            {poolType && resourceMode === "manual" ? (
              <Field label="Load Node">
                <select
                  aria-label="Load Nodes"
                  className={cn(inputClass(false), "text-text-main")}
                  multiple
                  onChange={(event) => {
                    const next = Array.from(event.target.selectedOptions).map(
                      (option) => option.value,
                    );
                    updateDraft((current) => ({
                      ...current,
                      resource: {
                        ...current.resource,
                        selectedNodeIds: next,
                        selectedNodeId: next[0] ?? null,
                      },
                    }));
                  }}
                  value={selectedNodeIds}
                >
                  {idleCandidates.map((node) => (
                    <option key={node.id} value={node.id}>
                      {testPlanCopy.nodeOption(node.host, node.status)}
                    </option>
                  ))}
                </select>
                <small>Hold Ctrl/⌘ to select multiple idle nodes.</small>
              </Field>
            ) : null}
            {isLoadingNodes ? (
              <p className="text-xs text-text-muted">
                Loading Load Nodes...
              </p>
            ) : null}
            {poolType && !isLoadingNodes && idleCandidates.length === 0 ? (
              <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
                {testPlanCopy.noNodes}{" "}
                <button
                  className="font-semibold text-primary underline"
                  onClick={navigateToLoadNodes}
                  type="button"
                >
                  Open Load Nodes
                </button>
              </p>
            ) : null}
          </div>
        </FieldSection>
      </div>

      <FieldSection
        title={testPlanCopy.scenarioOrchestration}
        description={testPlanCopy.scenarioOrchestrationHelp}
        action={
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={scenarios.length === 0}
            onClick={addScenario}
            type="button"
          >
            <Plus className="h-3.5 w-3.5" />
            {testPlanCopy.addScenario}
          </button>
        }
      >
        {scenarios.length === 0 ? (
          <p className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
            {testPlanCopy.noScenarios}{" "}
            <a
              className="font-semibold text-primary underline"
              href="/scenarios"
            >
              Open Scenarios
            </a>
          </p>
        ) : null}
        <div className="space-y-3">
          {draft.scenarioItems.map((item, index) => {
            const settings = item.loadSettings ?? defaultLoadSettings;
            const problem = loadSettingsProblem(item);
            return (
              <div
                className={cn(
                  "rounded-xl border p-3",
                  problem
                    ? "border-error/40 bg-error-container/10"
                    : "border-white/10 bg-black/10",
                )}
                key={item.id}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-[240px] flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="font-mono text-xs text-secondary">
                        Scenario {index + 1}
                      </span>
                      <select
                        aria-label="Scenario name"
                        className="min-w-[220px] rounded-lg border border-white/10 bg-surface-container px-2 py-1.5 text-sm text-text-main outline-none focus:border-primary/50"
                        onChange={(event) =>
                          changeScenarioItemScenario(item.id, event.target.value)
                        }
                        value={item.scenarioId}
                      >
                        {scenarios.map((scenario) => (
                          <option key={scenario.id} value={scenario.id}>
                            {scenario.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <p className="mt-1.5 font-mono text-[11px] text-text-muted">
                      {item.scenarioName ?? "Scenario"} · revision{" "}
                      {item.scenarioRevision ?? "–"} ·{" "}
                      {item.enabledStepCount ?? 0} enabled steps · updated{" "}
                      {item.updatedAt ? formatDate(item.updatedAt) : "–"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <MiniButton
                      disabled={index === 0}
                      onClick={() => moveScenarioItem(item.id, -1)}
                    >
                      ↑ Up
                    </MiniButton>
                    <MiniButton
                      disabled={index === draft.scenarioItems.length - 1}
                      onClick={() => moveScenarioItem(item.id, 1)}
                    >
                      ↓ Down
                    </MiniButton>
                    <MiniButton
                      onClick={() => removeScenarioItem(item.id)}
                      tone="danger"
                    >
                      Remove
                    </MiniButton>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-7">
                  {LOAD_SETTING_LABELS.map(([label, key]) => (
                    <label
                      className="grid gap-1 text-xs text-text-muted"
                      key={key}
                    >
                      {label}
                      <input
                        aria-label={`${label} ${index + 1}`}
                        className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 text-sm text-text-main outline-none focus:border-primary/50"
                        min="0"
                        type="number"
                        value={String(settings[key] ?? "")}
                        onChange={(event) =>
                          updateLoadSettings(item.id, key, event.target.value)
                        }
                      />
                    </label>
                  ))}
                </div>
                {problem ? (
                  <p className="mt-2 text-xs text-error">
                    {loadProblemCopy[problem]}
                  </p>
                ) : null}
              </div>
            );
          })}
          {draft.scenarioItems.length === 0 ? (
            <p className="rounded-xl border border-dashed border-white/10 p-5 text-sm text-text-muted">
              {testPlanCopy.noScenarioItems}
            </p>
          ) : null}
        </div>
      </FieldSection>

      <FieldSection
        title={testPlanCopy.slaRules}
        description={testPlanCopy.slaRulesHelp}
        action={
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={draft.slaRules.length >= 5}
            onClick={addSlaRule}
            type="button"
          >
            <Plus className="h-3.5 w-3.5" />
            {testPlanCopy.addRule}
          </button>
        }
      >
        <div className="space-y-3">
          {draft.slaRules.map((rule, index) => {
            const metric = metricValueForSubject(rule.subject);
            const option = metricOption(metric);
            const unitOptions = option.units as readonly SlaThresholdUnit[];
            const pattern = responseCodePattern(rule.subject);
            const patternValid = isSupportedResponseCodePattern(pattern);
            return (
              <div
                className="rounded-xl border border-white/10 bg-black/10 p-3"
                key={rule.id}
              >
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-mono text-xs text-secondary">
                    Rule {index + 1}
                  </span>
                  <div className="ml-auto flex items-center gap-2">
                    <MiniButton
                      onClick={() => removeSlaRule(rule.id)}
                      tone="danger"
                    >
                      Remove
                    </MiniButton>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-[1.2fr_1fr_0.8fr_0.8fr_1fr]">
                  <label className="grid gap-1 text-xs text-text-muted">
                    Fail when metric
                    <select
                      aria-label="SLA metric"
                      className={cn(inputClass(false), "text-text-main")}
                      onChange={(event) =>
                        changeSlaMetric(
                          rule,
                          event.target.value as SlaMetricValue,
                        )
                      }
                      value={metric}
                    >
                      {slaMetricOptions.map((metricOptionItem) => (
                        <option
                          key={metricOptionItem.value}
                          value={metricOptionItem.value}
                        >
                          {metricOptionItem.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-xs text-text-muted">
                    Condition
                    <select
                      aria-label="SLA condition"
                      className={cn(inputClass(false), "text-text-main")}
                      onChange={(event) =>
                        updateSlaRule(rule.id, {
                          condition: event.target
                            .value as TestPlanSlaRule["condition"],
                        })
                      }
                      value={rule.condition}
                    >
                      <option value="gt">Greater than</option>
                      <option value="gte">At least</option>
                      <option value="lt">Less than</option>
                      <option value="lte">At most</option>
                      <option value="eq">Equals</option>
                    </select>
                  </label>
                  <label className="grid gap-1 text-xs text-text-muted">
                    Threshold
                    <input
                      aria-label="SLA threshold"
                      className="rounded-lg border border-white/10 bg-black/20 px-2 py-2 text-sm text-text-main outline-none focus:border-primary/50"
                      min="0"
                      type="number"
                      value={rule.threshold.value}
                      onChange={(event) =>
                        updateSlaRule(rule.id, {
                          threshold: {
                            ...rule.threshold,
                            value: Number(event.target.value),
                          },
                        })
                      }
                    />
                  </label>
                  <label className="grid gap-1 text-xs text-text-muted">
                    Unit
                    <select
                      aria-label="SLA unit"
                      className={cn(inputClass(false), "text-text-main")}
                      onChange={(event) =>
                        updateSlaRule(rule.id, {
                          threshold: {
                            ...rule.threshold,
                            unit: event.target
                              .value as TestPlanSlaRule["threshold"]["unit"],
                          },
                        })
                      }
                      value={
                        isValidUnitForMetric(metric, rule.threshold.unit)
                          ? rule.threshold.unit
                          : option.defaultUnit
                      }
                    >
                      {unitOptions.map((unit) => (
                        <option key={unit} value={unit}>
                          {unitLabels[unit]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1 text-xs text-text-muted">
                    Action
                    <select
                      aria-label="SLA action"
                      className={cn(inputClass(false), "text-text-main")}
                      onChange={(event) =>
                        updateSlaRule(rule.id, {
                          action: event.target
                            .value as TestPlanSlaRule["action"],
                        })
                      }
                      value={rule.action}
                    >
                      <option value="continue">Continue</option>
                      <option value="stop">Stop</option>
                    </select>
                  </label>
                </div>
                {metric === "rc" ? (
                  <div className="mt-3 grid max-w-xs gap-1 text-xs text-text-muted">
                    Response code pattern
                    <input
                      aria-label="Response code pattern"
                      className={cn(
                        "rounded-lg border bg-black/20 px-2 py-1.5 font-mono text-sm text-text-main outline-none focus:border-primary/50",
                        patternValid
                          ? "border-white/10"
                          : "border-error/60",
                      )}
                      onChange={(event) =>
                        updateSlaRule(rule.id, {
                          subject: subjectForMetric("rc", event.target.value),
                        })
                      }
                      value={pattern}
                    />
                    <span className="text-[11px] text-text-muted">
                      Use 500, 4??, or *.
                    </span>
                  </div>
                ) : null}
              </div>
            );
          })}
          {draft.slaRules.length === 0 ? (
            <p className="rounded-xl border border-dashed border-white/10 p-5 text-sm text-text-muted">
              {testPlanCopy.noSlaRules}
            </p>
          ) : null}
        </div>
      </FieldSection>

      {pendingConfirmation ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div
            aria-label={testPlanCopy.highConcurrencyTitle}
            aria-modal="true"
            className="w-full max-w-md rounded-2xl border border-warning/30 bg-surface-container-low p-6 shadow-2xl"
            role="dialog"
          >
            <h2 className="text-xl font-semibold text-white">
              {testPlanCopy.highConcurrencyTitle}
            </h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              {testPlanCopy.highConcurrencyBody}
            </p>
            <p className="mt-3 font-mono text-xs text-warning">
              {testPlanCopy.highConcurrencyMeta(
                localExpectedConcurrency,
                draft.runGuard.softConcurrencyPerNodeLimit,
              )}
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm text-text-main transition hover:bg-white/5"
                onClick={() => setPendingConfirmation(null)}
                type="button"
              >
                {testPlanCopy.cancel}
              </button>
              <button
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary transition hover:brightness-110"
                onClick={() => {
                  setPendingConfirmation(null);
                  void handleRun("standard", true);
                }}
                type="button"
              >
                {testPlanCopy.confirmAndRun}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
