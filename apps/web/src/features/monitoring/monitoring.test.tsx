import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { MonitoringCard } from "../runs/pages/run-report-page";

const RUN_ID = "01J00000000000000000000003";
const WORKSPACE_ID = "01HZW000000000000000000000";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "monitoring@example.com",
    displayName: "Monitoring User",
    role: "admin",
    status: "active",
  },
  currentWorkspace: { id: WORKSPACE_ID, name: "Default Workspace" },
  defaultWorkspace: { id: WORKSPACE_ID, name: "Default Workspace" },
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

function embedResponse(overrides: Record<string, unknown>) {
  return {
    dashboardUid: "surgepilot-jmeter-13644",
    enabled: false,
    from: null,
    iframeUrl: null,
    runId: null,
    status: "not_configured",
    to: null,
    warnings: [],
    ...overrides,
  };
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("P1-00 monitoring page", () => {
  it("renders the same-origin Grafana iframe from window.location query params", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed")) {
        const parsed = new URL(url, "http://localhost");
        expect(parsed.searchParams.get("runId")).toBe(RUN_ID);
        expect(parsed.searchParams.get("from")).toBe("1906703945000");
        expect(parsed.searchParams.get("to")).toBe("1906704370000");
        return jsonResponse(
          embedResponse({
            enabled: true,
            from: "1906703945000",
            iframeUrl: `/grafana/d/surgepilot-jmeter-13644/jmeter-load-test?orgId=1&kiosk&var-runId=${RUN_ID}&from=1906703945000&to=1906704370000`,
            runId: RUN_ID,
            status: "ready",
            to: "1906704370000",
          }),
        );
      }
      if (url.includes("/grafana/")) return new Response("<html></html>");
      return jsonResponse({});
    });

    const { container } = renderAt(
      `/observability/monitoring?runId=${RUN_ID}&from=1906703945000&to=1906704370000`,
    );

    expect(
      await screen.findByRole("heading", { name: "Monitoring" }),
    ).toBeTruthy();
    expect(
      await screen.findByText(/Dashboard configuration is ready/i),
    ).toBeTruthy();
    expect(
      container.querySelector("[data-monitoring-state='ready']"),
    ).not.toBeNull();
    const frame = await screen.findByTitle("Grafana monitoring dashboard");
    expect(frame.getAttribute("src")).toContain(
      "/grafana/d/surgepilot-jmeter-13644",
    );
    expect(frame.getAttribute("src")).toContain(`var-runId=${RUN_ID}`);
    expect(frame.getAttribute("style")).toContain("flex");
    expect(
      container.querySelector("main[data-monitoring-page='true']"),
    ).not.toBeNull();
    expect(
      container.querySelector("main[data-monitoring-page='true']")?.style
        .maxWidth,
    ).toBe("none");
    expect(
      screen.queryByText(/token|internal url|node write|influxdb/i),
    ).toBeNull();
  });

  it("renders a distinct not-configured empty state", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed"))
        return jsonResponse(
          embedResponse({
            status: "not_configured",
            warnings: ["monitoring_not_configured"],
          }),
        );
      return jsonResponse({});
    });

    const { container } = renderAt("/observability/monitoring");

    expect(
      await screen.findByRole("heading", { name: "Monitoring is not configured" }),
    ).toBeTruthy();
    expect(
      container.querySelector("[data-monitoring-state='not_configured']"),
    ).not.toBeNull();
    expect(
      screen.queryByRole("heading", { name: "Monitoring configuration error" }),
    ).toBeNull();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).toBeNull();
    expect(screen.queryByText(/administrator|restart|nginx|provision/i)).toBeNull();
  });

  it("renders a distinct configuration-error empty state", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed"))
        return jsonResponse(
          embedResponse({
            status: "config_error",
            warnings: ["monitoring_config_incomplete"],
          }),
        );
      return jsonResponse({});
    });

    const { container } = renderAt("/observability/monitoring");

    expect(
      await screen.findByRole("heading", {
        name: "Monitoring configuration error",
      }),
    ).toBeTruthy();
    expect(
      container.querySelector("[data-monitoring-state='config_error']"),
    ).not.toBeNull();
    expect(
      screen.queryByRole("heading", { name: "Monitoring is not configured" }),
    ).toBeNull();
    expect(screen.queryByText(/administrator|restart|nginx|provision/i)).toBeNull();
  });

  it("renders a distinct disabled empty state", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed"))
        return jsonResponse(embedResponse({ status: "disabled" }));
      return jsonResponse({});
    });

    const { container } = renderAt("/observability/monitoring");

    expect(
      await screen.findByRole("heading", { name: "Monitoring is disabled" }),
    ).toBeTruthy();
    expect(
      container.querySelector("[data-monitoring-state='disabled']"),
    ).not.toBeNull();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).toBeNull();
  });

  it("shows neutral user-facing copy when the Grafana iframe is unavailable", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed"))
        return jsonResponse(
          embedResponse({
            enabled: true,
            iframeUrl: "/grafana/d/surgepilot-jmeter-13644/jmeter-load-test?kiosk",
            status: "ready",
          }),
        );
      if (url.includes("/grafana/")) {
        return new Response("Bad Gateway", { status: 502 });
      }
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    expect(
      await screen.findByText(/temporarily unavailable/i),
    ).toBeTruthy();
    expect(screen.queryByText(/restart|nginx|provision/i)).toBeNull();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).toBeNull();
  });

  it("shows a session-focused empty state when the same-origin preflight is unauthorized", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed"))
        return jsonResponse(
          embedResponse({
            enabled: true,
            iframeUrl: "/grafana/d/surgepilot-jmeter-13644/jmeter-load-test?kiosk",
            status: "ready",
          }),
        );
      if (url.includes("/grafana/")) {
        return new Response("Forbidden", { status: 403 });
      }
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    expect(
      await screen.findByText(/Check your session, then try again/i),
    ).toBeTruthy();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).toBeNull();
  });

  it("shows a safe empty state when the embed request fails", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed")) {
        return jsonResponse(
          { code: "INTERNAL", message: "Internal error.", requestId: "req" },
          { status: 500 },
        );
      }
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    expect(await screen.findByText("Monitoring could not be loaded.")).toBeTruthy();
    expect(screen.queryByText(/token|internal url|node write/i)).toBeNull();
  });
});

describe("P1-00 Run Report monitoring card", () => {
  it("shows the Debug muted hint and no monitoring link", async () => {
    mockFetch(() =>
      jsonResponse({
        dashboardUid: "surgepilot-jmeter-13644",
        disabledReason: "debug_run_not_monitored",
        enabledForRun: false,
        grafanaFrom: null,
        grafanaTo: null,
        iframeUrl: null,
        platformMonitoringUrl: null,
        runEndedAt: null,
        runId: RUN_ID,
        runStartedAt: null,
        status: "disabled",
        warnings: [],
      }),
    );

    render(<MonitoringCard runId={RUN_ID} workspaceId={WORKSPACE_ID} />);

    expect(
      await screen.findByRole("heading", { name: "Monitoring" }),
    ).toBeTruthy();
    expect(
      await screen.findByText("Debug Runs do not emit monitoring data."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: "Open Monitoring" }),
    ).toBeNull();
    expect(
      screen.queryByText(/administrator|restart|nginx|token|node write/i),
    ).toBeNull();
  });

  it("links to monitoring only for an enabled Standard Run", async () => {
    mockFetch(() =>
      jsonResponse({
        dashboardUid: "surgepilot-jmeter-13644",
        disabledReason: null,
        enabledForRun: true,
        grafanaFrom: "1906703945000",
        grafanaTo: "1906704370000",
        iframeUrl: `/grafana/d/surgepilot-jmeter-13644/jmeter-load-test?var-runId=${RUN_ID}`,
        platformMonitoringUrl: `/observability/monitoring?runId=${RUN_ID}&from=1906703945000&to=1906704370000`,
        runEndedAt: null,
        runId: RUN_ID,
        runStartedAt: null,
        status: "enabled",
        warnings: [],
      }),
    );

    render(<MonitoringCard runId={RUN_ID} workspaceId={WORKSPACE_ID} />);

    const link = await screen.findByRole("link", { name: "Open Monitoring" });
    expect(link.getAttribute("href")).toBe(
      `/observability/monitoring?runId=${RUN_ID}&from=1906703945000&to=1906704370000`,
    );
    expect(
      screen.getByText(/Grafana dashboard is available for this Standard Run/i),
    ).toBeTruthy();
    expect(
      screen.queryByText(/token|internal url|node write/i),
    ).toBeNull();
  });

  it("shows a safe empty state when monitoring is not configured for the run", async () => {
    mockFetch(() =>
      jsonResponse({
        dashboardUid: "surgepilot-jmeter-13644",
        disabledReason: "not_configured",
        enabledForRun: false,
        grafanaFrom: null,
        grafanaTo: null,
        iframeUrl: null,
        platformMonitoringUrl: null,
        runEndedAt: null,
        runId: RUN_ID,
        runStartedAt: null,
        status: "not_configured",
        warnings: [],
      }),
    );

    render(<MonitoringCard runId={RUN_ID} workspaceId={WORKSPACE_ID} />);

    expect(
      await screen.findByText("Monitoring is not configured for this run."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: "Open Monitoring" }),
    ).toBeNull();
    expect(
      screen.queryByText(/administrator|restart|nginx/i),
    ).toBeNull();
  });

  it("shows a safe empty state when the monitoring link request fails", async () => {
    mockFetch(() =>
      jsonResponse(
        { code: "INTERNAL", message: "Internal error.", requestId: "req" },
        { status: 500 },
      ),
    );

    render(<MonitoringCard runId={RUN_ID} workspaceId={WORKSPACE_ID} />);

    expect(
      await screen.findByText("Monitoring details are unavailable for this run."),
    ).toBeTruthy();
    expect(
      screen.queryByRole("link", { name: "Open Monitoring" }),
    ).toBeNull();
  });
});
