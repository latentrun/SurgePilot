import { expect, test } from "@playwright/test";

const apiPort = process.env.SURGEPILOT_E2E_API_PORT ?? "8000";
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;

async function currentWorkspaceId(page: import("@playwright/test").Page) {
  const response = await page.request.get(`${apiBaseUrl}/api/v1/auth/me`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()).defaultWorkspace.id as string;
}

async function csrfToken(page: import("@playwright/test").Page) {
  const response = await page.request.get(`${apiBaseUrl}/api/v1/auth/csrf`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()).csrfToken as string;
}

async function seedScenario(page: import("@playwright/test").Page, workspaceId: string, csrf: string) {
  const response = await page.request.post(`${apiBaseUrl}/api/v1/scenarios`, {
    headers: { "x-csrf-token": csrf, "x-workspace-id": workspaceId },
    data: {
      name: "P1 preview scenario",
      description: "P1-04 browser smoke",
      tags: ["p1", "preview"],
      baseUrlExpression: "https://example.test",
      defaultSettings: {
        thinkTimeMs: 0,
        timeoutMs: 30000,
        followRedirects: true,
        keepAlive: true,
        storeCache: true,
        storeCookie: true,
        retrieveResources: false,
      },
      dataSources: [],
      steps: [
        {
          id: "01J0000000000000000000001A",
          enabled: true,
          name: "Health",
          method: "GET",
          path: "/health",
          queryParams: [],
          headers: [],
          body: { type: "none", contentType: null, rawText: null, formFields: [] },
          uploadFiles: [],
          extractors: [],
          assertions: [
            {
              id: "01J0000000000000000000001B",
              type: "status_code",
              expectedStatus: 200,
              enabled: true,
            },
          ],
          scripts: [],
          settings: {
            thinkTimeMs: null,
            timeoutMs: null,
            followRedirects: null,
            keepAlive: null,
          },
        },
      ],
    },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

async function seedTestPlan(
  page: import("@playwright/test").Page,
  workspaceId: string,
  csrf: string,
  scenarioId: string,
) {
  const response = await page.request.post(`${apiBaseUrl}/api/v1/test-plans`, {
    headers: { "x-csrf-token": csrf, "x-workspace-id": workspaceId },
    data: {
      name: "P1 polish plan",
      description: "P1-04 browser smoke",
      tags: [],
      envGroupId: null,
      runMode: "sequential",
      resource: { poolType: null, selectedNodeId: null },
      scenarioItems: [
        {
          id: "01J0000000000000000000002A",
          scenarioId,
          enabled: true,
          order: 0,
          loadSettings: {
            concurrencyPerNode: 1,
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
    },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

test("P1-04 Scenario and Test Plan polish surfaces are visible and scoped", async ({ page }) => {
  const email = "p1-polish@example.com";
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("P1 Polish User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/, { timeout: 15_000 });

  const workspaceId = await currentWorkspaceId(page);
  const csrf = await csrfToken(page);
  const scenario = await seedScenario(page, workspaceId, csrf);
  const plan = await seedTestPlan(page, workspaceId, csrf, scenario.id);

  await page.goto(`/scenarios/${scenario.id}`);
  await expect(page.getByRole("heading", { name: "P1 preview scenario" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview YAML" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Generated YAML Preview" })).toHaveCount(0);
  await expect(page.getByText(/Apply YAML|Save YAML|Edit generated YAML|Run from preview/)).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: `Clone ${scenario.name}` }),
  ).toBeVisible();
  await page.getByRole("button", { name: `Archive ${scenario.name}` }).click();
  await expect(page.getByRole("dialog", { name: "Archive Scenario" })).toBeVisible();
  await expect(page.getByText(/hidden from active lists/i)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.goto("/scenarios");
  await expect(page.getByRole("button", { name: "Clone" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Archive" }).first().click();
  await expect(page.getByRole("dialog", { name: "Archive Scenario" })).toBeVisible();
  await expect(page.getByText(/hidden from active lists/i)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.goto("/test-plans");
  await expect(page.getByText("P1 polish plan")).toBeVisible();
  await expect(page.getByText("No tags")).toBeVisible();
  await expect(page.getByRole("button", { name: "Clone" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Archive" }).first().click();
  await expect(page.getByRole("dialog", { name: "Archive Test Plan" })).toBeVisible();
  await expect(page.getByText(/historical Run Reports keep/i)).toBeVisible();

  await page.getByRole("button", { name: "Cancel" }).click();
  await page.goto(`/test-plans/${plan.id}`);
  await expect(page.getByRole("heading", { name: "Generated YAML Preview" })).toBeVisible();
  await expect(page.getByText(/Preview requires a Load Node/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview YAML" })).toBeVisible();
  await expect(page.getByText(/Apply YAML|Save YAML|Edit generated YAML|Run from preview/)).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: `Clone ${plan.name}` }),
  ).toBeVisible();
  await page.getByRole("button", { name: `Archive ${plan.name}` }).click();
  await expect(page.getByRole("dialog", { name: "Archive Test Plan" })).toBeVisible();
  await expect(page.getByText(/historical Run Reports keep/i)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
});
