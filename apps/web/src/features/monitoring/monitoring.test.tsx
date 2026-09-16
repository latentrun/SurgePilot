import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";

const authSession = {
  user: {
    id: "01J00000000000000000000001",
    email: "monitoring@example.com",
    displayName: "Monitoring User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: "01J00000000000000000000002",
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
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
  it("renders the same-origin Grafana iframe without exposing internal settings", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed")) {
        const parsed = new URL(url);
        expect(parsed.searchParams.get("runId")).toBe(
          "01J00000000000000000000003",
        );
        expect(parsed.searchParams.get("from")).toBe("1906703945000");
        expect(parsed.searchParams.get("to")).toBe("1906704370000");
        return jsonResponse({
          enabled: true,
          status: "ready",
          iframeUrl:
            "/grafana/d/surgepilot-jmeter/jmeter-load-test?orgId=1&kiosk&theme=dark&var-runId=01J00000000000000000000003&from=1906703945000&to=1906704370000",
          runId: "01J00000000000000000000003",
          from: "1906703945000",
          to: "1906704370000",
          dashboardUid: "surgepilot-jmeter",
          warnings: [],
        });
      }
      if (url.includes("/grafana/")) return new Response("<html></html>");
      return jsonResponse({});
    });

    const { container } = renderAt(
      "/observability/monitoring?runId=01J00000000000000000000003&from=1906703945000&to=1906704370000",
    );

    expect(
      await screen.findByRole("heading", { name: "Monitoring" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/View read-only JMeter runtime metrics/i),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Monitoring" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    const frame = await screen.findByTitle("Grafana monitoring dashboard");
    expect(frame).toHaveAttribute(
      "src",
      expect.stringContaining("/grafana/d/surgepilot-jmeter"),
    );
    expect(frame).toHaveAttribute(
      "src",
      expect.stringContaining("var-runId=01J00000000000000000000003"),
    );
    expect(frame).toHaveClass("flex-1");
    expect(frame).not.toHaveClass("rounded-2xl");
    expect(container.querySelector("main")).toHaveClass("px-0");
    expect(
      container.querySelector("section[data-monitoring-page='true']"),
    ).not.toHaveClass("max-w-7xl");
    expect(
      screen.queryByText(/token|internal url|node write|influxdb/i),
    ).not.toBeInTheDocument();
  });

  it("renders a clear empty state when monitoring is not configured", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed"))
        return jsonResponse({
          enabled: false,
          status: "config_error",
          iframeUrl: null,
          runId: null,
          from: null,
          to: null,
          dashboardUid: "surgepilot-jmeter",
          warnings: ["monitoring_config_incomplete"],
        });
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    expect(
      await screen.findByRole("heading", { name: "Monitoring" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText(/Monitoring is not configured/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).not.toBeInTheDocument();
  });

  it("shows a Web-owned error state when the Grafana iframe fails to load", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed")) {
        return jsonResponse({
          enabled: true,
          status: "ready",
          iframeUrl:
            "/grafana/d/surgepilot-jmeter/jmeter-load-test?orgId=1&kiosk&theme=dark",
          runId: null,
          from: null,
          to: null,
          dashboardUid: "surgepilot-jmeter",
          warnings: [],
        });
      }
      if (url.includes("/grafana/")) return new Response("<html></html>");
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    const frame = await screen.findByTitle("Grafana monitoring dashboard");
    fireEvent.error(frame);

    expect(
      await screen.findByText(/Grafana dashboard could not be loaded/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/token|internal url|node write/i),
    ).not.toBeInTheDocument();
  });

  it("shows a session-focused error state when the same-origin Grafana preflight is unauthorized", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed")) {
        return jsonResponse({
          enabled: true,
          status: "ready",
          iframeUrl:
            "/grafana/d/surgepilot-jmeter/jmeter-load-test?orgId=1&kiosk&theme=dark",
          runId: null,
          from: null,
          to: null,
          dashboardUid: "surgepilot-jmeter",
          warnings: [],
        });
      }
      if (url.includes("/grafana/")) {
        return new Response("Forbidden", { status: 403 });
      }
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    expect(
      await screen.findByText(/Check your session, then try again/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).not.toBeInTheDocument();
  });

  it("shows a gateway-focused error state when the Grafana reverse proxy is unavailable", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/monitoring/embed")) {
        return jsonResponse({
          enabled: true,
          status: "ready",
          iframeUrl:
            "/grafana/d/surgepilot-jmeter/jmeter-load-test?orgId=1&kiosk&theme=dark",
          runId: null,
          from: null,
          to: null,
          dashboardUid: "surgepilot-jmeter",
          warnings: [],
        });
      }
      if (url.includes("/grafana/")) {
        return new Response("Bad Gateway", { status: 502 });
      }
      return jsonResponse({});
    });

    renderAt("/observability/monitoring");

    expect(
      await screen.findByText(/Grafana gateway is unavailable/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTitle("Grafana monitoring dashboard"),
    ).not.toBeInTheDocument();
  });
});
