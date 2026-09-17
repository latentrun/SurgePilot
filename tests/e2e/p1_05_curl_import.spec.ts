import { expect, test } from "@playwright/test";

test("authenticated user imports a cURL command into a Scenario draft", async ({
  page,
}) => {
  const email = "curl-import@example.com";
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("cURL Import User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/scenarios");
  await expect(
    page.getByRole("heading", { name: "Scenarios", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Create Scenario" }).first().click();
  await page.getByLabel("Scenario name").fill("cURL import smoke");
  await page.getByRole("button", { name: "Create", exact: true }).click();

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
  await expect(page.getByText("POST /v1/orders")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await expect(
    page.getByTestId("scenario-designer-summary").getByText("https://api.example.test"),
  ).toBeVisible();
  await expect(page.getByText("/v1/orders").first()).toBeVisible();
});
