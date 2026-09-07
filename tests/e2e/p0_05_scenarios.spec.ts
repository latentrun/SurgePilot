import { expect, test } from "@playwright/test";

const workspaceId = "01HZW000000000000000000000";
const scenarioId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";
const envGroupId = "01HZX3Y9M0E9W7Z6M5QK9S8P7B";
const nodeId = "01HZX3Y9M0E9W7Z6M5QK9S8P7N";
const runId = "01HZX3Y9M0E9W7Z6M5QK9S8P7R";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "scenarios@example.com",
    displayName: "Scenario User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: workspaceId,
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

const defaultSettings = {
  thinkTimeMs: 0,
  timeoutMs: 30000,
  followRedirects: true,
  keepAlive: true,
  storeCache: true,
  storeCookie: true,
  retrieveResources: false,
};

function scenarioDetail(overrides: Record<string, unknown> = {}) {
  return {
    id: scenarioId,
    name: "Checkout smoke",
    description: null,
    tags: ["checkout"],
    scenarioType: "visual",
    stepCount: 0,
    enabledStepCount: 0,
    dependencyFileCount: 0,
    revision: 1,
    baseUrlExpression: "${base_url}",
    defaultSettings,
    dataSources: [],
    steps: [],
    createdAt: "2030-06-01T09:00:00Z",
    updatedAt: "2030-06-01T09:00:00Z",
    ...overrides,
  };
}

const idleNode = {
  id: nodeId,
  scope: "workspace",
  workspaceId,
  host: "debug-node-smoke.internal",
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

const stagingEnvGroup = {
  id: envGroupId,
  name: "Staging",
  description: "Staging environment",
  variableCount: 1,
  inUse: false,
  createdBy: authSession.user.id,
  updatedBy: authSession.user.id,
  createdAt: "2030-06-01T07:00:00Z",
  updatedAt: "2030-06-01T07:00:00Z",
};

function summaryFromDetail(detail: Record<string, unknown>) {
  return {
    id: detail.id,
    name: detail.name,
    description: detail.description,
    tags: detail.tags,
    scenarioType: detail.scenarioType,
    stepCount: detail.stepCount,
    enabledStepCount: detail.enabledStepCount,
    dependencyFileCount: detail.dependencyFileCount,
    revision: detail.revision,
    createdAt: detail.createdAt,
    updatedAt: detail.updatedAt,
  };
}

function enabledStepCount(steps: unknown[]) {
  return steps.filter(
    (step) => (step as { enabled?: boolean }).enabled !== false,
  ).length;
}

test("creates a Scenario and starts a Scenario Debug Run", async ({ page }) => {
  let storedDetail: Record<string, unknown> | null = null;
  let createPayload: Record<string, unknown> | null = null;
  let savePayload: Record<string, unknown> | null = null;
  let debugRunPayload: Record<string, unknown> | null = null;
  let deleted = false;

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
    if (url.pathname === "/api/v1/setup/status") {
      await route.fulfill({
        json: {
          needsBootstrap: false,
          allowSignup: true,
          hasDefaultWorkspace: true,
          storageAvailable: true,
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/scenarios" && method === "POST") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      const payload = request.postDataJSON() as Record<string, unknown>;
      createPayload = payload;
      storedDetail = scenarioDetail({
        name: payload.name,
        tags: payload.tags,
        baseUrlExpression: payload.baseUrlExpression,
      });
      await route.fulfill({ status: 201, json: storedDetail });
      return;
    }
    if (url.pathname === "/api/v1/scenarios" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      const detail = storedDetail;
      const items =
        detail !== null && !deleted ? [summaryFromDetail(detail)] : [];
      await route.fulfill({
        json: { items, page: 1, pageSize: 20, total: items.length },
      });
      return;
    }
    if (url.pathname === `/api/v1/scenarios/${scenarioId}` && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      const detail = storedDetail ?? scenarioDetail();
      await route.fulfill({ json: detail });
      return;
    }
    if (
      url.pathname === `/api/v1/scenarios/${scenarioId}` &&
      method === "PATCH"
    ) {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      const payload = request.postDataJSON() as Record<string, unknown>;
      savePayload = payload;
      const steps = (payload.steps ?? []) as unknown[];
      storedDetail = {
        ...(storedDetail ?? scenarioDetail()),
        ...payload,
        stepCount: steps.length,
        enabledStepCount: enabledStepCount(steps),
        revision: (payload.expectedRevision as number) + 1,
        updatedAt: "2030-06-01T09:30:00Z",
      };
      await route.fulfill({ json: storedDetail });
      return;
    }
    if (
      url.pathname === `/api/v1/scenarios/${scenarioId}` &&
      method === "DELETE"
    ) {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      deleted = true;
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
    if (url.pathname === "/api/v1/dependency-files" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({
        json: { items: [], page: 1, pageSize: 100, total: 0 },
      });
      return;
    }
    if (url.pathname === "/api/v1/load-nodes" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      const params = new URL(request.url()).searchParams;
      const nodes = params.get("status") === "idle" ? [idleNode] : [];
      await route.fulfill({
        json: { items: nodes, limit: 100, offset: 0, total: nodes.length },
      });
      return;
    }
    if (url.pathname === "/api/v1/runs" && method === "POST") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      debugRunPayload = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 201,
        json: {
          id: runId,
          state: "initializing",
          runType: "debug",
          sourceType: "debug_scenario",
          sourceId: scenarioId,
          selectedNodeId: nodeId,
          createdAt: "2030-06-01T09:31:00Z",
          deduplicated: false,
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { code: "RESOURCE_NOT_FOUND" } });
  });

  await page.goto("/scenarios");
  await expect(page.getByRole("heading", { name: "Scenarios" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No scenarios yet" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Create Scenario" }).first().click();
  await expect(
    page.getByRole("dialog", { name: "Create Scenario" }),
  ).toBeVisible();
  await page.getByLabel("Scenario name").fill("Checkout smoke");
  await page.getByLabel("Tags").fill("checkout, smoke");
  await page.getByRole("button", { name: "Create", exact: true }).click();

  await expect(page.getByRole("heading", { name: "Checkout smoke" })).toBeVisible();
  expect(createPayload).toMatchObject({
    name: "Checkout smoke",
    baseUrlExpression: "${base_url}",
    tags: ["checkout", "smoke"],
  });

  await page.getByRole("button", { name: "Add Step" }).first().click();
  await expect(page.getByLabel("Path")).toHaveValue("/");
  await page.getByLabel("Path").fill("/health");
  await expect(page.getByText("Unsaved changes")).toBeVisible();
  await expect(page.getByText("Revision 1")).toBeVisible();

  await page.getByRole("button", { name: "Debug", exact: true }).click();
  const debugDialog = page.getByRole("dialog", { name: "Debug Run" });
  await expect(debugDialog).toBeVisible();
  await expect(
    debugDialog.getByText("1 virtual user · 1 iteration"),
  ).toBeVisible();

  await page.getByLabel("Debug Environment").locator("option").first().waitFor();
  await page.getByLabel("Debug Environment").selectOption(envGroupId);
  await expect(page.getByLabel("Load Node")).toContainText(
    "debug-node-smoke.internal",
  );
  await page.getByLabel("Load Node").selectOption(nodeId);
  await page.getByRole("button", { name: "Start Debug Run" }).click();

  await expect(page).toHaveURL(/\/runs\/01HZX3Y9M0E9W7Z6M5QK9S8P7R$/);
  await expect(
    page.getByRole("heading", { name: "Debug Run started" }),
  ).toBeVisible();

  expect(savePayload).toMatchObject({
    expectedRevision: 1,
    name: "Checkout smoke",
  });
  expect((savePayload?.steps as unknown[] | undefined)?.length).toBe(1);
  const savedSteps = (savePayload?.steps ?? []) as Array<
    Record<string, unknown>
  >;
  expect(savedSteps[0]).toMatchObject({ method: "GET", path: "/health" });
  expect(debugRunPayload).toEqual({
    runType: "debug",
    sourceType: "debug_scenario",
    sourceId: scenarioId,
    expectedSourceRevision: 2,
    envGroupId,
    selectedNodeId: nodeId,
  });

  await page.getByRole("link", { name: "Scenarios" }).click();
  await expect(page.getByRole("link", { name: "Checkout smoke" })).toBeVisible();

  await page.getByRole("button", { name: "Delete Checkout smoke" }).click();
  await expect(
    page.getByRole("dialog", { name: "Delete Scenario" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No scenarios yet" }),
  ).toBeVisible();
});
