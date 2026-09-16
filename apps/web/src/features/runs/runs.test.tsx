import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import type { RunReportDetail } from "../../app/api-client";
import { runReportRefetchInterval } from "./pages/run-report-page";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "runs@example.com",
    displayName: "Runs User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: "01HZW000000000000000000000",
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

const runListItem = {
  id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
  state: "finished",
  runType: "standard",
  sourceType: "test_plan",
  sourceId: "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
  sourceName: "Checkout Load Test",
  sourceRevision: 4,
  tags: ["checkout"],
  validity: "valid",
  slaResult: "failed",
  triggeredBy: { id: authSession.user.id, email: authSession.user.email },
  selectedNode: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
    name: "Load Node S8P7N",
    scope: "workspace",
  },
  allocatedNodeCount: 2,
  createdAt: "2030-06-03T08:00:00.000Z",
  startedAt: "2030-06-03T08:00:05.000Z",
  endedAt: "2030-06-03T08:05:10.000Z",
  durationMs: 305000,
  artifactCount: 2,
  hasArtifactsZip: true,
};

const olderRunListItem = {
  ...runListItem,
  id: "01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
  sourceName: "Checkout Baseline",
  createdAt: "2030-06-02T08:00:00.000Z",
  hasArtifactsZip: false,
};

const reportDetail = {
  id: runListItem.id,
  verdict: {
    state: "finished",
    runType: "standard",
    sourceType: "test_plan",
    validity: "valid",
    slaResult: "failed",
    slaResultReason: null,
    durationMs: 305000,
    triggeredBy: { id: authSession.user.id, email: authSession.user.email },
    createdAt: "2030-06-03T08:00:00.000Z",
    acceptedAt: "2030-06-03T08:00:02.000Z",
    startedAt: "2030-06-03T08:00:05.000Z",
    endedAt: "2030-06-03T08:05:10.000Z",
    lastHeartbeatAt: "2030-06-03T08:05:00.000Z",
    failureReason: null,
    failureMessage: null,
    forcedConvergence: false,
    warnings: [],
  },
  kpiSummary: {
    status: "parsed",
    sourceArtifactId: "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
    totalRequests: 1200,
    failedRequests: 12,
    errorRate: 0.01,
    averageResponseTimeMs: 153.2,
    p90Ms: 420,
    p95Ms: 610,
    p99Ms: 950,
    throughputPerSecond: null,
    missingReasons: [],
  },
  failureDiagnostics: {
    failureReason: null,
    failureMessage: null,
    hasFailedRequestsPreview: false,
    notes: [],
  },
  finalStatsPreview: {
    status: "parsed",
    truncated: false,
    rows: [
      {
        label: "GET /checkout",
        totalRequests: 400,
        successRequests: 396,
        failedRequests: 4,
        errorRate: 0.01,
        averageResponseTimeMs: 188.4,
        p90Ms: 500,
        p95Ms: 700,
        p99Ms: 980,
        responseCodeCounts: { "200": 396, "500": 4 },
      },
    ],
  },
  debugHttpTrace: null,
  snapshot: {
    schemaVersion: 1,
    sourceName: "Checkout Load Test",
    sourceRevision: 4,
    envGroupName: "Staging",
    runMode: "sequential",
    scenarioCount: 1,
    scenarioItems: [
      {
        scenarioName: "Checkout scenario",
        loadSettings: {
          concurrencyPerNode: 10,
          rampUpSeconds: 30,
          holdForSeconds: 300,
          iterations: null,
          targetRps: 50,
          steps: 5,
          delaySeconds: 7,
        },
      },
    ],
    slaRuleCount: 1,
    slaRules: [{ metric: "p95", condition: "lte", thresholdText: "500ms" }],
    dependencyFileCount: 0,
    dependencyFileNames: ["users.csv"],
    envGroupVariableKeys: ["API_TOKEN", "BASE_URL"],
    resourceRequest: {
      mode: "manual",
      poolType: "workspace",
      selectedNodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
      selectedNodeIds: [
        "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
      ],
      nodeCount: null,
      expectedConcurrencyPerNode: 10,
    },
  },
  allocatedNodes: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
      name: "Load Node S8P7N",
      scope: "workspace",
      nodeIndex: 1,
      totalNodes: 2,
      state: "finished",
      lastHeartbeatAt: "2030-06-03T08:05:00.000Z",
      terminalReason: "finished",
      cleanupStatus: "released",
      quarantineReason: null,
      slaResult: "passed",
    },
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
      name: "Load Node S8P7M",
      scope: "workspace",
      nodeIndex: 2,
      totalNodes: 2,
      state: "finished",
      lastHeartbeatAt: "2030-06-03T08:05:00.000Z",
      terminalReason: "finished",
      cleanupStatus: "released",
      quarantineReason: null,
      slaResult: "failed",
    },
  ],
  artifactsSummary: {
    count: 2,
    hasArtifactsZip: true,
    hasFinalStatsCsv: true,
    latestAvailableAt: "2030-06-03T08:05:20.000Z",
  },
};

const aggregateReportDetail = {
  ...reportDetail,
  kpiSummary: {
    status: "parsed",
    sourceArtifactId: null,
    totalRequests: 400,
    failedRequests: 20,
    errorRate: 0.05,
    averageResponseTimeMs: 175,
    p90Ms: null,
    p95Ms: null,
    p99Ms: null,
    throughputPerSecond: null,
    missingReasons: [],
  },
  finalStatsPreview: {
    status: "parsed",
    truncated: false,
    warnings: ["percentile_aggregation_unsupported"],
    rows: [
      {
        label: null,
        totalRequests: 400,
        successRequests: 380,
        failedRequests: 20,
        errorRate: 0.05,
        averageResponseTimeMs: 175,
        p90Ms: null,
        p95Ms: null,
        p99Ms: null,
        responseCodeCounts: { "200": 380, "500": 20 },
      },
    ],
  },
};

const monitoringEnabledLink = {
  runId: runListItem.id,
  enabledForRun: true,
  status: "enabled",
  disabledReason: null,
  platformMonitoringUrl: `/observability/monitoring?runId=${runListItem.id}&from=1906703945000&to=1906704370000`,
  iframeUrl: `/grafana/d/surgepilot-jmeter/jmeter-load-test?orgId=1&kiosk&theme=dark&var-runId=${runListItem.id}&from=1906703945000&to=1906704370000`,
  dashboardUid: "surgepilot-jmeter",
  runStartedAt: "2030-06-03T08:00:05.000Z",
  runEndedAt: "2030-06-03T08:05:10.000Z",
  grafanaFrom: "1906703945000",
  grafanaTo: "1906704370000",
  warnings: [],
};

const monitoringDisabledLink = {
  runId: runListItem.id,
  enabledForRun: false,
  status: "disabled",
  disabledReason: "debug_run_not_monitored",
  platformMonitoringUrl: null,
  iframeUrl: null,
  dashboardUid: "surgepilot-jmeter",
  runStartedAt: "2030-06-03T08:00:05.000Z",
  runEndedAt: "2030-06-03T08:05:10.000Z",
  grafanaFrom: null,
  grafanaTo: null,
  warnings: [],
};

const monitoringConfigErrorLink = {
  ...monitoringDisabledLink,
  status: "config_error",
  disabledReason: null,
  warnings: ["monitoring_config_incomplete"],
};

const missingSummaryReport = {
  ...reportDetail,
  verdict: {
    ...reportDetail.verdict,
    state: "running",
    endedAt: null,
    durationMs: null,
  },
  kpiSummary: {
    status: "missing",
    sourceArtifactId: null,
    totalRequests: null,
    failedRequests: null,
    errorRate: null,
    averageResponseTimeMs: null,
    p90Ms: null,
    p95Ms: null,
    p99Ms: null,
    throughputPerSecond: null,
    missingReasons: ["final_stats_missing"],
  },
  finalStatsPreview: { status: "missing", truncated: false, rows: [] },
  artifactsSummary: {
    count: 0,
    hasArtifactsZip: false,
    hasFinalStatsCsv: false,
    latestAvailableAt: null,
  },
};

const pendingSummaryReport = {
  ...reportDetail,
  kpiSummary: {
    status: "pending",
    sourceArtifactId: "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
    totalRequests: null,
    failedRequests: null,
    errorRate: null,
    averageResponseTimeMs: null,
    p90Ms: null,
    p95Ms: null,
    p99Ms: null,
    throughputPerSecond: null,
    missingReasons: ["summary_pending"],
  },
  finalStatsPreview: { status: "pending", truncated: false, rows: [] },
};

const debugTraceReport = {
  ...reportDetail,
  verdict: {
    ...reportDetail.verdict,
    runType: "debug",
    sourceType: "debug_scenario",
    validity: "invalid",
  },
  debugHttpTrace: {
    status: "available",
    sourceArtifactId: "01HZX3Y9M0E9W7Z6M5QK9S8P7T",
    entryCount: 1,
    traceTruncated: false,
    warnings: [],
    entries: [
      {
        sequence: 1,
        label: "Login",
        method: "POST",
        url: "https://api.example.test/login",
        requestHeaders: { Authorization: "[REDACTED]", "X-Trace": "safe" },
        requestBody: {
          contentType: "application/json",
          text: '{"password":"[REDACTED]"}',
          bodyStorage: "inline",
          bodyTruncated: false,
          sizeBytes: 25,
          sha256Prefix: null,
        },
        responseStatus: 401,
        responseHeaders: {
          "Set-Cookie": "[REDACTED]",
          "Content-Type": "application/json",
        },
        responseBody: {
          contentType: "application/json",
          text: '{"error":"unauthorized"}',
          bodyStorage: "inline",
          bodyTruncated: false,
          sizeBytes: 24,
          sha256Prefix: null,
        },
        durationMs: 123,
        error: "Unauthorized",
      },
    ],
  },
};

const largeBodyTraceReport = {
  ...debugTraceReport,
  debugHttpTrace: {
    ...debugTraceReport.debugHttpTrace,
    entryCount: 1,
    entries: [
      {
        ...debugTraceReport.debugHttpTrace.entries[0],
        requestBody: {
          contentType: "application/json",
          text: '{"name":"preview"}',
          inlinePreview: '{"name":"preview"}',
          bodyStorage: "truncated",
          bodyTruncated: true,
          sizeBytes: 131072,
          sha256Prefix: "1111222233334444",
          downloadArtifactId: null,
          dropReason: null,
        },
        responseBody: {
          contentType: "text/html",
          text: "<html>preview</html>",
          inlinePreview: "<html>preview</html>",
          bodyStorage: "sidecar",
          bodyTruncated: true,
          sizeBytes: 3 * 1024 * 1024,
          sha256Prefix: "aaaabbbbccccdddd",
          downloadArtifactId: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
          dropReason: null,
        },
      },
      {
        ...debugTraceReport.debugHttpTrace.entries[0],
        sequence: 2,
        label: "PDF",
        method: "GET",
        url: "https://api.example.test/report.pdf",
        requestBody: {
          contentType: "application/pdf",
          text: null,
          inlinePreview: null,
          bodyStorage: "dropped",
          bodyTruncated: false,
          sizeBytes: 8 * 1024 * 1024,
          sha256Prefix: "ddddccccbbbbaaaa",
          downloadArtifactId: null,
          dropReason: "body_too_large",
        },
        responseBody: {
          contentType: "application/octet-stream",
          text: null,
          inlinePreview: null,
          bodyStorage: "dropped",
          bodyTruncated: false,
          sizeBytes: 9 * 1024 * 1024,
          sha256Prefix: "eeeeffff00001111",
          downloadArtifactId: null,
          dropReason: "binary_body",
        },
      },
    ],
  },
};

const unavailableTraceReport = {
  ...debugTraceReport,
  debugHttpTrace: {
    status: "unavailable",
    sourceArtifactId: null,
    entryCount: 0,
    traceTruncated: false,
    warnings: ["debug_http_trace_missing"],
    entries: [],
  },
};

const activeDebugTraceReport = {
  ...debugTraceReport,
  verdict: {
    ...debugTraceReport.verdict,
    state: "running",
    endedAt: null,
    durationMs: null,
  },
  debugHttpTrace: null,
};

const unsupportedActiveDebugTraceReport = {
  ...activeDebugTraceReport,
  verdict: {
    ...activeDebugTraceReport.verdict,
    sourceType: "protocol_smoke",
  },
};

const artifacts = {
  items: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
      nodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
      allocationId: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
      artifactType: "final_stats_csv",
      relativePath: "artifacts/final_stats.csv",
      displayFilename: "final_stats.csv",
      sizeBytes: 2048,
      sha256: "a".repeat(64),
      contentType: "text/csv",
      terminalLate: false,
      createdAt: "2030-06-03T08:05:18.000Z",
      availableAt: "2030-06-03T08:05:18.000Z",
      downloadUrl:
        "/api/v1/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R/artifacts/01HZX3Y9M0E9W7Z6M5QK9S8P7F/download",
    },
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
      nodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7M",
      allocationId: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
      artifactType: "artifacts_zip",
      relativePath: "artifacts/final_stats.csv",
      displayFilename: "artifacts.zip",
      sizeBytes: 4096,
      sha256: "b".repeat(64),
      contentType: "application/zip",
      terminalLate: false,
      createdAt: "2030-06-03T08:05:19.000Z",
      availableAt: "2030-06-03T08:05:19.000Z",
      downloadUrl:
        "/api/v1/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R/artifacts/01HZX3Y9M0E9W7Z6M5QK9S8P7G/download",
    },
  ],
  nextCursor: null,
};

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...init.headers },
  });
}

function requestUrl(input: RequestInfo | URL) {
  return input instanceof Request ? input.url : String(input);
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input.method : (init?.method ?? "GET");
}

async function requestBody(input: RequestInfo | URL, init?: RequestInit) {
  if (input instanceof Request) return input.clone().json();
  return JSON.parse(String(init?.body ?? "{}"));
}

function mockFetch(
  handler: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Response | Promise<Response>,
) {
  const fetchMock = vi.fn(handler);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
  window.localStorage.clear();
  Object.defineProperty(window, "isSecureContext", {
    configurable: true,
    value: true,
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("P0-07 runs web flow", () => {
  it("renders Run List filters, rows, cursor pagination, and no P1/P2 entries", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/runs")) {
        const parsed = new URL(url);
        if (parsed.searchParams.get("cursor") === "cursor-2")
          return jsonResponse({ items: [olderRunListItem], nextCursor: null });
        return jsonResponse({ items: [runListItem], nextCursor: "cursor-2" });
      }
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });

    renderAt("/runs");

    expect(
      await screen.findByRole("heading", { name: "Runs" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Execution history")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /runs/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByLabelText("State")).toBeInTheDocument();
    expect(screen.getByLabelText("Validity")).toBeInTheDocument();
    expect(screen.getByLabelText("Run Type")).toBeInTheDocument();
    expect(screen.getByLabelText("Source Type")).toBeInTheDocument();
    expect(await screen.findByText("Checkout Load Test")).toBeInTheDocument();
    expect(screen.getByText("Tags")).toBeInTheDocument();
    expect(screen.getByText("Started")).toBeInTheDocument();
    const formattedStartedAt = new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(runListItem.startedAt));
    expect(screen.getByText(formattedStartedAt)).toBeInTheDocument();
    expect(screen.queryByText("Artifacts")).not.toBeInTheDocument();
    expect(screen.queryByText("SLA")).not.toBeInTheDocument();
    expect(
      screen.getByText(`${runListItem.id} · 2 nodes`),
    ).toBeInTheDocument();
    expect(screen.getByText("checkout")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Report" })).toHaveAttribute(
      "href",
      `/runs/${runListItem.id}`,
    );
    expect(screen.queryByText("View Report")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Load more runs" }),
    );
    expect(await screen.findByText("Checkout Baseline")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Load more runs" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Open Monitoring" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Schedule|Generated YAML|Node Count/i),
    ).not.toBeInTheDocument();
  });

  it("renders Run List empty state without P1/P2 links", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/runs"))
        return jsonResponse({ items: [], nextCursor: null });
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });

    renderAt("/runs");

    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open Test Plans" }),
    ).toHaveAttribute("href", "/test-plans");
    expect(
      screen.getByRole("link", { name: "Open Scenarios" }),
    ).toHaveAttribute("href", "/scenarios");
    expect(
      screen.queryByRole("link", { name: "Open Monitoring" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Schedule|Generated YAML|Node Count/i),
    ).not.toBeInTheDocument();
  });

  it("renders Failure Diagnostics only when safe details exist", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringEnabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse(artifacts);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({
          ...reportDetail,
          failureDiagnostics: {
            ...reportDetail.failureDiagnostics,
            failureReason: "heartbeat_timeout",
            failureMessage: "internal token=do-not-render",
            notes: ["heartbeat_timeout"],
          },
          verdict: {
            ...reportDetail.verdict,
            failureReason: "internal_failure",
            failureMessage: "internal token=do-not-render",
          },
        });
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByRole("heading", { name: "Failure Diagnostics" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Runner heartbeat timed out.")).toBeInTheDocument();
    expect(screen.queryByText(/do-not-render/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/heartbeat timeout/i)).toHaveLength(2);
    expect(
      screen.getByText(/Download logs or the archive from Artifacts/i),
    ).toBeInTheDocument();
  });

  it("explains known SLA result reasons without exposing unknown server text", async () => {
    let reason = "missing_sla_result";
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringEnabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({
          ...reportDetail,
          verdict: { ...reportDetail.verdict, slaResultReason: reason },
        });
      return jsonResponse({});
    });

    const view = renderAt(`/runs/${runListItem.id}`);
    expect(
      await screen.findByText(
        "One or more Load Nodes did not report an SLA result.",
      ),
    ).toBeInTheDocument();

    reason = "internal_token=do-not-render";
    view.unmount();
    renderAt(`/runs/${runListItem.id}`);
    await screen.findByRole("heading", { name: "Run Report" });
    expect(screen.queryByText(/do-not-render/)).not.toBeInTheDocument();
  });

  it("rejects a malformed Run Report before polling or Monitoring lookup", async () => {
    let monitoringRequests = 0;
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`)) {
        monitoringRequests += 1;
        return jsonResponse(monitoringEnabledLink);
      }
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({ verdict: { state: "finished" } });
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByText("Run Report could not be loaded."),
    ).toBeInTheDocument();
    expect(monitoringRequests).toBe(0);
  });

  it("rejects malformed nested Run Report arrays before rendering", async () => {
    let monitoringRequests = 0;
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`)) {
        monitoringRequests += 1;
        return jsonResponse(monitoringEnabledLink);
      }
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({
          ...reportDetail,
          kpiSummary: {
            ...reportDetail.kpiSummary,
            missingReasons: "summary_pending",
          },
          failureDiagnostics: {
            ...reportDetail.failureDiagnostics,
            notes: "heartbeat_timeout",
          },
        });
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByText("Run Report could not be loaded."),
    ).toBeInTheDocument();
    expect(monitoringRequests).toBe(0);
  });

  it("rejects malformed Load Node primitives before Monitoring lookup", async () => {
    let monitoringRequests = 0;
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`)) {
        monitoringRequests += 1;
        return jsonResponse(monitoringEnabledLink);
      }
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({
          ...reportDetail,
          allocatedNodes: [
            {
              ...reportDetail.allocatedNodes[0],
              scope: {},
            },
          ],
        });
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByText("Run Report could not be loaded."),
    ).toBeInTheDocument();
    expect(monitoringRequests).toBe(0);
  });

  it("rejects malformed Run Report datetimes before Monitoring lookup", async () => {
    let monitoringRequests = 0;
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`)) {
        monitoringRequests += 1;
        return jsonResponse(monitoringEnabledLink);
      }
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({
          ...reportDetail,
          verdict: {
            ...reportDetail.verdict,
            createdAt: "not-a-date",
          },
        });
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByText("Run Report could not be loaded."),
    ).toBeInTheDocument();
    expect(monitoringRequests).toBe(0);
  });

  it("renders only allowlisted Load Node terminal reasons", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringEnabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse({
          ...reportDetail,
          allocatedNodes: [
            {
              ...reportDetail.allocatedNodes[0],
              terminalReason: "internal_token=do-not-render",
            },
            {
              ...reportDetail.allocatedNodes[1],
              terminalReason: "unknown_runner_error",
            },
          ],
        });
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByRole("heading", { name: "Run Report" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/do-not-render/i)).not.toBeInTheDocument();
    expect(screen.getByText("Runner execution failed")).toBeInTheDocument();
  });

  it("renders Run Report sections in order, collapsed artifacts, and safe missing KPI copy", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringEnabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse(artifacts);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(reportDetail);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByRole("heading", { name: "Run Report" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Run Report")).toHaveLength(1);
    const sectionNames = [
      "Verdict Summary",
      "KPI Summary",
      "Monitoring",
      "Final Stats Preview",
      "Snapshot Summary",
      "Artifacts",
      "Nodes",
    ];
    expect(
      screen.queryByRole("heading", { name: "Failure Diagnostics" }),
    ).not.toBeInTheDocument();
    const headings = sectionNames.map((name) =>
      screen.getByRole("heading", { name }),
    );
    for (let index = 0; index < headings.length - 1; index += 1) {
      expect(
        headings[index].compareDocumentPosition(headings[index + 1]) &
          Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    }
    expect(screen.getAllByText("SLA failed").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Valid")).toBeInTheDocument();
    expect(screen.getByLabelText("Report Validity")).toBeInTheDocument();
    expect(screen.queryByText(/^Validity$/)).not.toBeInTheDocument();
    expect(
      screen
        .getByLabelText("Report Validity")
        .compareDocumentPosition(
          screen.getByRole("button", { name: "Refresh" }),
        ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const verdictSummary = screen
      .getByRole("heading", { name: "Verdict Summary" })
      .closest("section");
    expect(verdictSummary).not.toBeNull();
    expect(
      within(verdictSummary as HTMLElement).queryByLabelText("Report Validity"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Checkout scenario")).toBeInTheDocument();
    expect(screen.getByText("Concurrency")).toBeInTheDocument();
    expect(screen.getAllByText("10").length).toBeGreaterThan(0);
    expect(screen.getByText("Ramp up")).toBeInTheDocument();
    expect(screen.getByText("30s")).toBeInTheDocument();
    expect(screen.getByText("Hold")).toBeInTheDocument();
    expect(screen.getByText("300s")).toBeInTheDocument();
    expect(screen.getByText("Target RPS")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("Delay")).toBeInTheDocument();
    expect(screen.getByText("7s")).toBeInTheDocument();
    expect(screen.getByText("p95 lte 500ms")).toBeInTheDocument();
    expect(screen.getByText("users.csv")).toBeInTheDocument();
    expect(screen.getByText("API_TOKEN")).toBeInTheDocument();
    expect(screen.getByText("BASE_URL")).toBeInTheDocument();
    expect(
      screen.getByText("Node 1 of 2 · Workspace · Finished"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Node 2 of 2 · Workspace · Finished"),
    ).toBeInTheDocument();
    expect(screen.getByText("Load Node S8P7M")).toBeInTheDocument();
    expect(screen.queryByText("load-01.internal")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/failed requests preview/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "HTTP Trace" }),
    ).not.toBeInTheDocument();
    const monitoringRegion = screen
      .getByRole("heading", { name: "Monitoring" })
      .closest("section");
    expect(monitoringRegion).not.toBeNull();
    expect(
      within(monitoringRegion as HTMLElement).getByText(
        /Grafana dashboard is available/i,
      ),
    ).toBeInTheDocument();
    expect(
      within(monitoringRegion as HTMLElement).getByRole("link", {
        name: "Open Monitoring",
      }),
    ).toHaveAttribute("href", monitoringEnabledLink.platformMonitoringUrl);
    expect(
      within(monitoringRegion as HTMLElement).queryByText(
        /token|internal|node write|influxdb/i,
      ),
    ).not.toBeInTheDocument();
    const artifactsRegion = screen.getByTestId("artifacts-section");
    expect(
      within(artifactsRegion).getByText("2 artifacts"),
    ).toBeInTheDocument();
    expect(
      within(artifactsRegion).queryByText("final_stats.csv"),
    ).not.toBeInTheDocument();
    await userEvent.click(
      within(artifactsRegion).getByRole("button", { name: /show artifacts/i }),
    );
    expect(
      await within(artifactsRegion).findByText("final_stats.csv"),
    ).toBeInTheDocument();
    expect(
      within(artifactsRegion).getByText("artifacts.zip"),
    ).toBeInTheDocument();
    expect(
      within(artifactsRegion).getByText("Download-only archive"),
    ).toBeInTheDocument();
    expect(
      within(artifactsRegion).getByText("Load Node S8P7N · Node 1 of 2"),
    ).toBeInTheDocument();
    expect(
      within(artifactsRegion).getByText("Load Node S8P7M · Node 2 of 2"),
    ).toBeInTheDocument();
    const links = within(artifactsRegion).getAllByRole("link", {
      name: "Download",
    });
    expect(links[0]).toHaveAttribute(
      "href",
      expect.stringContaining("01HZX3Y9M0E9W7Z6M5QK9S8P7F"),
    );
    expect(links[1]).toHaveAttribute(
      "href",
      expect.stringContaining("01HZX3Y9M0E9W7Z6M5QK9S8P7G"),
    );
    expect(
      within(artifactsRegion).queryByText(
        /storageKey|run-artifacts|runnerHome|sshUser/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders aggregate final stats totals and warnings without node label rows", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringEnabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse(artifacts);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(aggregateReportDetail);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    const kpiSection = (await screen.findByRole("heading", { name: "KPI Summary" })).closest(
      "section",
    );
    expect(kpiSection).not.toBeNull();
    expect(within(kpiSection as HTMLElement).getByText("400")).toBeInTheDocument();
    expect(within(kpiSection as HTMLElement).getByText("5.00%")).toBeInTheDocument();
    expect(within(kpiSection as HTMLElement).getByText("175 ms")).toBeInTheDocument();
    expect(
      within(kpiSection as HTMLElement).queryByText(/Percentile aggregation unsupported/i),
    ).not.toBeInTheDocument();

    const previewSection = screen
      .getByRole("heading", { name: "Final Stats Preview" })
      .closest("section");
    expect(previewSection).not.toBeNull();
    expect(within(previewSection as HTMLElement).getAllByText("Total")).toHaveLength(2);
    expect(
      within(previewSection as HTMLElement).queryByText("GET /checkout"),
    ).not.toBeInTheDocument();
    expect(
      within(previewSection as HTMLElement).getByText(/Percentile aggregation unsupported/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Failure Diagnostics" }),
    ).not.toBeInTheDocument();
  });

  it("renders sanitized Debug HTTP Trace details and unavailable state", async () => {
    const writeText = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const fetchMock = mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringDisabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse(artifacts);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(debugTraceReport);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByRole("heading", { name: "HTTP Trace" }),
    ).toBeInTheDocument();
    expect(screen.getByText("POST")).toBeInTheDocument();
    expect(
      screen.getByText("https://api.example.test/login"),
    ).toBeInTheDocument();
    expect(screen.getByText("401")).toBeInTheDocument();
    expect(screen.getByText("123 ms")).toBeInTheDocument();
    expect(
      screen.queryByText(/secret-token|open-sesame|object-key/i),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /show trace details/i }),
    );
    expect(
      await screen.findByText(/Authorization: \[REDACTED\]/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Set-Cookie: \[REDACTED\]/)).toBeInTheDocument();
    expect(screen.getByText(/unauthorized/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /copy url/i }));
    expect(writeText).toHaveBeenCalledWith("https://api.example.test/login");
    await userEvent.click(
      screen.getAllByRole("button", { name: /copy preview/i })[0],
    );
    expect(writeText).toHaveBeenCalledWith('{"password":"[REDACTED]"}');
    await userEvent.click(screen.getByRole("button", { name: /copy error/i }));
    expect(writeText).toHaveBeenCalledWith("Unauthorized");
    expect(writeText).not.toHaveBeenCalledWith(
      expect.stringMatching(/secret-token|open-sesame|object-key/i),
    );

    fetchMock.mockImplementation((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringDisabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(unavailableTraceReport);
      return jsonResponse({});
    });
    cleanup();
    renderAt(`/runs/${runListItem.id}`);
    expect(
      await screen.findByText(/HTTP trace is unavailable/i),
    ).toBeInTheDocument();
  });

  it("renders large Debug HTTP Trace body states without exposing object keys", async () => {
    const writeText = vi.fn();
    if (!("createObjectURL" in URL)) {
      Object.defineProperty(URL, "createObjectURL", {
        configurable: true,
        value: vi.fn(),
      });
    }
    if (!("revokeObjectURL" in URL)) {
      Object.defineProperty(URL, "revokeObjectURL", {
        configurable: true,
        value: vi.fn(),
      });
    }
    const createObjectURL = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:debug-http-body");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL");
    const anchorClick = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringDisabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse(artifacts);
      if (
        url.includes(
          `/api/v1/runs/${runListItem.id}/debug-http-body-blobs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/download`,
        )
      ) {
        const headers =
          input instanceof Request ? input.headers : new Headers(init?.headers);
        expect(headers.get("x-workspace-id")).toBe(
          authSession.defaultWorkspace.id,
        );
        return new Response(new Blob(["<html>sanitized body</html>"]), {
          status: 200,
        });
      }
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(largeBodyTraceReport);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByRole("heading", { name: "HTTP Trace" }),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getAllByRole("button", { name: /show trace details/i })[0],
    );
    expect(screen.getByText(/storage:truncated/)).toBeInTheDocument();
    expect(screen.getByText('{"name":"preview"}')).toBeInTheDocument();
    expect(
      screen.getByText(/Body preview truncated to the debug trace limit/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/storage:sidecar/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /Large sanitized body stored as an internal sidecar artifact/i,
      ),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /download sanitized body/i }),
    );
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) =>
          requestUrl(input).includes(
            `/api/v1/runs/${runListItem.id}/debug-http-body-blobs/01HZX3Y9M0E9W7Z6M5QK9S8P7B/download`,
          ),
        ),
      ).toBe(true);
    });
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(anchorClick).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:debug-http-body");
    expect(
      screen.queryByRole("link", { name: /download sanitized body/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/run-artifacts|body-blob-object-key/i),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getAllByRole("button", { name: /copy preview/i })[0],
    );
    expect(writeText).toHaveBeenCalledWith('{"name":"preview"}');
    expect(writeText).not.toHaveBeenCalledWith(
      expect.stringMatching(/sanitized body/i),
    );

    await userEvent.click(
      screen.getAllByRole("button", { name: /show trace details/i })[0],
    );
    expect(
      screen.getByText(/Body was not captured: Body Too Large/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Body was not captured: Binary Body/i),
    ).toBeInTheDocument();
  });

  it("renders an active Debug HTTP Trace empty state before upload", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringDisabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse({ items: [], nextCursor: null });
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(activeDebugTraceReport);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByRole("heading", { name: "HTTP Trace" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/will appear after the Debug Run uploads/i),
    ).toBeInTheDocument();

    cleanup();
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringDisabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse({ items: [], nextCursor: null });
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(unsupportedActiveDebugTraceReport);
      return jsonResponse({});
    });
    renderAt(`/runs/${runListItem.id}`);
    await screen.findByText(
      "Run is still active. Static run metadata will refresh every 5 seconds.",
    );
    expect(
      screen.queryByRole("heading", { name: "HTTP Trace" }),
    ).not.toBeInTheDocument();
  });

  it("shows N/A and static running information without live metrics", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringConfigErrorLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse({ items: [], nextCursor: null });
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(missingSummaryReport);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    expect(
      await screen.findByText(
        "Run is still active. Static run metadata will refresh every 5 seconds.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(4);
    expect(
      screen.getByText("Final stats artifact has not been uploaded yet."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/live metrics|log tail|TPS chart/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/Monitoring is not configured for this run/i),
    ).toBeInTheDocument();
  });

  it("uses bounded report polling rules for active and terminal pending reports", () => {
    expect(
      runReportRefetchInterval(missingSummaryReport as RunReportDetail, 0),
    ).toBe(5000);
    expect(runReportRefetchInterval(reportDetail as RunReportDetail, 0)).toBe(
      false,
    );
    expect(
      runReportRefetchInterval(pendingSummaryReport as RunReportDetail, 11),
    ).toBe(5000);
    expect(
      runReportRefetchInterval(pendingSummaryReport as RunReportDetail, 12),
    ).toBe(false);
  });

  it("caps terminal pending summary polling by completed fetches with identical responses", async () => {
    vi.useFakeTimers();
    let reportFetches = 0;
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringDisabledLink);
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse({ items: [], nextCursor: null });
      if (url.includes(`/api/v1/runs/${runListItem.id}`)) {
        reportFetches += 1;
        return jsonResponse(pendingSummaryReport);
      }
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);

    for (
      let index = 0;
      index < 10 && !screen.queryByRole("heading", { name: "Run Report" });
      index += 1
    ) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
    }
    expect(
      screen.getByRole("heading", { name: "Run Report" }),
    ).toBeInTheDocument();
    for (let index = 0; index < 15; index += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
    }

    expect(reportFetches).toBeLessThanOrEqual(13);
  });

  it("sends CSRF when validity changes and reconciles from the API response", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes(`/api/v1/runs/${runListItem.id}/monitoring`))
        return jsonResponse(monitoringEnabledLink);
      if (
        url.includes(`/api/v1/runs/${runListItem.id}/validity`) &&
        method === "PATCH"
      ) {
        const body = await requestBody(input, init);
        expect(body.validity).toBe("invalid");
        const headers =
          input instanceof Request ? input.headers : new Headers(init?.headers);
        expect(headers.get("x-csrf-token")).toBe("csrf-token");
        return jsonResponse({
          id: runListItem.id,
          validity: "invalid",
          validityUpdatedAt: "2030-06-03T09:00:00.000Z",
          validityUpdatedBy: {
            id: authSession.user.id,
            email: authSession.user.email,
          },
        });
      }
      if (url.includes(`/api/v1/runs/${runListItem.id}/artifacts`))
        return jsonResponse(artifacts);
      if (url.includes(`/api/v1/runs/${runListItem.id}`))
        return jsonResponse(reportDetail);
      return jsonResponse({});
    });

    renderAt(`/runs/${runListItem.id}`);
    await screen.findByRole("heading", { name: "Run Report" });
    fireEvent.change(screen.getByLabelText("Report Validity"), {
      target: { value: "invalid" },
    });

    expect(await screen.findByText("Invalid")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();
  });
});
