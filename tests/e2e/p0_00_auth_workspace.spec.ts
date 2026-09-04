import { expect, test } from "@playwright/test";

test("setup status to first admin registration to overview logout and login", async ({
  page,
}) => {
  const email = "admin@example.com";
  const password = "password123";

  await page.goto("/register");

  await expect(
    page.getByRole("heading", { name: "Create administrator" }),
  ).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Admin User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create administrator" }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await expect(
    page.getByRole("heading", { name: "Welcome to SurgePilot" }),
  ).toBeVisible();
  await expect(page.getByRole("main").getByText("Admin User")).toBeVisible();
  await expect(
    page.getByRole("main").getByText("Default Workspace", { exact: true }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", { name: "Sign in" }),
  ).toBeVisible();

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await expect(
    page.getByRole("heading", { name: "Welcome to SurgePilot" }),
  ).toBeVisible();
  await expect(page.getByRole("main").getByText("Admin User")).toBeVisible();
  await expect(
    page.getByRole("main").getByText("Default Workspace", { exact: true }),
  ).toBeVisible();
});
