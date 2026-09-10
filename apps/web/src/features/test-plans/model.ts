import type {
  TestPlanCreateRequest,
  TestPlanDetail,
  TestPlanLoadSettings,
  TestPlanPatchRequest,
  TestPlanScenarioItem,
  TestPlanSlaRule,
} from "../../app/api-client";
import { testPlanCopy } from "./copy";

const ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const ulid = () =>
  `01${Array.from({ length: 24 }, () => ULID_ALPHABET[Math.floor(Math.random() * ULID_ALPHABET.length)]).join("")}`;

export const defaultLoadSettings: TestPlanLoadSettings = {
  concurrencyPerNode: 1,
  rampUpSeconds: 0,
  holdForSeconds: 60,
  iterations: null,
  targetRps: null,
  steps: null,
  delaySeconds: 0,
};

export function blankTestPlanPayload(
  name: string,
  description: string | null,
  tags: string[],
): TestPlanCreateRequest {
  return {
    name,
    description,
    tags,
    envGroupId: null,
    runMode: "sequential",
    resource: {
      mode: "manual",
      poolType: null,
      selectedNodeId: null,
      selectedNodeIds: [],
      nodeCount: null,
    },
    scenarioItems: [],
    slaRules: [],
  };
}

export function toPatchPayload(detail: TestPlanDetail): TestPlanPatchRequest {
  return {
    expectedRevision: detail.revision,
    name: detail.name,
    description: detail.description,
    tags: detail.tags,
    envGroupId: detail.envGroupId ?? null,
    runMode: detail.runMode,
    resource: detail.resource ?? {
      mode: "manual",
      poolType: null,
      selectedNodeId: null,
      selectedNodeIds: [],
      nodeCount: null,
    },
    scenarioItems: detail.scenarioItems.map((item, index) => ({
      id: item.id,
      scenarioId: item.scenarioId,
      enabled: true,
      order: index,
      loadSettings: item.loadSettings ?? { ...defaultLoadSettings },
    })),
    slaRules: detail.slaRules.map((rule) => ({
      id: rule.id,
      enabled: true,
      subject: rule.subject,
      label: rule.label ?? null,
      condition: rule.condition,
      threshold: rule.threshold,
      timeframeLogic: rule.timeframeLogic ?? null,
      timeframeSeconds: rule.timeframeSeconds ?? null,
      action: rule.action,
    })),
  };
}

export function needsEnabledStateMigration(detail: TestPlanDetail): boolean {
  return (
    detail.scenarioItems.some((item) => !item.enabled) ||
    detail.slaRules.some((rule) => !rule.enabled)
  );
}

export function newScenarioItem(scenario: {
  id: string;
  name: string;
  revision: number;
  enabledStepCount: number;
  updatedAt: string;
}): TestPlanScenarioItem {
  return {
    id: ulid(),
    scenarioId: scenario.id,
    scenarioName: scenario.name,
    scenarioRevision: scenario.revision,
    enabledStepCount: scenario.enabledStepCount,
    updatedAt: scenario.updatedAt,
    enabled: true,
    order: 0,
    loadSettings: { ...defaultLoadSettings },
  };
}

export function newSlaRule(): TestPlanSlaRule {
  return {
    id: ulid(),
    enabled: true,
    subject: "p95",
    label: null,
    condition: "gt",
    threshold: { value: 500, unit: "ms" },
    timeframeLogic: null,
    timeframeSeconds: null,
    action: "continue",
  };
}

export function tagsFromText(value: string) {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 10);
}

export function tagText(tags: string[]) {
  return tags.join(", ");
}

const STANDARD_ONLY_NOT_RUNNABLE_REASONS = new Set([
  "single_node_concurrency_hard_limit",
  "too_many_sla_rules",
]);

export function canRunDraft(detail: TestPlanDetail | null) {
  if (!detail) return false;
  const mode = detail.resource.mode ?? "manual";
  const hasResource = mode === "auto"
    ? Boolean(detail.resource.poolType && detail.resource.nodeCount)
    : Boolean(
        detail.resource.poolType &&
        (detail.resource.selectedNodeIds?.length || detail.resource.selectedNodeId),
      );
  return (
    detail.scenarioItems.length > 0 &&
    hasResource
  );
}

export function canDebugSavedPlan(detail: TestPlanDetail | null) {
  if (!detail) return false;
  if (
    detail.scenarioItems.length === 0 ||
    !detail.resource.poolType ||
    !detail.resource.selectedNodeId
  ) {
    return false;
  }
  if (detail.runnable) return true;
  return (
    detail.notRunnableReasons.length > 0 &&
    detail.notRunnableReasons.every((reason) =>
      STANDARD_ONLY_NOT_RUNNABLE_REASONS.has(reason),
    )
  );
}

export function expectedConcurrency(detail: TestPlanDetail | null) {
  if (!detail) return 0;
  const values = detail.scenarioItems.map(
    (item) => item.loadSettings?.concurrencyPerNode ?? 1,
  );
  if (values.length === 0) return 0;
  return detail.runMode === "parallel"
    ? values.reduce((sum, value) => sum + value, 0)
    : Math.max(...values);
}

export type LoadSettingsProblemKey =
  | "termination"
  | "stepsRequireRampUp"
  | "targetRpsRequiresHoldFor";

export function loadSettingsProblem(
  item: TestPlanScenarioItem,
): LoadSettingsProblemKey | null {
  const settings = item.loadSettings ?? defaultLoadSettings;
  const hasHold =
    settings.holdForSeconds !== null && settings.holdForSeconds !== undefined;
  const hasIterations =
    settings.iterations !== null && settings.iterations !== undefined;
  if (hasHold === hasIterations) return "termination";
  if (settings.steps && settings.rampUpSeconds <= 0) {
    return "stepsRequireRampUp";
  }
  if (settings.targetRps && !hasHold) {
    return "targetRpsRequiresHoldFor";
  }
  return null;
}

export function validateLoadSettings(detail: TestPlanDetail | null) {
  if (!detail) return [];
  const errors: string[] = [];
  detail.scenarioItems.forEach((item, index) => {
    const problem = loadSettingsProblem(item);
    if (problem === "termination") {
      errors.push(testPlanCopy.loadSettingErrors.termination(index + 1));
    } else if (problem === "stepsRequireRampUp") {
      errors.push(testPlanCopy.loadSettingErrors.stepsRequireRampUp(index + 1));
    } else if (problem === "targetRpsRequiresHoldFor") {
      errors.push(
        testPlanCopy.loadSettingErrors.targetRpsRequiresHoldFor(index + 1),
      );
    }
  });
  return errors;
}

const RESPONSE_CODE_PATTERN = /^(?:\d{3}|\d\?\?|\*)$/;

export function isSupportedResponseCodePattern(pattern: string) {
  return RESPONSE_CODE_PATTERN.test(pattern.trim());
}

export function validateSlaRules(detail: TestPlanDetail | null) {
  if (!detail) return [];
  const errors: string[] = [];
  detail.slaRules.forEach((rule, index) => {
    if (
      rule.subject.startsWith("rc") &&
      !isSupportedResponseCodePattern(rule.subject.slice(2))
    ) {
      errors.push(testPlanCopy.slaRuleErrors.responseCodePattern(index + 1));
    }
  });
  return errors;
}

export function validateTestPlanDraft(detail: TestPlanDetail | null) {
  return [...validateLoadSettings(detail), ...validateSlaRules(detail)];
}
