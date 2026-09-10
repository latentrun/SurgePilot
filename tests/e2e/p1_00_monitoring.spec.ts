import { expect, test } from "@playwright/test";

const workspaceId = "01J00000000000000000000002";
const runId = "01J00000000000000000000003";

test("Monitoring page embeds the same-origin Grafana dashboard", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "01J00000000000000000000001",
          email: "monitoring@example.com",
          displayName: "Monitoring User",
          role: "admin",
          status: "active",
        },
        defaultWorkspace: { id: workspaceId, name: "Default Workspace" },
        csrfToken: "csrf-token",
      }),
    });
  });
  await page.route("**/api/v1/monitoring/embed**", async (route) => {
    const url = new URL(route.request().url());
    expect(route.request().headers()["x-workspace-id"]).toBe(workspaceId);
    expect(url.searchParams.get("runId")).toBe(runId);
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        enabled: true,
        status: "ready",
        iframeUrl: `/grafana/d/surgepilot-jmeter/jmeter-load-test?orgId=1&kiosk&theme=dark&var-runId=${runId}&from=1906703945000&to=1906704370000`,
        runId,
        from: "1906703945000",
        to: "1906704370000",
        dashboardUid: "surgepilot-jmeter",
        warnings: [],
      }),
    });
  });
  await page.route("**/grafana/**", async (route) => {
    await route.fulfill({
      contentType: "text/html",
      body: "<html><body>Grafana placeholder</body></html>",
    });
  });

  await page.goto(
    `/observability/monitoring?runId=${runId}&from=1906703945000&to=1906704370000`,
  );

  await expect(page.getByRole("heading", { name: "Monitoring" })).toBeVisible();
  await expect(
    page
      .frameLocator('iframe[title="Grafana monitoring dashboard"]')
      .getByText("Grafana placeholder"),
  ).toBeVisible();
  await expect(
    page.getByText(/token|internal url|node write|influxdb/i),
  ).toHaveCount(0);
});
