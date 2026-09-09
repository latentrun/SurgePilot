import { expect, test } from "@playwright/test";

async function ensureAdminSession(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  if (await page.url().then((url) => /\/overview$/.test(url))) return;

  await page.goto("/register");
  await page.getByLabel("Email").fill("admin@example.com");
  await page.getByLabel("Display name").fill("Admin User");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);
}

test("admin creates and switches workspaces without leaking the previous view", async ({ page }) => {
  await ensureAdminSession(page);

  await page.goto("/admin/workspaces");
  await expect(page.getByRole("heading", { name: "Workspaces" })).toBeVisible();
  const name = `Workspace B ${Date.now()}`;
  await page.getByPlaceholder("Workspace name").fill(name);
  await page.getByRole("button", { name: "Create Workspace" }).click();
  await expect(page.getByRole("main").getByText(name, { exact: true })).toBeVisible();

  await page.getByLabel("Current Workspace").selectOption({ label: name });
  await expect(page).toHaveURL(/\/overview$/);
  await expect(page.getByRole("main").getByText(name, { exact: true })).toBeVisible();
  await expect(page.getByRole("main").getByText("Default Workspace", { exact: true })).toHaveCount(0);
});

test("system settings exposes policy controls and configured status only", async ({ page }) => {
  await ensureAdminSession(page);
  await page.goto("/admin/system-settings");
  await expect(page.getByRole("heading", { name: "System Settings" })).toBeVisible();
  await expect(page.getByLabel("JMeter memory Xmx")).toBeVisible();
  await expect(page.getByText("Runner internal token")).toBeVisible();
  await expect(page.getByText(/single node concurrency hard limit/i)).toHaveCount(0);
  await expect(page.getByText(/monitoring token/i)).toHaveCount(0);
});
