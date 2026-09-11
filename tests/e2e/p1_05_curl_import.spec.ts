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
      name: "cURL import smoke",
      description: "P1-05 browser smoke",
      tags: ["p1", "import"],
      baseUrlExpression: "${base_url}",
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
      steps: [],
    },
  });
  expect(response.status()).toBe(201);
  return response.json();
}

test("authenticated user imports a cURL command into a Scenario draft", async ({ page }) => {
  const email = "curl-import@example.com";
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("cURL Import User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/, { timeout: 15_000 });

  const workspaceId = await currentWorkspaceId(page);
  const csrf = await csrfToken(page);
  const scenario = await seedScenario(page, workspaceId, csrf);

  await page.goto(`/scenarios/${scenario.id}`);
  await expect(
    page.getByRole("heading", { name: "cURL import smoke" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Import cURL" }).click();
  await page.getByLabel("cURL command").fill(
    "curl -H 'Authorization: Bearer token' --data '{\"sku\":\"A1\"}' https://api.example.test/v1/orders?region=sg",
  );
  await page.getByRole("button", { name: "Preview import" }).click();

  await expect(page.getByText("POST /v1/orders")).toBeVisible();
  await expect(page.getByText("region=sg", { exact: true })).toBeVisible();
  await expect(page.getByText("Sensitive information warning")).toBeVisible();
  await page.getByLabel("Apply to Global Config").check();
  await page.getByRole("button", { name: "Import Step" }).click();

  await expect(page.getByText("Unsaved changes")).toBeVisible();
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await expect(
    page.getByText("https://api.example.test", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("POST /v1/orders").first()).toBeVisible();
});
