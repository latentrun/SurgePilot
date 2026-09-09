import { expect, test } from "@playwright/test";

test("Debug Run Report exposes sanitized HTTP Trace and no later-scope navigation", async ({ page }) => {
  await page.route("**/api/v1/auth/me", async (route) => {
    await route.fulfill({
      json: {
        user: { id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A", email: "debug@example.com", displayName: "Debug User", role: "admin", status: "active" },
        defaultWorkspace: { id: "01HZW000000000000000000000", name: "Default Workspace" },
      },
    });
  });
  await page.route("**/api/v1/runs/debug-trace-report", async (route) => {
    await route.fulfill({
      json: {
        id: "debug-trace-report",
        verdict: { state: "finished", runType: "debug", sourceType: "debug_scenario", validity: "invalid", slaResult: "not_evaluated", slaResultReason: null, durationMs: 123, triggeredBy: { email: "debug@example.com" }, createdAt: "2030-06-01T09:00:00Z", startedAt: "2030-06-01T09:00:01Z", endedAt: "2030-06-01T09:00:02Z", lastHeartbeatAt: "2030-06-01T09:00:02Z", failureReason: null, forcedConvergence: false },
        kpiSummary: { status: "missing", totalRequests: null, failedRequests: null, errorRate: null, averageResponseTimeMs: null, p90Ms: null, p95Ms: null, p99Ms: null },
        failureDiagnostics: { failureMessage: null, failureReason: null, hasFailedRequestsPreview: false },
        finalStatsPreview: { status: "missing", rows: [], truncated: false },
        debugHttpTrace: { status: "available", sourceArtifactId: "internal-only", entryCount: 1, traceTruncated: false, warnings: [], entries: [{ sequence: 1, label: "Login", method: "GET", url: "https://example.test/login", requestHeaders: { Authorization: "[REDACTED]" }, requestBody: { contentType: "application/json", text: "{}" }, responseStatus: 200, responseHeaders: {}, responseBody: { contentType: "application/json", text: "{\"ok\":true}" }, durationMs: 12, error: null }] },
        snapshot: { scenarioCount: 1, slaRuleCount: 0, dependencyFileCount: 0, sourceName: "Debug scenario", sourceRevision: 1, envGroupName: "Staging", runMode: "sequential", resourceRequest: { mode: "manual", poolType: "workspace", selectedNodeId: "node-1", expectedConcurrencyPerNode: 1 } },
        artifactsSummary: { count: 0, hasArtifactsZip: false, hasFinalStatsCsv: false, latestAvailableAt: null },
      },
    });
  });
  await page.goto("/runs/debug-trace-report");

  await expect(page.getByRole("heading", { name: "HTTP Trace" })).toBeVisible();
  await expect(page.getByText("Authorization: [REDACTED]")).toBeVisible();
  await expect(page.getByText("Monitoring")).toHaveCount(0);
  await expect(page.getByText("[REDACTED]")).toBeVisible();
});
