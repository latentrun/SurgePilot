import { expect, test } from "@playwright/test";

test("authenticated user creates edits duplicates and deletes Env Groups", async ({ page }) => {
  const email = "envgroups@example.com";
  const password = "password123";

  await page.goto("/register");

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Env Groups User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/assets/env-groups");
  await expect(page.getByRole("heading", { name: "Env Groups", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "New Env Group" }).click();
  await page.getByLabel("Name").fill("Staging");
  await page.getByLabel("Description").fill("Staging variables");
  await page.getByRole("button", { name: "Add variable" }).click();
  await page.getByLabel("Key").fill("BASE_URL");
  await page.getByLabel("Value").fill("https://example.test");
  await page.getByRole("button", { name: "Save Env Group" }).click();

  await expect(page.getByText("Staging", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Edit Staging" }).click();
  await expect(page.locator('input[value="BASE_URL"]')).toBeVisible();
  await page.locator('input[value="https://example.test"]').fill("https://staging.example.test");
  await page.getByRole("button", { name: "Save Env Group" }).click();

  await expect(page.getByRole("button", { name: "Edit Staging" })).toBeVisible();
  await page.getByRole("button", { name: "Duplicate Staging" }).click();
  await expect(page.getByText("Copy of Staging", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Delete Copy of Staging" }).click();
  await expect(page.getByText("Delete Copy of Staging? This action cannot be undone.")).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();

  await expect(page.getByText("Copy of Staging", { exact: true })).toBeHidden();
  await expect(page.getByText("Staging", { exact: true })).toBeVisible();
});
