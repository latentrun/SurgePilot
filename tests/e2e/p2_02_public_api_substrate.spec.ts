import { expect, test } from "@playwright/test";

test("user creates a personal API key and uses it for public API read", async ({ page, request }) => {
  const suffix = Date.now();
  const email = `p2-02-api-key-${suffix}@example.com`;
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("API Key User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  await page.goto("/account/api-keys");
  await expect(page.getByRole("heading", { name: "API Keys" })).toBeVisible();
  const workspaceId = await page.locator('select[aria-label="Current Workspace"]').inputValue();
  await expect(page.locator("code").filter({ hasText: workspaceId })).toHaveText(workspaceId);
  await page.getByRole("button", { name: "Copy Workspace ID" }).click();
  await expect(page.getByRole("button", { name: "Workspace ID copied" })).toHaveText("Copied");

  await page.getByRole("button", { name: "Create API Key" }).click();
  const dialog = page.getByRole("dialog", { name: "Create API Key" });
  await dialog.getByLabel("Name").fill("E2E reader");
  await dialog.getByLabel("Read").check();
  await dialog.getByRole("button", { name: "Create key" }).click();
  await expect(dialog.getByText("Copy this token now. It will not be shown again.")).toBeVisible();
  const plaintext = (await dialog.locator("code").innerText()).trim();
  expect(plaintext).toMatch(/^surgepilot_pat_/);

  const publicResponse = await request.get("/api/public/v1/scenarios", {
    headers: { Authorization: `Bearer ${plaintext}`, "x-workspace-id": workspaceId },
  });
  expect(publicResponse.status()).toBe(200);
  expect(await publicResponse.json()).toMatchObject({ items: [], page: 1, total: 0 });
});
