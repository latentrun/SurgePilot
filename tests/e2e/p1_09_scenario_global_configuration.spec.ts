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

async function seedScenario(
  page: import("@playwright/test").Page,
  workspaceId: string,
  csrf: string,
) {
  const response = await page.request.post(`${apiBaseUrl}/api/v1/scenarios`, {
    headers: { "x-csrf-token": csrf, "x-workspace-id": workspaceId },
    data: {
      name: "P1 global config scenario",
      description: "P1-09 browser smoke",
      tags: ["p1", "global-config"],
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
      globalHeaders: [],
      variables: [
        {
          id: "01J0000000000000000000091A",
          name: "base_url",
          value: "https://scenario.example.test",
          enabled: true,
        },
      ],
      dataSources: [],
      steps: [
        {
          id: "01J0000000000000000000091B",
          enabled: true,
          name: "Health",
          method: "GET",
          path: "/health",
          queryParams: [],
          headers: [],
          body: {
            type: "none",
            contentType: null,
            rawText: null,
            formFields: [],
          },
          uploadFiles: [],
          extractors: [],
          assertions: [],
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

test("P1-09 Scenario Global Configuration persists headers and variables", async ({
  page,
}) => {
  const email = "p1-global-config@example.com";
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("P1 Global Config User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  const workspaceId = await currentWorkspaceId(page);
  const csrf = await csrfToken(page);
  const scenario = await seedScenario(page, workspaceId, csrf);

  await page.goto(`/scenarios/${scenario.id}`);
  await expect(
    page.getByRole("heading", { name: "P1 global config scenario" }),
  ).toBeVisible();
  await page
    .getByTestId("scenario-designer-header")
    .getByRole("button", { name: "Global Config" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Global Configuration" });
  await expect(dialog.getByRole("tab", { name: "Settings" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await dialog.getByRole("tab", { name: "Headers" }).click();
  await expect(dialog.getByText("No global headers.")).toBeVisible();
  await dialog.getByRole("button", { name: "Add global header" }).click();
  await dialog.getByLabel("Global header 1 name").fill("X-API-Version");
  await dialog.getByLabel("Global header 1 value").fill("${api_version}");
  await dialog.getByRole("tab", { name: "Variables" }).click();
  await dialog.getByRole("button", { name: "Add variable" }).click();
  await dialog.getByLabel("Scenario variable 2 name").fill("api_version");
  await dialog.getByLabel("Scenario variable 2 value").fill("v1");
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(page.getByText("Unsaved changes")).toBeVisible();
  const header = page.getByTestId("scenario-designer-header");
  await header.getByRole("button", { name: "Save" }).click();
  await expect(header.getByText("Saved", { exact: true })).toBeVisible();

  const response = await page.request.get(
    `${apiBaseUrl}/api/v1/scenarios/${scenario.id}`,
    { headers: { "x-workspace-id": workspaceId } },
  );
  expect(response.ok()).toBeTruthy();
  const saved = await response.json();
  expect(saved.globalHeaders).toEqual([
    expect.objectContaining({
      name: "X-API-Version",
      value: "${api_version}",
      enabled: true,
    }),
  ]);
  expect(saved.variables).toEqual([
    expect.objectContaining({ name: "base_url", enabled: true }),
    expect.objectContaining({
      name: "api_version",
      value: "v1",
      enabled: true,
    }),
  ]);
  await expect(
    page.getByText(/Apply YAML|Edit YAML|Import YAML|globalScripts/i),
  ).toHaveCount(0);
});
