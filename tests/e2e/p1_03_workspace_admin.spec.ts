import { expect, test } from "@playwright/test";

const adminEmail = "admin@example.com";
const adminPassword = "password123";

async function ensureAdminSession(page: import("@playwright/test").Page) {
  await page.goto("/register");
  if (
    await page.getByLabel("Email").waitFor({ state: "visible", timeout: 5_000 }).then(
      () => true,
      () => false,
    )
  ) {
    await page.getByLabel("Email").fill(adminEmail);
    await page.getByLabel("Display name").fill("Admin User");
    await page.getByLabel("Password").fill(adminPassword);
    await page
      .getByRole("button", { name: /Create (Administrator|account)/ })
      .click();
    if (
      await page.waitForURL(/\/overview$/, { timeout: 5_000 }).then(
        () => true,
        () => false,
      )
    ) {
      return;
    }
  }

  await page.goto("/login");
  await page.getByLabel("Email").fill(adminEmail);
  await page.getByLabel("Password").fill(adminPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/overview$/);
}

test("admin creates and switches workspaces without leaking the previous workspace view", async ({
  page,
}) => {
  const workspaceName = `Workspace B ${Date.now()}`;
  await ensureAdminSession(page);

  await page.goto("/admin/workspaces");
  await expect(
    page.getByRole("heading", { name: "Workspaces" }),
  ).toBeVisible();
  await page.getByPlaceholder("Workspace name").fill(workspaceName);
  await page.getByRole("button", { name: "Create Workspace" }).click();
  await expect(
    page.getByRole("main").getByText(workspaceName, { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Current Workspace")).toContainText(workspaceName);

  await page.getByLabel("Current Workspace").selectOption({ label: workspaceName });
  await expect(page).toHaveURL(/\/overview$/);
  await expect(
    page.getByRole("main").getByText(workspaceName, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("main").getByText("Default Workspace", { exact: true }),
  ).toHaveCount(0);

  await page.getByLabel("Current Workspace").selectOption({
    label: "Default Workspace",
  });
  await expect(
    page.getByRole("main").getByText("Default Workspace", { exact: true }),
  ).toBeVisible();
});

test("admin system settings exposes only accepted policy controls", async ({ page }) => {
  await ensureAdminSession(page);

  await page.goto("/admin/system-settings");
  await expect(
    page.getByRole("heading", { name: "System Settings" }),
  ).toBeVisible();
  await expect(page.getByLabel("Allow local signup")).toBeVisible();
  await expect(page.getByLabel("JMeter memory Xmx")).toBeVisible();
  await expect(
    page.getByLabel("Max Scenario items per Test Plan"),
  ).toBeVisible();
  await expect(
    page.getByLabel("Dependency file allowed extensions"),
  ).toBeVisible();
  await expect(page.getByText("Runner internal token")).toBeVisible();
  await expect(page.getByText("SSH credential encryption key")).toBeVisible();
  await expect(page.getByText("MinIO credentials")).toBeVisible();
  await expect(
    page.getByText(/single node concurrency hard limit/i),
  ).toHaveCount(0);
  await expect(page.getByText(/monitoring token/i)).toHaveCount(0);
  await expect(page.getByText(/grafana/i)).toHaveCount(0);
  await expect(page.getByText(/influx/i)).toHaveCount(0);
});
