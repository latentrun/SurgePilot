import { expect, test } from "@playwright/test";

const apiPort = process.env.SURGEPILOT_E2E_API_PORT ?? "8000";
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;

test("Test Plan list columns and Global Context layout stay aligned", async ({
  page,
}) => {
  await page.goto("/register");
  await page.getByLabel("Email").fill("test-plan-layout@example.com");
  await page.getByLabel("Display name").fill("Test Plan Layout User");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  const sessionResponse = await page.request.get(
    `${apiBaseUrl}/api/v1/auth/me`,
  );
  const csrfResponse = await page.request.get(`${apiBaseUrl}/api/v1/auth/csrf`);
  expect(sessionResponse.ok()).toBeTruthy();
  expect(csrfResponse.ok()).toBeTruthy();
  const workspaceId = (await sessionResponse.json()).defaultWorkspace
    .id as string;
  const csrfToken = (await csrfResponse.json()).csrfToken as string;

  const testPlanResponse = await page.request.post(
    `${apiBaseUrl}/api/v1/test-plans`,
    {
      headers: { "x-csrf-token": csrfToken, "x-workspace-id": workspaceId },
      data: {
        name: "Layout verification plan",
        description: "Browser coverage for Test Plan layout",
        tags: [],
        envGroupId: null,
        runMode: "sequential",
        resource: { poolType: null, selectedNodeId: null },
        scenarioItems: [],
        slaRules: [],
      },
    },
  );
  expect(testPlanResponse.status()).toBe(201);
  const testPlan = await testPlanResponse.json();

  await page.goto("/test-plans");
  await expect(page.getByText("Layout verification plan")).toBeVisible();
  const updatedHeader = page.getByText("Updated", { exact: true });
  const actionsHeader = page.getByText("Actions", { exact: true });
  await expect(updatedHeader).toBeVisible();
  await expect(updatedHeader.locator("..").locator(":scope > span")).toHaveText([
    "Name",
    "Mode",
    "Scenarios",
    "Concurrency",
    "Updated",
    "Actions",
  ]);
  await expect(page.getByText("Env", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Node", { exact: true })).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  const listGrid = page.getByTestId("test-plan-list-grid");
  await expect(listGrid).toBeVisible();
  expect(
    await listGrid.evaluate(
      (element) => getComputedStyle(element).overflowX === "auto",
    ),
  ).toBe(true);
  expect(
    await listGrid.evaluate(
      (element) => element.scrollWidth > element.clientWidth,
    ),
  ).toBe(true);
  await expect(actionsHeader).toBeVisible();

  await page.goto(`/test-plans/${testPlan.id}`);
  const envGroupSelect = page.getByLabel("Env Group");
  const runModeSelect = page.getByLabel("Run Mode");
  await expect(envGroupSelect).toBeVisible();
  await expect(runModeSelect).toBeVisible();
  const envGroupBox = await envGroupSelect.boundingBox();
  const runModeBox = await runModeSelect.boundingBox();

  expect(envGroupBox).not.toBeNull();
  expect(runModeBox).not.toBeNull();
  expect(runModeBox!.y).toBeGreaterThan(envGroupBox!.y + envGroupBox!.height);
});
