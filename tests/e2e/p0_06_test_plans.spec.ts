import { expect, test, type Page } from "@playwright/test";

const workspaceId = "01HZW000000000000000000000";
const planId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";
const scenarioId = "01HZX3Y9M0E9W7Z6M5QK9S8P7B";
const envGroupId = "01HZX3Y9M0E9W7Z6M5QK9S8P7C";
const itemId = "01HZX3Y9M0E9W7Z6M5QK9S8P7D";
const ruleId = "01HZX3Y9M0E9W7Z6M5QK9S8P7E";
const nodeId = "01HZX3Y9M0E9W7Z6M5QK9S8P7N";
const standardRunId = "01HZX3Y9M0E9W7Z6M5QK9S8P7R";
const debugRunId = "01HZX3Y9M0E9W7Z6M5QK9S8P7S";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "test-plans@example.com",
    displayName: "Test Plan User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: workspaceId,
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

const stagingEnvGroup = {
  id: envGroupId,
  name: "Staging",
  description: "Staging environment",
  variableCount: 1,
  inUse: true,
  createdBy: authSession.user.id,
  updatedBy: authSession.user.id,
  createdAt: "2030-06-01T07:00:00Z",
  updatedAt: "2030-06-01T07:00:00Z",
};

const checkoutScenario = {
  id: scenarioId,
  name: "Checkout flow",
  description: null,
  tags: ["checkout"],
  scenarioType: "visual",
  stepCount: 1,
  enabledStepCount: 1,
  dependencyFileCount: 0,
  revision: 2,
  createdAt: "2030-06-01T08:00:00Z",
  updatedAt: "2030-06-01T08:30:00Z",
};

const idleNode = {
  id: nodeId,
  scope: "workspace",
  workspaceId,
  host: "plan-node-smoke.internal",
  sshPort: 22,
  sshUser: "surgepilot",
  runnerHome: "/opt/surgepilot/runner",
  authType: "password",
  credentialConfigured: true,
  credentialFingerprint: null,
  generatedPublicKey: null,
  maintainer: null,
  remark: null,
  status: "idle",
  lastStatusReason: null,
  runnerVersion: "0.1.0",
  bundleVersion: "p0-03",
  lastInitializedAt: "2030-06-01T08:30:00Z",
  lastCheckedAt: "2030-06-01T08:30:00Z",
  lastHeartbeatAt: null,
  currentRunId: null,
  lastInitAttemptId: null,
  createdAt: "2030-06-01T08:00:00Z",
  updatedAt: "2030-06-01T08:30:00Z",
};

const defaultLoadSettings = {
  concurrencyPerNode: 1,
  rampUpSeconds: 0,
  holdForSeconds: 60,
  iterations: null,
  targetRps: null,
  steps: null,
  delaySeconds: 0,
};

function runGuard(expectedConcurrencyPerNode: number, softLimit: number) {
  return {
    expectedConcurrencyPerNode,
    softConcurrencyPerNodeLimit: softLimit,
    hardConcurrencyPerNodeLimit: 10000,
    requiresHighConcurrencyConfirmation: expectedConcurrencyPerNode > softLimit,
  };
}

function scenarioItem(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    id: itemId,
    scenarioId,
    scenarioName: "Checkout flow",
    scenarioRevision: 2,
    enabledStepCount: 1,
    updatedAt: "2030-06-01T08:30:00Z",
    enabled: true,
    order: 0,
    loadSettings: { ...defaultLoadSettings },
    ...overrides,
  };
}

function slaRule(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: ruleId,
    enabled: true,
    subject: "p95",
    label: null,
    condition: "gt",
    threshold: { value: 500, unit: "ms" },
    timeframeLogic: null,
    timeframeSeconds: null,
    action: "continue",
    ...overrides,
  };
}

function planDetail(
  state: PlanState,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  const expectedConcurrency =
    state.runMode === "parallel"
      ? state.scenarioItems.reduce(
          (sum, item) =>
            sum + ((item.loadSettings as Record<string, unknown>)
              .concurrencyPerNode as number),
          0,
        )
      : state.scenarioItems.reduce(
          (max, item) =>
            Math.max(
              max,
              (item.loadSettings as Record<string, unknown>)
                .concurrencyPerNode as number,
            ),
          0,
        );
  return {
    id: planId,
    name: state.name,
    description: state.description,
    tags: state.tags,
    envGroupId: state.envGroupId,
    runMode: state.runMode,
    resource: state.resource,
    scenarioItems: state.scenarioItems,
    slaRules: state.slaRules,
    runGuard: runGuard(expectedConcurrency, state.softLimit),
    runnable:
      state.scenarioItems.length > 0 &&
      Boolean(state.resource.poolType && state.resource.selectedNodeId),
    notRunnableReasons:
      state.scenarioItems.length > 0 &&
      state.resource.poolType &&
      state.resource.selectedNodeId
        ? []
        : ["no_resource_configuration"],
    revision: state.revision,
    createdAt: "2030-06-01T09:00:00Z",
    updatedAt: "2030-06-01T09:30:00Z",
    ...overrides,
  };
}

function planSummary(detail: Record<string, unknown>): Record<string, unknown> {
  return {
    id: detail.id,
    name: detail.name,
    description: detail.description,
    tags: detail.tags,
    envGroup: detail.envGroupId
      ? { id: detail.envGroupId, name: "Staging" }
      : null,
    scenarioItemCount: (detail.scenarioItems as unknown[]).length,
    enabledScenarioItemCount: (detail.scenarioItems as unknown[]).length,
    slaRuleCount: (detail.slaRules as unknown[]).length,
    expectedConcurrencyPerNode: (
      detail.runGuard as Record<string, unknown>
    ).expectedConcurrencyPerNode,
    requiresHighConcurrencyConfirmation: Boolean(
      (detail.runGuard as Record<string, unknown>)
        .requiresHighConcurrencyConfirmation,
    ),
    resource: detail.resource,
    runMode: detail.runMode,
    runnable: detail.runnable,
    notRunnableReasons: detail.notRunnableReasons,
    revision: detail.revision,
    updatedAt: detail.updatedAt,
    updatedBy: { id: authSession.user.id, displayName: "Test Plan User" },
  };
}

type PlanState = {
  name: string;
  description: string | null;
  tags: string[];
  envGroupId: string | null;
  runMode: "sequential" | "parallel";
  resource: { poolType: "public" | "private" | null; selectedNodeId: string | null };
  scenarioItems: Array<Record<string, unknown>>;
  slaRules: Array<Record<string, unknown>>;
  revision: number;
  softLimit: number;
};

type RunAttempt = {
  runType: string;
  sourceType: string;
  sourceId: string;
  expectedSourceRevision: number;
  confirmHighConcurrency: boolean;
};

type Captures = {
  listRequests: number;
  createPayload: Record<string, unknown> | null;
  savePayload: Record<string, unknown> | null;
  debugSavePayload: Record<string, unknown> | null;
  standardAttempts: RunAttempt[];
  debugAttempt: RunAttempt | null;
  deleted: boolean;
};

async function installRoutes(
  page: Page,
  state: PlanState,
  captures: Captures,
) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (url.pathname === "/api/v1/auth/me") {
      await route.fulfill({ json: authSession });
      return;
    }
    if (url.pathname === "/api/v1/auth/csrf") {
      await route.fulfill({ json: { csrfToken: "csrf-token" } });
      return;
    }
    if (url.pathname === "/api/v1/test-plans" && method === "POST") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      const payload = request.postDataJSON() as Record<string, unknown>;
      captures.createPayload = payload;
      state.name = payload.name as string;
      state.description = (payload.description as string | null) ?? null;
      state.tags = (payload.tags as string[]) ?? [];
      state.envGroupId = (payload.envGroupId as string | null) ?? null;
      state.runMode = (payload.runMode as "sequential" | "parallel") ?? "sequential";
      state.resource = payload.resource as PlanState["resource"];
      state.scenarioItems = [];
      state.slaRules = [];
      state.revision = 1;
      await route.fulfill({ status: 201, json: planDetail(state) });
      return;
    }
    if (url.pathname === "/api/v1/test-plans" && method === "GET") {
      const detail = planDetail(state);
      const items =
        captures.deleted || state.revision === 0 ? [] : [planSummary(detail)];
      captures.listRequests += 1;
      await route.fulfill({
        json: { items, page: 1, pageSize: 100, total: items.length },
      });
      return;
    }
    if (url.pathname === `/api/v1/test-plans/${planId}` && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({ json: planDetail(state) });
      return;
    }
    if (url.pathname === `/api/v1/test-plans/${planId}` && method === "PATCH") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      const payload = request.postDataJSON() as Record<string, unknown>;
      if (payload.expectedRevision !== state.revision) {
        await route.fulfill({
          status: 409,
          json: { code: "TEST_PLAN_REVISION_CONFLICT", message: "stale" },
        });
        return;
      }
      state.revision += 1;
      state.name = payload.name as string;
      state.description = (payload.description as string | null) ?? null;
      state.tags = (payload.tags as string[]) ?? [];
      state.envGroupId = (payload.envGroupId as string | null) ?? null;
      state.runMode = (payload.runMode as "sequential" | "parallel") ?? "sequential";
      state.resource = payload.resource as PlanState["resource"];
      state.scenarioItems = (payload.scenarioItems as Array<
        Record<string, unknown>
      >).map((item) => {
        const id = (item.id as string | null) ?? itemId;
        return {
          id,
          scenarioId: item.scenarioId as string,
          scenarioName: checkoutScenario.name,
          scenarioRevision: checkoutScenario.revision,
          enabledStepCount: checkoutScenario.enabledStepCount,
          updatedAt: checkoutScenario.updatedAt,
          enabled: (item.enabled as boolean) ?? true,
          order: (item.order as number) ?? 0,
          loadSettings: item.loadSettings ?? { ...defaultLoadSettings },
        };
      });
      state.slaRules = (payload.slaRules as Array<Record<string, unknown>>).map(
        (rule) => ({
          id: (rule.id as string | null) ?? ruleId,
          enabled: (rule.enabled as boolean) ?? true,
          subject: rule.subject as string,
          label: (rule.label as string | null) ?? null,
          condition: rule.condition as string,
          threshold: rule.threshold,
          timeframeLogic: (rule.timeframeLogic as string | null) ?? null,
          timeframeSeconds: (rule.timeframeSeconds as number | null) ?? null,
          action: rule.action as string,
        }),
      );
      if (state.revision === 2) {
        captures.savePayload = payload;
      } else if (state.revision === 3) {
        captures.debugSavePayload = payload;
      }
      await route.fulfill({ json: planDetail(state) });
      return;
    }
    if (url.pathname === `/api/v1/test-plans/${planId}` && method === "DELETE") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      captures.deleted = true;
      state.revision = 0;
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (url.pathname === "/api/v1/env-groups" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({
        json: {
          items: [stagingEnvGroup],
          page: 1,
          pageSize: 100,
          total: 1,
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/scenarios" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({
        json: {
          items: [checkoutScenario],
          page: 1,
          pageSize: 100,
          total: 1,
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/load-nodes" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({
        json: { items: [idleNode], limit: 100, offset: 0, total: 1 },
      });
      return;
    }
    if (url.pathname === "/api/v1/runs" && method === "POST") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      const payload = request.postDataJSON() as RunAttempt;
      if (payload.runType === "debug") {
        captures.debugAttempt = payload;
        await route.fulfill({
          status: 201,
          json: {
            id: debugRunId,
            state: "initializing",
            runType: "debug",
            sourceType: "test_plan",
            sourceId: planId,
            selectedNodeId: nodeId,
            createdAt: "2030-06-01T09:40:00Z",
            deduplicated: false,
          },
        });
        return;
      }
      captures.standardAttempts.push(payload);
      if (payload.confirmHighConcurrency !== true) {
        await route.fulfill({
          status: 409,
          json: {
            code: "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED",
            message: "Confirmation required",
          },
        });
        return;
      }
      await route.fulfill({
        status: 201,
        json: {
          id: standardRunId,
          state: "initializing",
          runType: "standard",
          sourceType: "test_plan",
          sourceId: planId,
          selectedNodeId: nodeId,
          createdAt: "2030-06-01T09:41:00Z",
          deduplicated: false,
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { code: "RESOURCE_NOT_FOUND" } });
  });
}

function initialPlanState(): PlanState {
  return {
    name: "Checkout Load Test",
    description: "Checkout flow baseline",
    tags: ["checkout", "baseline"],
    envGroupId: envGroupId,
    runMode: "sequential",
    resource: { poolType: "private", selectedNodeId: nodeId },
    scenarioItems: [scenarioItem()],
    slaRules: [slaRule()],
    revision: 0,
    softLimit: 5,
  };
}

test("creates a Test Plan, saves orchestration, and starts a standard Run Now", async ({
  page,
}) => {
  const state = initialPlanState();
  state.revision = 0;
  const captures: Captures = {
    listRequests: 0,
    createPayload: null,
    savePayload: null,
    debugSavePayload: null,
    standardAttempts: [],
    debugAttempt: null,
    deleted: false,
  };
  await installRoutes(page, state, captures);

  await page.goto("/test-plans");
  await expect(page.getByRole("heading", { name: "Test Plans" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No test plans yet" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Create Test Plan" }).first().click();
  const createDialog = page.getByRole("dialog", { name: "Create Test Plan" });
  await expect(createDialog).toBeVisible();
  await createDialog.getByLabel("Test Plan name").fill("Checkout Load Test");
  await createDialog.getByLabel("Description").fill("Checkout flow baseline");
  await createDialog.getByLabel("Tags").fill("checkout, baseline");
  await createDialog.getByRole("button", { name: "Create", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Checkout Load Test" })).toBeVisible();
  await expect(page.getByText("Revision 1")).toBeVisible();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  expect(captures.createPayload).toMatchObject({
    name: "Checkout Load Test",
    description: "Checkout flow baseline",
    tags: ["checkout", "baseline"],
    runMode: "sequential",
    resource: { poolType: null, selectedNodeId: null },
    scenarioItems: [],
    slaRules: [],
  });

  const envGroupSelect = page.getByLabel("Env Group");
  await envGroupSelect.locator("option", { hasText: "Staging" }).first().waitFor();
  await envGroupSelect.selectOption(envGroupId);
  await expect(page.getByLabel("Run Mode")).toHaveValue("sequential");

  await page.getByLabel("Pool Type").selectOption("private");
  const loadNodeSelect = page.getByLabel("Load Node");
  await expect(
    loadNodeSelect.locator(`option[value="${nodeId}"]`),
  ).toHaveCount(1);
  await loadNodeSelect.selectOption(nodeId);

  const addScenarioButton = page.getByRole("button", { name: "Add Scenario" });
  await expect(addScenarioButton).toBeEnabled();
  await addScenarioButton.click();
  await expect(page.getByText("Scenario 1")).toBeVisible();
  await expect(page.getByLabel("Scenario name")).toHaveValue(scenarioId);
  await expect(page.getByLabel("Concurrency / Node 1")).toHaveValue("1");
  await expect(page.getByLabel("Hold-for 1")).toHaveValue("60");

  await page.getByLabel("Concurrency / Node 1").fill("10");
  await expect(page.getByText("Unsaved changes")).toBeVisible();
  await expect(page.getByText("Revision 1")).toBeVisible();

  await page.getByRole("button", { name: "Add Rule" }).click();
  await expect(page.getByText("Rule 1")).toBeVisible();
  await expect(page.getByLabel("SLA metric")).toHaveValue("p95");
  await expect(page.getByLabel("SLA threshold")).toHaveValue("500");

  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await expect(page.getByText("Revision 2")).toBeVisible();
  await expect(
    page.getByText("Expected single-node concurrency: 10 (soft limit 5)"),
  ).toBeVisible();

  expect(captures.savePayload).toMatchObject({
    expectedRevision: 1,
    name: "Checkout Load Test",
    description: "Checkout flow baseline",
    tags: ["checkout", "baseline"],
    envGroupId,
    runMode: "sequential",
    resource: { poolType: "private", selectedNodeId: nodeId },
  });
  const savedItems = (captures.savePayload?.scenarioItems ?? []) as Array<
    Record<string, unknown>
  >;
  expect(savedItems.length).toBe(1);
  expect(savedItems[0]).toMatchObject({
    scenarioId,
    enabled: true,
    order: 0,
  });
  expect(savedItems[0].loadSettings).toMatchObject({ concurrencyPerNode: 10 });
  const savedRules = (captures.savePayload?.slaRules ?? []) as Array<
    Record<string, unknown>
  >;
  expect(savedRules.length).toBe(1);
  expect(savedRules[0]).toMatchObject({
    subject: "p95",
    condition: "gt",
    threshold: { value: 500, unit: "ms" },
    action: "continue",
  });

  await page.getByRole("button", { name: "Run Now", exact: true }).click();
  const confirmation = page.getByRole("dialog", {
    name: "Confirm high concurrency",
  });
  await expect(confirmation).toBeVisible();
  await expect(confirmation.getByText("Expected: 10 / Soft limit: 5")).toBeVisible();
  await confirmation
    .getByRole("button", { name: "Confirm and run", exact: true })
    .click();

  await expect(page).toHaveURL(new RegExp(`/runs/${standardRunId}$`));
  await expect(
    page.getByRole("heading", { name: "Debug Run started" }),
  ).toBeVisible();

  expect(captures.standardAttempts.length).toBe(2);
  expect(captures.standardAttempts[0]).toEqual({
    runType: "standard",
    sourceType: "test_plan",
    sourceId: planId,
    expectedSourceRevision: 2,
    confirmHighConcurrency: false,
  });
  expect(captures.standardAttempts[1]).toEqual({
    runType: "standard",
    sourceType: "test_plan",
    sourceId: planId,
    expectedSourceRevision: 2,
    confirmHighConcurrency: true,
  });
});

test("opens a saved Test Plan, runs Debug, and deletes the plan", async ({
  page,
}) => {
  const state = initialPlanState();
  state.revision = 2;
  const captures: Captures = {
    listRequests: 0,
    createPayload: null,
    savePayload: null,
    debugSavePayload: null,
    standardAttempts: [],
    debugAttempt: null,
    deleted: false,
  };
  await installRoutes(page, state, captures);

  await page.goto("/test-plans");
  await expect(page.getByText("Checkout Load Test")).toBeVisible();
  await expect(page.getByText("1/1")).toBeVisible();

  await page.getByRole("link", { name: "Checkout Load Test" }).click();
  await expect(page.getByRole("heading", { name: "Checkout Load Test" })).toBeVisible();
  await expect(page.getByText("Revision 2")).toBeVisible();
  await expect(page.getByLabel("Env Group")).toHaveValue(envGroupId);
  await expect(page.getByLabel("Scenario name")).toHaveValue(scenarioId);
  await expect(page.getByLabel("Concurrency / Node 1")).toHaveValue("10");

  await page.getByLabel("Description").fill("Checkout debug run description");
  await expect(page.getByText("Unsaved changes")).toBeVisible();
  await page
    .getByRole("button", { name: "Save and Debug", exact: true })
    .click();

  await expect(page).toHaveURL(new RegExp(`/runs/${debugRunId}$`));
  await expect(
    page.getByRole("heading", { name: "Debug Run started" }),
  ).toBeVisible();

  expect(captures.debugSavePayload).toMatchObject({
    expectedRevision: 2,
    description: "Checkout debug run description",
  });
  expect(captures.debugAttempt).toEqual({
    runType: "debug",
    sourceType: "test_plan",
    sourceId: planId,
    expectedSourceRevision: 3,
    confirmHighConcurrency: false,
  });

  await page.getByRole("link", { name: "Test Plans" }).click();
  await expect(page.getByRole("heading", { name: "Test Plans" })).toBeVisible();
  await page.getByRole("button", { name: "Delete Checkout Load Test" }).click();
  const deleteDialog = page.getByRole("dialog", { name: "Delete Test Plan" });
  await expect(deleteDialog).toBeVisible();
  await expect(deleteDialog.getByText(/hidden from active lists/)).toBeVisible();
  await deleteDialog.getByRole("button", { name: "Delete", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: "No test plans yet" }),
  ).toBeVisible();
  expect(captures.deleted).toBe(true);
});
