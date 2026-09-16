import { useMutation, useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Pencil } from "lucide-react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createRun,
  getCsrfToken,
  getTestPlanExecutionPreview,
  getTestPlan,
  listEnvGroups,
  listLoadNodes,
  listScenarios,
  patchTestPlan,
  type ApiError,
  type ExecutionPreviewResponse,
  type RunResourceRequest,
  type TestPlanDetail,
  type TestPlanScenarioItem,
  type TestPlanSlaRule,
} from "../../../app/api-client";
import { useAuthSession } from "../../../app/auth-session";
import { useWorkspaceSwitchGuard } from "../../../app/workspace-switch-guard";
import { IconActionButton } from "../../../components/icon-action";
import {
  canDebugSavedPlan,
  canRunDraft,
  defaultLoadSettings,
  expectedConcurrency,
  isSupportedResponseCodePattern,
  needsEnabledStateMigration,
  newScenarioItem,
  newSlaRule,
  tagText as formatTagText,
  tagsFromText,
  toPatchPayload,
  validateTestPlanDraft,
} from "../model";
import { testPlanCopy } from "../copy";

function useWriteToken() {
  const { csrfToken } = useAuthSession();
  return async () => csrfToken ?? (await getCsrfToken()).csrfToken;
}

function errorMessage(error: unknown) {
  const body = (error as ApiError | undefined)?.body;
  if (body?.code === "TEST_PLAN_REVISION_CONFLICT")
    return testPlanCopy.staleRevision;
  if (body?.code === "LOAD_NODE_BUSY") return testPlanCopy.nodeBusy;
  if (body?.code === "TEST_PLAN_NOT_RUNNABLE") return testPlanCopy.notRunnable;
  if (body?.code === "VALIDATION_ERROR") return testPlanCopy.validationError;
  return testPlanCopy.actionFailed;
}

function previewErrorMessage(error: unknown, detail: TestPlanDetail | null) {
  const body = (error as ApiError | undefined)?.body;
  if (
    body?.code === "TEST_PLAN_NOT_RUNNABLE" &&
    detail?.notRunnableReasons.includes("load_node_required")
  ) {
    return testPlanCopy.previewLoadNodeRequired;
  }
  if (body?.code === "TEST_PLAN_NOT_RUNNABLE") {
    return testPlanCopy.previewNotRunnable;
  }
  return testPlanCopy.previewFailed;
}

function sectionClass() {
  return "rounded-2xl border border-white/10 bg-black/10 p-4";
}

function miniButton(tone: "neutral" | "primary" | "danger" = "neutral") {
  if (tone === "primary")
    return "rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs text-primary disabled:opacity-40";
  if (tone === "danger")
    return "rounded-lg border border-error/30 px-3 py-1.5 text-xs text-error disabled:opacity-40";
  return "rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white disabled:opacity-40";
}

function helpDisclosure(label: string, body: string) {
  return (
    <details className="group relative inline-block text-left">
      <summary
        aria-label={label}
        className="grid h-6 w-6 cursor-pointer list-none place-items-center rounded-full border border-white/10 bg-white/5 text-xs font-semibold text-secondary transition hover:border-primary/40 hover:text-primary [&::-webkit-details-marker]:hidden"
      >
        ?
      </summary>
      <div className="absolute right-0 z-20 mt-2 w-72 rounded-xl border border-white/10 bg-surface-container p-3 text-xs leading-5 text-text-muted shadow-2xl">
        {body}
      </div>
    </details>
  );
}

function parseOptionalNumber(value: string) {
  if (value.trim() === "") return null;
  return Number(value);
}

function standardResourceRequest(
  detail: TestPlanDetail,
  nonIdleNodeIds: ReadonlySet<string> = new Set(),
): RunResourceRequest | undefined {
  const mode = detail.resource.mode ?? "manual";
  const concurrencyPerNode = expectedConcurrency(detail) || undefined;
  if (mode === "auto") {
    return {
      mode: "auto",
      nodeCount: detail.resource.nodeCount ?? 1,
      concurrencyPerNode,
    };
  }
  const selectedNodeIds =
    detail.resource.selectedNodeIds && detail.resource.selectedNodeIds.length
      ? detail.resource.selectedNodeIds
      : detail.resource.selectedNodeId
        ? [detail.resource.selectedNodeId]
        : [];
  return {
    mode: "manual",
    selectedNodeIds: selectedNodeIds.filter(
      (nodeId) => !nonIdleNodeIds.has(nodeId),
    ),
    concurrencyPerNode,
  };
}

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

export function TestPlanEditorPage() {
  const { planId = "" } = useParams();
  const navigate = useNavigate();
  const { session } = useAuthSession();
  const workspaceId = session?.defaultWorkspace.id ?? "";
  const getWriteToken = useWriteToken();
  const [draft, setDraft] = useState<TestPlanDetail | null>(null);
  const [tagText, setTagText] = useState("");
  const [dirty, setDirty] = useState(false);
  const [renamingName, setRenamingName] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [previewRunType, setPreviewRunType] = useState<"debug" | "standard">(
    "debug",
  );
  const [executionPreview, setExecutionPreview] =
    useState<ExecutionPreviewResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<
    "standard" | "debug" | null
  >(null);
  const [nodePickerOpen, setNodePickerOpen] = useState(false);
  const bypassNavigationBlockRef = useRef(false);
  const dirtyRef = useRef(false);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty &&
      !bypassNavigationBlockRef.current &&
      currentLocation.pathname !== nextLocation.pathname,
  );
  const workspaceSwitchGuard = useMemo(
    () => ({
      dirty,
      safePath: "/test-plans",
      onAbandon: () => {
        bypassNavigationBlockRef.current = true;
        setDirty(false);
        setError(null);
        setRunError(null);
        setPendingConfirmation(null);
      },
    }),
    [dirty],
  );
  useWorkspaceSwitchGuard(workspaceSwitchGuard);
  useEffect(() => {
    if (blocker.state === "blocked") {
      if (window.confirm(testPlanCopy.unsavedPrompt)) {
        bypassNavigationBlockRef.current = true;
        blocker.proceed();
      } else {
        blocker.reset();
      }
    }
  }, [blocker]);

  const planQuery = useQuery({
    enabled: Boolean(workspaceId && planId),
    queryKey: ["test-plan", workspaceId, planId],
    queryFn: () => getTestPlan(planId, workspaceId),
    retry: false,
  });
  const envQuery = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["env-groups", workspaceId, "test-plan-editor"],
    queryFn: () => listEnvGroups({ workspaceId, pageSize: 100, sort: "name" }),
  });
  const scenarioQuery = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["scenarios", workspaceId, "test-plan-picker"],
    queryFn: () => listScenarios({ workspaceId, pageSize: 100, sort: "name" }),
  });
  const nodeQuery = useQuery({
    enabled: Boolean(workspaceId),
    queryKey: ["load-nodes", workspaceId, "test-plan-idle"],
    queryFn: () =>
      listLoadNodes({
        workspaceId,
        status: "idle",
        limit: 100,
        offset: 0,
        sort: "host",
      }),
  });
  const nonIdleNodeIds = useMemo(
    () =>
      new Set(
        nodeQuery.data?.items
          .filter((node) => node.status !== "idle")
          .map((node) => node.id) ?? [],
      ),
    [nodeQuery.data?.items],
  );
  const manualNodeCandidates = useMemo(() => {
    const poolType = draft?.resource.poolType;
    return (
      nodeQuery.data?.items.filter((node) => {
        if (node.status !== "idle") return false;
        if (poolType === "public") return node.scope === "public";
        if (poolType === "private") return node.scope === "workspace";
        return true;
      }) ?? []
    );
  }, [draft?.resource.poolType, nodeQuery.data?.items]);
  const selectedManualNodeIds = useMemo(() => {
    if (!draft) return [];
    return draft.resource.selectedNodeIds?.length
      ? draft.resource.selectedNodeIds
      : draft.resource.selectedNodeId
        ? [draft.resource.selectedNodeId]
        : [];
  }, [draft]);
  const selectedManualNodeCount = selectedManualNodeIds.length;

  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  useEffect(() => {
    if (planQuery.data) {
      if (dirtyRef.current) return;
      const next = normalizeDetail(planQuery.data);
      setDraft(next);
      setTagText(formatTagText(next.tags));
      setDirty(needsEnabledStateMigration(planQuery.data));
      setRenamingName(false);
      setError(null);
      setRunError(null);
      setExecutionPreview(null);
      setPreviewError(null);
    }
  }, [planQuery.data]);
  const updateDraft = (
    updater: (current: TestPlanDetail) => TestPlanDetail,
  ) => {
    setDraft((current) => {
      if (!current) return current;
      const next = updater(current);
      return normalizeDetail(next);
    });
    setDirty(true);
    clearExecutionPreview();
  };
  function clearExecutionPreview() {
    setExecutionPreview(null);
    setPreviewError(null);
  }

  const saveMutation = useMutation({
    mutationFn: async (next: TestPlanDetail) =>
      patchTestPlan(
        planId,
        toPatchPayload(next),
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (updated) => {
      const normalized = normalizeDetail(updated);
      setDraft(normalized);
      setTagText(formatTagText(normalized.tags));
      setDirty(false);
      setRenamingName(false);
      setError(null);
      clearExecutionPreview();
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const runMutation = useMutation({
    mutationFn: async ({
      next,
      runType,
      confirmHighConcurrency,
    }: {
      next: TestPlanDetail;
      runType: "standard" | "debug";
      confirmHighConcurrency: boolean;
    }) =>
      createRun(
        {
          runType,
          sourceType: "test_plan",
          sourceId: next.id,
          expectedSourceRevision: next.revision,
          confirmHighConcurrency,
          resourceRequest:
            runType === "standard"
              ? standardResourceRequest(next, nonIdleNodeIds)
              : undefined,
        },
        workspaceId,
        await getWriteToken(),
      ),
    onSuccess: (run) => {
      bypassNavigationBlockRef.current = true;
      navigate(`/runs/${run.id}`);
    },
    onError: (err, variables) => {
      const apiError = err as ApiError;
      if (
        apiError.body?.code === "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED" &&
        variables.runType === "standard"
      ) {
        setPendingConfirmation("standard");
        return;
      }
      if (apiError.body?.code === "LOAD_NODE_BUSY") void nodeQuery.refetch();
      setRunError(errorMessage(err));
    },
  });
  const previewMutation = useMutation({
    mutationFn: async () =>
      getTestPlanExecutionPreview({
        testPlanId: planId,
        workspaceId,
        runType: previewRunType,
      }),
    onSuccess: (preview) => {
      setExecutionPreview(preview);
      setPreviewError(null);
    },
    onError: (error) => {
      setExecutionPreview(null);
      setPreviewError(previewErrorMessage(error, draft));
    },
  });

  const saveCurrent = async () => {
    if (!draft) return null;
    if (validationErrors.length > 0) return null;
    if (!dirty) return draft;
    return normalizeDetail(await saveMutation.mutateAsync(draft));
  };
  const saveDraft = () => {
    if (!draft) return;
    if (validationErrors.length > 0) return;
    saveMutation.mutate(draft);
  };

  const runWith = async (
    runType: "standard" | "debug",
    confirmHighConcurrency = false,
  ) => {
    try {
      const saved = await saveCurrent();
      if (!saved) return;
      if (
        runType === "standard" ? !saved.runnable : !canDebugSavedPlan(saved)
      ) {
        setRunError(testPlanCopy.notRunnable);
        return;
      }
      await runMutation.mutateAsync({
        next: saved,
        runType,
        confirmHighConcurrency,
      });
    } catch {
      // React Query onError handlers surface actionable feedback; event handlers must not leak rejected promises.
    }
  };

  const validationErrors = useMemo(() => validateTestPlanDraft(draft), [draft]);
  const draftCanDebug = draft
    ? dirty
      ? canRunDraft(draft)
      : canDebugSavedPlan(draft)
    : false;
  const draftCanRunStandard = draft
    ? dirty
      ? canRunDraft(draft)
      : draft.runnable
    : false;
  const localExpectedConcurrency = expectedConcurrency(draft);
  if (planQuery.isError) {
    return (
      <div className="rounded-2xl border border-error/30 bg-error-container p-8 text-on-error-container">
        {testPlanCopy.detailLoadError}
      </div>
    );
  }
  if (planQuery.isLoading || draft === null) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-8 text-text-muted">
        {testPlanCopy.loadingDetail}
      </div>
    );
  }

  return (
    <section className="mx-auto max-w-7xl space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link className="text-sm text-primary" to="/test-plans">
            {testPlanCopy.backToList}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            {renamingName ? (
              <input
                aria-label={testPlanCopy.renameInputLabel}
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
                  {draft.name || testPlanCopy.untitled}
                </h1>
                <IconActionButton
                  Icon={Pencil}
                  label={testPlanCopy.rename}
                  onClick={() => setRenamingName(true)}
                />
              </>
            )}
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {testPlanCopy.revisionStatus(draft.revision, dirty)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-xl border border-white/10 px-4 py-2 text-white disabled:opacity-40"
            disabled={
              !dirty || saveMutation.isPending || validationErrors.length > 0
            }
            onClick={saveDraft}
            type="button"
          >
            {testPlanCopy.save}
          </button>
          <button
            className="rounded-xl border border-primary/40 bg-primary/10 px-4 py-2 font-semibold text-primary disabled:opacity-40"
            disabled={
              runMutation.isPending ||
              saveMutation.isPending ||
              validationErrors.length > 0 ||
              !draftCanDebug
            }
            onClick={() => void runWith("debug")}
            type="button"
          >
            {dirty ? testPlanCopy.saveAndDebug : testPlanCopy.debug}
          </button>
          <button
            className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary disabled:opacity-40"
            disabled={
              runMutation.isPending ||
              saveMutation.isPending ||
              validationErrors.length > 0 ||
              !draftCanRunStandard
            }
            onClick={() => void runWith("standard")}
            type="button"
          >
            {dirty ? testPlanCopy.saveAndRunNow : testPlanCopy.runNow}
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
          {error}
        </div>
      ) : null}
      {runError ? (
        <div className="rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
          {runError}
        </div>
      ) : null}
      {validationErrors.length ? (
        <div className="rounded-xl border border-warning/30 bg-warning-container p-3 text-sm text-on-warning-container">
          {validationErrors.join(" ")}
        </div>
      ) : null}

      <section className={sectionClass()}>
        <h2 className="text-lg font-semibold text-white">
          {testPlanCopy.basicInfo}
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="grid gap-1 text-sm text-text-muted">
            Test Plan name
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={draft.name}
              onChange={(event) =>
                updateDraft((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
            />
          </label>
          <label className="grid gap-1 text-sm text-text-muted">
            Tags
            <input
              className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={tagText}
              onChange={(event) => {
                setTagText(event.target.value);
                updateDraft((current) => ({
                  ...current,
                  tags: tagsFromText(event.target.value),
                }));
              }}
            />
          </label>
          <label className="grid gap-1 text-sm text-text-muted md:col-span-2">
            Description
            <textarea
              className="min-h-20 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
              value={draft.description ?? ""}
              onChange={(event) =>
                updateDraft((current) => ({
                  ...current,
                  description: event.target.value || null,
                }))
              }
            />
          </label>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <section className={sectionClass()}>
          <h2 className="text-lg font-semibold text-white">
            {testPlanCopy.globalContext}
          </h2>
          <div className="mt-4 grid gap-4">
            <label className="grid gap-1 text-sm text-text-muted">
              Env Group
              <select
                className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
                value={draft.envGroupId ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    envGroupId: event.target.value || null,
                  }))
                }
              >
                <option value="">No environment</option>
                {envQuery.data?.items.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-sm text-text-muted">
              Run Mode
              <select
                className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
                value={draft.runMode}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    runMode: event.target.value as TestPlanDetail["runMode"],
                  }))
                }
              >
                <option value="sequential">Sequential</option>
                <option value="parallel">Parallel</option>
              </select>
            </label>
          </div>
        </section>

        <section className={sectionClass()}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-white">
                {testPlanCopy.resourceConfiguration}
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                {testPlanCopy.expectedConcurrencyLabel}: {""}
                <span className="font-mono text-primary">
                  {localExpectedConcurrency}
                </span>{" "}
                (soft limit {draft.runGuard.softConcurrencyPerNodeLimit})
              </p>
            </div>
            {helpDisclosure(
              "Resource configuration help",
              "Standard Runs can use multiple nodes. Debug stays single-node. Pool Type limits which idle Load Nodes appear in the picker.",
            )}
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <fieldset className="grid gap-2 text-sm text-text-muted">
              <legend className="text-sm text-text-muted">Resource Mode</legend>
              <div className="grid gap-2 rounded-xl border border-white/10 bg-surface-container-low p-2">
                {[
                  ["manual", "Manual selected nodes"],
                  ["auto", "Auto node count"],
                ].map(([value, label]) => (
                  <label
                    className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-white transition hover:bg-white/5"
                    key={value}
                  >
                    <input
                      checked={(draft.resource.mode ?? "manual") === value}
                      className="h-4 w-4 accent-primary"
                      name="test-plan-resource-mode"
                      type="radio"
                      value={value}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          resource: {
                            ...current.resource,
                            mode: event.target
                              .value as TestPlanDetail["resource"]["mode"],
                            selectedNodeIds:
                              event.target.value === "manual"
                                ? (current.resource.selectedNodeIds ?? [])
                                : [],
                            selectedNodeId:
                              event.target.value === "manual"
                                ? current.resource.selectedNodeId
                                : null,
                            nodeCount:
                              event.target.value === "auto"
                                ? (current.resource.nodeCount ?? 2)
                                : null,
                          },
                        }))
                      }
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="grid gap-1 text-sm text-text-muted">
              Pool Type
              <select
                className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-white"
                value={draft.resource.poolType ?? ""}
                onChange={(event) =>
                  updateDraft((current) => ({
                    ...current,
                    resource: {
                      ...current.resource,
                      poolType: (event.target.value ||
                        null) as TestPlanDetail["resource"]["poolType"],
                      selectedNodeId: null,
                      selectedNodeIds: [],
                    },
                  }))
                }
              >
                <option value="">{testPlanCopy.selectPool}</option>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </select>
            </label>
            {(draft.resource.mode ?? "manual") === "auto" ? (
              <div className="grid gap-1 text-sm text-text-muted">
                <label htmlFor="test-plan-resource-node-count">
                  Node Count
                </label>
                <input
                  aria-describedby="test-plan-resource-node-count-help"
                  className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-white"
                  id="test-plan-resource-node-count"
                  min={1}
                  max={10}
                  type="number"
                  value={draft.resource.nodeCount ?? 2}
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
                />
                <span
                  className="text-xs text-secondary"
                  id="test-plan-resource-node-count-help"
                >
                  SurgePilot allocates this many currently idle visible nodes.
                </span>
              </div>
            ) : (
              <div className="grid gap-2 text-sm text-text-muted">
                <span>Selected Nodes</span>
                <div className="flex flex-wrap items-center gap-3">
                  <Dialog.Root
                    open={nodePickerOpen}
                    onOpenChange={setNodePickerOpen}
                  >
                    <Dialog.Trigger asChild>
                      <button
                        className="rounded-xl border border-primary/30 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary disabled:opacity-40"
                        disabled={!draft.resource.poolType}
                        type="button"
                      >
                        Select nodes
                      </button>
                    </Dialog.Trigger>
                    <Dialog.Portal>
                      <Dialog.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
                      <Dialog.Content className="fixed left-1/2 top-1/2 z-50 grid max-h-[78vh] w-[min(640px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 gap-4 overflow-hidden rounded-2xl border border-white/10 bg-surface-container p-6 text-white shadow-2xl">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <Dialog.Title className="text-lg font-semibold">
                              Select Load Nodes
                            </Dialog.Title>
                            <Dialog.Description className="mt-1 text-sm text-text-muted">
                              Choose idle {draft.resource.poolType ?? "visible"}{" "}
                              nodes for this Standard Run.
                            </Dialog.Description>
                          </div>
                          <Dialog.Close className="rounded-lg p-2 text-secondary transition hover:bg-white/10 hover:text-white">
                            Close
                          </Dialog.Close>
                        </div>
                        <div className="min-h-0 space-y-2 overflow-auto pr-1">
                          {manualNodeCandidates.length ? (
                            manualNodeCandidates.map((node) => (
                              <label
                                className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 transition hover:border-primary/30 hover:bg-white/[0.06]"
                                key={node.id}
                              >
                                <span className="grid gap-0.5">
                                  <span className="text-sm font-medium text-white">
                                    {testPlanCopy.nodeOption(
                                      node.host,
                                      node.status,
                                    )}
                                  </span>
                                  <span className="text-xs capitalize text-text-muted">
                                    {node.scope === "public"
                                      ? "Public pool"
                                      : "Private pool"}
                                  </span>
                                </span>
                                <input
                                  checked={selectedManualNodeIds.includes(
                                    node.id,
                                  )}
                                  className="h-4 w-4 accent-primary"
                                  type="checkbox"
                                  onChange={(event) => {
                                    const selectedNodeIds = event.target.checked
                                      ? Array.from(
                                          new Set([
                                            ...selectedManualNodeIds,
                                            node.id,
                                          ]),
                                        )
                                      : selectedManualNodeIds.filter(
                                          (nodeId) => nodeId !== node.id,
                                        );
                                    updateDraft((current) => ({
                                      ...current,
                                      resource: {
                                        ...current.resource,
                                        mode: "manual",
                                        selectedNodeIds,
                                        selectedNodeId:
                                          selectedNodeIds[0] ?? null,
                                        nodeCount: null,
                                      },
                                    }));
                                  }}
                                />
                              </label>
                            ))
                          ) : (
                            <p className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-text-muted">
                              No idle nodes are available for the selected pool.
                            </p>
                          )}
                        </div>
                        <div className="flex items-center justify-between gap-3 border-t border-white/10 pt-4">
                          <span className="text-sm text-text-muted">
                            Selected: {selectedManualNodeCount}
                          </span>
                          <Dialog.Close className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-on-primary">
                            Done
                          </Dialog.Close>
                        </div>
                      </Dialog.Content>
                    </Dialog.Portal>
                  </Dialog.Root>
                  <span className="text-sm text-secondary">
                    {selectedManualNodeCount}{" "}
                    {selectedManualNodeCount === 1 ? "node" : "nodes"} selected
                  </span>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      <section className={sectionClass()}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {testPlanCopy.scenarioOrchestration}
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              {testPlanCopy.scenarioOrchestrationHelp}
            </p>
          </div>
          <button
            className={miniButton("primary")}
            disabled={!scenarioQuery.data?.items.length}
            onClick={() => {
              const scenario = scenarioQuery.data?.items[0];
              if (!scenario) return;
              updateDraft((current) => ({
                ...current,
                scenarioItems: [
                  ...current.scenarioItems,
                  newScenarioItem(scenario),
                ],
              }));
            }}
            type="button"
          >
            {testPlanCopy.addScenario}
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {draft.scenarioItems.map((item, index) => (
            <div
              className="rounded-xl border border-white/10 bg-white/[0.03] p-3"
              key={item.id}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="grid min-w-[240px] flex-1 gap-1 text-xs text-text-muted md:max-w-sm">
                  Scenario Name
                  <select
                    aria-label="Scenario name"
                    className="rounded-lg border border-white/10 bg-surface-container-low px-2 py-1.5 text-sm text-white"
                    value={item.scenarioId}
                    onChange={(event) => {
                      const scenario = scenarioQuery.data?.items.find(
                        (row) => row.id === event.target.value,
                      );
                      if (!scenario) return;
                      updateDraft((current) => ({
                        ...current,
                        scenarioItems: current.scenarioItems.map(
                          (row): TestPlanScenarioItem =>
                            row.id === item.id
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
                    }}
                  >
                    {scenarioQuery.data?.items.map((scenario) => (
                      <option key={scenario.id} value={scenario.id}>
                        {scenario.name}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex gap-2">
                  <button
                    className={miniButton()}
                    disabled={index === 0}
                    onClick={() =>
                      updateDraft((current) => {
                        const rows = [...current.scenarioItems];
                        [rows[index - 1], rows[index]] = [
                          rows[index],
                          rows[index - 1],
                        ];
                        return { ...current, scenarioItems: rows };
                      })
                    }
                    type="button"
                  >
                    Up
                  </button>
                  <button
                    className={miniButton()}
                    disabled={index === draft.scenarioItems.length - 1}
                    onClick={() =>
                      updateDraft((current) => {
                        const rows = [...current.scenarioItems];
                        [rows[index], rows[index + 1]] = [
                          rows[index + 1],
                          rows[index],
                        ];
                        return { ...current, scenarioItems: rows };
                      })
                    }
                    type="button"
                  >
                    Down
                  </button>
                  <button
                    className={miniButton("danger")}
                    onClick={() =>
                      updateDraft((current) => ({
                        ...current,
                        scenarioItems: current.scenarioItems.filter(
                          (row) => row.id !== item.id,
                        ),
                      }))
                    }
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-6">
                {[
                  ["Concurrency / Node", "concurrencyPerNode"],
                  ["Ramp-up", "rampUpSeconds"],
                  ["Hold-for", "holdForSeconds"],
                  ["Iterations", "iterations"],
                  ["Target RPS", "targetRps"],
                  ["Steps", "steps"],
                  ["Delay", "delaySeconds"],
                ].map(([label, key]) => (
                  <label
                    className="grid gap-1 text-xs text-text-muted"
                    key={key}
                  >
                    {label}
                    <input
                      className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 text-white"
                      type="number"
                      value={String(
                        (item.loadSettings ?? defaultLoadSettings)[
                          key as keyof typeof defaultLoadSettings
                        ] ?? "",
                      )}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          scenarioItems: current.scenarioItems.map(
                            (row): TestPlanScenarioItem =>
                              row.id === item.id
                                ? {
                                    ...row,
                                    loadSettings: {
                                      ...(row.loadSettings ??
                                        defaultLoadSettings),
                                      [key]:
                                        key === "targetRps" ||
                                        key === "iterations" ||
                                        key === "holdForSeconds" ||
                                        key === "steps"
                                          ? parseOptionalNumber(
                                              event.target.value,
                                            )
                                          : Number(event.target.value),
                                    },
                                  }
                                : row,
                          ),
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          ))}
          {draft.scenarioItems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 p-5 text-sm text-text-muted">
              {testPlanCopy.noScenarioItems}
            </div>
          ) : null}
        </div>
      </section>

      <section className={sectionClass()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {testPlanCopy.slaRules}
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              {testPlanCopy.slaRulesHelp}
            </p>
          </div>
          <button
            className={miniButton("primary")}
            onClick={() =>
              updateDraft((current) => ({
                ...current,
                slaRules: [...current.slaRules, newSlaRule()],
              }))
            }
            type="button"
          >
            {testPlanCopy.addRule}
          </button>
        </div>
        <div className="mt-4 space-y-3">
          {draft.slaRules.map((rule) => {
            const metric = metricValueForSubject(rule.subject);
            const option = metricOption(metric);
            const unitOptions = option.units as readonly SlaThresholdUnit[];
            return (
              <div
                className="rounded-xl border border-white/10 bg-white/[0.03] p-3"
                key={rule.id}
              >
                <div className="grid gap-3 md:grid-cols-[1.1fr_0.9fr_0.7fr_0.7fr_0.8fr_auto]">
                  <label className="grid gap-1 text-xs text-text-muted">
                    Metric
                    <select
                      aria-label="SLA metric"
                      className="rounded-lg border border-white/10 bg-surface-container-low px-2 py-1.5 text-white"
                      value={metric}
                      onChange={(event) => {
                        const nextMetric = event.target.value as SlaMetricValue;
                        const nextOption = metricOption(nextMetric);
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.map((row) =>
                            row.id === rule.id
                              ? {
                                  ...row,
                                  subject: subjectForMetric(
                                    nextMetric,
                                    responseCodePattern(row.subject),
                                  ),
                                  condition: nextOption.defaultCondition,
                                  threshold: {
                                    value: nextOption.defaultThreshold,
                                    unit: nextOption.defaultUnit,
                                  },
                                }
                              : row,
                          ),
                        }));
                      }}
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
                    Fail when
                    <select
                      aria-label="Fail when"
                      className="rounded-lg border border-white/10 bg-surface-container-low px-2 py-1.5 text-white"
                      value={rule.condition}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.map((row) =>
                            row.id === rule.id
                              ? {
                                  ...row,
                                  condition: event.target
                                    .value as TestPlanSlaRule["condition"],
                                }
                              : row,
                          ),
                        }))
                      }
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
                      className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 text-white"
                      type="number"
                      value={rule.threshold.value}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.map((row) =>
                            row.id === rule.id
                              ? {
                                  ...row,
                                  threshold: {
                                    ...row.threshold,
                                    value: Number(event.target.value),
                                  },
                                }
                              : row,
                          ),
                        }))
                      }
                    />
                  </label>
                  <label className="grid gap-1 text-xs text-text-muted">
                    Unit
                    <select
                      aria-label="SLA unit"
                      className="rounded-lg border border-white/10 bg-surface-container-low px-2 py-1.5 text-white"
                      value={
                        isValidUnitForMetric(metric, rule.threshold.unit)
                          ? rule.threshold.unit
                          : option.defaultUnit
                      }
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.map((row) =>
                            row.id === rule.id
                              ? {
                                  ...row,
                                  threshold: {
                                    ...row.threshold,
                                    unit: event.target
                                      .value as TestPlanSlaRule["threshold"]["unit"],
                                  },
                                }
                              : row,
                          ),
                        }))
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
                      className="rounded-lg border border-white/10 bg-surface-container-low px-2 py-1.5 text-white"
                      value={rule.action}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.map((row) =>
                            row.id === rule.id
                              ? {
                                  ...row,
                                  action: event.target
                                    .value as TestPlanSlaRule["action"],
                                }
                              : row,
                          ),
                        }))
                      }
                    >
                      <option value="continue">Continue</option>
                      <option value="stop">Stop</option>
                    </select>
                  </label>
                  <div className="flex items-end">
                    <button
                      className={miniButton("danger")}
                      onClick={() =>
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.filter(
                            (row) => row.id !== rule.id,
                          ),
                        }))
                      }
                      type="button"
                    >
                      Remove
                    </button>
                  </div>
                </div>
                {metric === "rc" ? (
                  <label className="mt-3 grid max-w-xs gap-1 text-xs text-text-muted">
                    Response code pattern
                    <input
                      aria-label="Response code pattern"
                      aria-invalid={
                        !isSupportedResponseCodePattern(
                          responseCodePattern(rule.subject),
                        )
                      }
                      className="rounded-lg border border-white/10 bg-black/20 px-2 py-1.5 text-white aria-invalid:border-error/60"
                      value={responseCodePattern(rule.subject)}
                      onChange={(event) =>
                        updateDraft((current) => ({
                          ...current,
                          slaRules: current.slaRules.map((row) =>
                            row.id === rule.id
                              ? {
                                  ...row,
                                  subject: subjectForMetric(
                                    "rc",
                                    event.target.value,
                                  ),
                                }
                              : row,
                          ),
                        }))
                      }
                    />
                    <span className="text-[11px] text-text-muted">
                      Use 500, 4??, or *.
                    </span>
                  </label>
                ) : null}
              </div>
            );
          })}
          {draft.slaRules.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 p-5 text-sm text-text-muted">
              {testPlanCopy.noSlaRules}
            </div>
          ) : null}
        </div>
      </section>

      <section className={sectionClass()}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {testPlanCopy.previewTitle}
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              {testPlanCopy.previewDescription}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="grid gap-1 text-xs text-text-muted">
              {testPlanCopy.previewRunType}
              <select
                aria-label={testPlanCopy.previewRunType}
                className="rounded-xl border border-white/10 bg-surface-container-low px-3 py-2 text-sm text-white"
                value={previewRunType}
                onChange={(event) => {
                  setPreviewRunType(event.target.value as "debug" | "standard");
                  clearExecutionPreview();
                }}
              >
                <option value="debug">Debug</option>
                <option value="standard">Standard</option>
              </select>
            </label>
            <button
              className="rounded-xl border border-primary/30 bg-primary/10 px-4 py-2 text-sm font-semibold text-primary disabled:opacity-40"
              disabled={dirty || previewMutation.isPending}
              onClick={() => previewMutation.mutate()}
              type="button"
            >
              {testPlanCopy.previewYaml}
            </button>
          </div>
        </div>
        {!dirty && draft.notRunnableReasons.includes("load_node_required") ? (
          <p className="mt-3 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
            {testPlanCopy.previewLoadNodePrerequisite}
          </p>
        ) : null}
        {dirty ? (
          <p className="mt-3 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
            {testPlanCopy.saveBeforePreview}
          </p>
        ) : null}
        {previewError ? (
          <p className="mt-3 rounded-xl border border-error/30 bg-error-container p-3 text-sm text-on-error-container">
            {previewError}
          </p>
        ) : null}
        {executionPreview ? (
          <div className="mt-4 space-y-3">
            {executionPreview.warnings.length > 0 ? (
              <div className="space-y-2">
                {executionPreview.warnings.map((warning) => (
                  <p
                    className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-warning"
                    key={`${warning.code}-${warning.field ?? "global"}`}
                  >
                    {warning.message}
                  </p>
                ))}
              </div>
            ) : null}
            <pre className="max-h-96 overflow-auto rounded-2xl border border-white/10 bg-black/30 p-4 font-mono text-xs leading-5 text-text-main">
              {executionPreview.content}
            </pre>
          </div>
        ) : null}
      </section>

      {pendingConfirmation ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div
            role="dialog"
            aria-label={testPlanCopy.highConcurrencyTitle}
            className="w-full max-w-md rounded-3xl border border-warning/30 bg-surface-container-low p-6 shadow-2xl"
          >
            <h2 className="text-xl font-semibold text-white">
              {testPlanCopy.highConcurrencyTitle}
            </h2>
            <p className="mt-2 text-sm text-text-muted">
              {testPlanCopy.highConcurrencyBody}
            </p>
            <p className="mt-3 font-mono text-xs text-warning">
              {testPlanCopy.highConcurrencyMeta(
                localExpectedConcurrency,
                draft.runGuard.softConcurrencyPerNodeLimit,
              )}
            </p>
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-xl border border-white/10 px-4 py-2 text-white"
                onClick={() => setPendingConfirmation(null)}
                type="button"
              >
                {testPlanCopy.cancel}
              </button>
              <button
                className="rounded-xl bg-primary px-4 py-2 font-semibold text-on-primary"
                onClick={() => {
                  setPendingConfirmation(null);
                  void runWith("standard", true);
                }}
                type="button"
              >
                {testPlanCopy.confirmAndRun}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
