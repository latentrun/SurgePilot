import { expect, test, type Page, type Route } from "@playwright/test";

const workspaceId = "01HZW000000000000000000000";
const testPlanId = "01J0000000000000000000001P";
const scenarioId = "01J0000000000000000000001S";
const nodeAId = "01J0000000000000000000001A";
const nodeBId = "01J0000000000000000000001B";
const runId = "01J0000000000000000000001R";

const authSession = {
  user: {
    id: "01J0000000000000000000001U",
    email: "p1-resource@example.com",
    displayName: "P1 Resource User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: { id: workspaceId, name: "Default Workspace" },
  csrfToken: "csrf-token",
};

const scenarioSummary = {
  id: scenarioId,
  name: "Checkout flow",
  description: null,
  tags: ["checkout"],
  scenarioType: "visual",
  stepCount: 1,
  enabledStepCount: 1,
  dependencyFileCount: 0,
  revision: 1,
  createdAt: "2030-06-18T08:00:00.000Z",
  updatedAt: "2030-06-18T08:00:00.000Z",
};

const loadNodes = {
  items: [
    {
      id: nodeAId,
      scope: "workspace",
      workspaceId,
      host: "private-node-a.internal",
      sshPort: 22,
      sshUser: "surgepilot",
      runnerHome: "/opt/surgepilot",
      authType: "password",
      credentialConfigured: true,
      credentialFingerprint: "fp-a",
      generatedPublicKey: null,
      maintainer: null,
      remark: null,
      status: "idle",
      lastStatusReason: null,
      runnerVersion: null,
      bundleVersion: null,
      lastInitializedAt: "2030-06-18T08:00:00.000Z",
      lastCheckedAt: "2030-06-18T08:00:00.000Z",
      lastHeartbeatAt: null,
      currentRunId: null,
      lastInitAttemptId: null,
      createdAt: "2030-06-18T08:00:00.000Z",
      updatedAt: "2030-06-18T08:00:00.000Z",
    },
    {
      id: nodeBId,
      scope: "workspace",
      workspaceId,
      host: "private-node-b.internal",
      sshPort: 22,
      sshUser: "surgepilot",
      runnerHome: "/opt/surgepilot",
      authType: "password",
      credentialConfigured: true,
      credentialFingerprint: "fp-b",
      generatedPublicKey: null,
      maintainer: null,
      remark: null,
      status: "idle",
      lastStatusReason: null,
      runnerVersion: null,
      bundleVersion: null,
      lastInitializedAt: "2030-06-18T08:00:00.000Z",
      lastCheckedAt: "2030-06-18T08:00:00.000Z",
      lastHeartbeatAt: null,
      currentRunId: null,
      lastInitAttemptId: null,
      createdAt: "2030-06-18T08:00:00.000Z",
      updatedAt: "2030-06-18T08:00:00.000Z",
    },
  ],
  limit: 100,
  offset: 0,
  total: 2,
};

const testPlanDetail = {
  id: testPlanId,
  name: "P1 multi-node plan",
  description: "P1-01 browser smoke",
  tags: ["p1", "resource"],
  envGroupId: null,
  envGroupName: null,
  runMode: "sequential",
  resource: {
    mode: "manual",
    poolType: "private",
    selectedNodeId: nodeAId,
    selectedNodeIds: [nodeAId],
    nodeCount: null,
  },
  scenarioItems: [
    {
      id: "01J0000000000000000000001I",
      scenarioId,
      scenarioName: scenarioSummary.name,
      scenarioRevision: 1,
      enabledStepCount: 1,
      updatedAt: "2030-06-18T08:00:00.000Z",
      enabled: true,
      order: 0,
      loadSettings: {
        concurrencyPerNode: 10,
        rampUpSeconds: 0,
        holdForSeconds: 60,
        iterations: null,
        targetRps: null,
        steps: null,
        delaySeconds: 0,
      },
    },
  ],
  slaRules: [],
  runGuard: {
    expectedConcurrencyPerNode: 10,
    softConcurrencyPerNodeLimit: 1000,
    hardConcurrencyPerNodeLimit: 10000,
    requiresHighConcurrencyConfirmation: false,
  },
  runnable: true,
  notRunnableReasons: [],
  revision: 1,
};

const runReport = {
  id: runId,
  verdict: {
    state: "finished",
    runType: "standard",
    sourceType: "test_plan",
    validity: "valid",
    slaResult: "passed",
    slaResultReason: null,
    durationMs: 120000,
    triggeredBy: { id: authSession.user.id, email: authSession.user.email },
    createdAt: "2030-06-18T08:10:00.000Z",
    acceptedAt: "2030-06-18T08:10:01.000Z",
    startedAt: "2030-06-18T08:10:02.000Z",
    endedAt: "2030-06-18T08:12:00.000Z",
    lastHeartbeatAt: "2030-06-18T08:11:55.000Z",
    failureReason: null,
    failureMessage: null,
    forcedConvergence: false,
    warnings: [],
  },
  kpiSummary: {
    status: "pending",
    sourceArtifactId: null,
    totalRequests: null,
    failedRequests: null,
    errorRate: null,
    averageResponseTimeMs: null,
    p90Ms: null,
    p95Ms: null,
    p99Ms: null,
    throughputPerSecond: null,
    missingReasons: ["final_stats_missing"],
  },
  failureDiagnostics: {
    failureReason: null,
    failureMessage: null,
    hasFailedRequestsPreview: false,
    notes: [],
  },
  finalStatsPreview: { status: "missing", truncated: false, rows: [] },
  debugHttpTrace: null,
  snapshot: {
    schemaVersion: 1,
    sourceName: testPlanDetail.name,
    sourceRevision: 1,
    envGroupName: null,
    runMode: "sequential",
    scenarioCount: 1,
    scenarioItems: testPlanDetail.scenarioItems.map((item) => ({
      scenarioName: item.scenarioName,
      loadSettings: item.loadSettings,
    })),
    scenarioNames: [scenarioSummary.name],
    slaRuleCount: 0,
    slaRules: [],
    dependencyFileCount: 0,
    dependencyFileNames: [],
    envGroupVariableKeys: [],
    resourceRequest: {
      mode: "manual",
      poolType: "workspace",
      selectedNodeId: nodeAId,
      selectedNodeIds: [nodeAId, nodeBId],
      nodeCount: null,
      expectedConcurrencyPerNode: 10,
    },
  },
  allocatedNodes: [
    {
      id: nodeAId,
      name: "Load Node 0001A",
      scope: "workspace",
      nodeIndex: 1,
      totalNodes: 2,
      state: "finished",
      lastHeartbeatAt: "2030-06-18T08:11:55.000Z",
      terminalReason: "finished",
      cleanupStatus: "released",
      quarantineReason: null,
      slaResult: "passed",
    },
    {
      id: nodeBId,
      name: "Load Node 0001B",
      scope: "workspace",
      nodeIndex: 2,
      totalNodes: 2,
      state: "finished",
      lastHeartbeatAt: "2030-06-18T08:11:55.000Z",
      terminalReason: "finished",
      cleanupStatus: "released",
      quarantineReason: null,
      slaResult: "passed",
    },
  ],
  nodes: [
    {
      id: nodeAId,
      name: "Load Node 0001A",
      scope: "workspace",
      poolType: "workspace",
      nodeIndex: 1,
      totalNodes: 2,
      stateAtReport: "finished",
      lastHeartbeatAt: "2030-06-18T08:11:55.000Z",
      terminalReason: "finished",
      cleanupStatus: "released",
      quarantineReason: null,
      slaResult: "passed",
    },
    {
      id: nodeBId,
      name: "Load Node 0001B",
      scope: "workspace",
      poolType: "workspace",
      nodeIndex: 2,
      totalNodes: 2,
      stateAtReport: "finished",
      lastHeartbeatAt: "2030-06-18T08:11:55.000Z",
      terminalReason: "finished",
      cleanupStatus: "released",
      quarantineReason: null,
      slaResult: "passed",
    },
  ],
  artifactsSummary: {
    count: 0,
    hasArtifactsZip: false,
    hasFinalStatsCsv: false,
    latestAvailableAt: null,
  },
};

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installApiFixtures(page: Page) {
  let runRequestBody: unknown = null;

  await page.route("**/api/v1/auth/me", (route) => json(route, authSession));
  await page.route("**/api/v1/auth/csrf", (route) =>
    json(route, { csrfToken: "csrf-token" }),
  );
  await page.route("**/api/v1/env-groups**", (route) =>
    json(route, { items: [], page: 1, pageSize: 100, total: 0 }),
  );
  await page.route("**/api/v1/scenarios**", (route) =>
    json(route, { items: [scenarioSummary], page: 1, pageSize: 100, total: 1 }),
  );
  await page.route("**/api/v1/load-nodes**", (route) => json(route, loadNodes));
  await page.route(`**/api/v1/test-plans/${testPlanId}`, async (route) => {
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON();
      await json(route, {
        ...testPlanDetail,
        revision: 2,
        resource: body.resource,
        scenarioItems: testPlanDetail.scenarioItems,
        runnable: true,
        notRunnableReasons: [],
      });
      return;
    }
    await json(route, testPlanDetail);
  });
  await page.route("**/api/v1/runs", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      runRequestBody = request.postDataJSON();
      await json(
        route,
        {
          id: runId,
          state: "initializing",
          runType: "standard",
          sourceType: "test_plan",
          sourceId: testPlanId,
          selectedNodeId: nodeAId,
          validity: "valid",
          createdAt: "2030-06-18T08:10:00.000Z",
          deduplicated: false,
        },
        201,
      );
      return;
    }
    await route.fallback();
  });
  await page.route(`**/api/v1/runs/${runId}/artifacts**`, (route) =>
    json(route, { items: [], page: 1, pageSize: 20, total: 0 }),
  );
  await page.route(`**/api/v1/runs/${runId}`, (route) => json(route, runReport));

  return () => runRequestBody;
}

test("P1-01 manual two-node Standard Run request and report allocation display", async ({
  page,
}) => {
  const getRunRequestBody = await installApiFixtures(page);

  await page.goto(`/test-plans/${testPlanId}`);
  await expect(page.getByRole("textbox", { name: "Test Plan name" })).toHaveValue("P1 multi-node plan");
  await page.getByRole("button", { name: "Select nodes" }).click();
  const nodeDialog = page.getByRole("dialog", { name: "Select Load Nodes" });
  const nodeACheckbox = nodeDialog.getByRole("checkbox", {
    name: /private-node-a\.internal · idle/i,
  });
  const nodeBCheckbox = nodeDialog.getByRole("checkbox", {
    name: /private-node-b\.internal · idle/i,
  });
  await expect(nodeACheckbox).toBeChecked();
  await nodeBCheckbox.check();
  await expect(nodeBCheckbox).toBeChecked();
  await nodeDialog.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("2 nodes selected")).toBeVisible();
  await page.getByRole("button", { name: "Run Now" }).first().click();

  await expect(page).toHaveURL(new RegExp(`/runs/${runId}$`));
  expect(getRunRequestBody()).toMatchObject({
    runType: "standard",
    sourceType: "test_plan",
    sourceId: testPlanId,
    expectedSourceRevision: 2,
    resourceRequest: {
      mode: "manual",
      selectedNodeIds: [nodeAId, nodeBId],
      concurrencyPerNode: 10,
    },
  });

  await expect(page.getByRole("heading", { name: "Run Report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Nodes" })).toBeVisible();
  await expect(page.getByText("Load Node 0001A")).toBeVisible();
  await expect(page.getByText("Load Node 0001B")).toBeVisible();
  await expect(page.getByText(/Node 1 of 2/)).toBeVisible();
  await expect(page.getByText(/Node 2 of 2/)).toBeVisible();
  await expect(page.getByText("Manual")).toBeVisible();
});
