import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";

const workspace = {
  id: "01HZW000000000000000000000",
  name: "Default Workspace",
};

function authSession(role: "admin" | "user" = "admin") {
  return {
    user: {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
      email: `${role}@example.com`,
      displayName: role === "admin" ? "Admin User" : "Regular User",
      role,
      status: "active",
    },
    defaultWorkspace: workspace,
    csrfToken: "csrf-token",
  };
}

const baseOverview = {
  generatedAt: "2030-06-07T10:30:00.000Z",
  workspace,
  statsScope: {
    windowDays: 30,
    windowStartedAt: "2030-05-08T10:30:00.000Z",
    resultRunScope: "valid_standard_terminal_runs",
    recentRunLimit: 5,
  },
  runStats: {
    resultRuns: {
      total: 3,
      byState: { finished: 1, failed: 1, aborted: 1 },
      bySlaResult: { passed: 1, failed: 1, notEvaluated: 1 },
    },
    activeRuns: { total: 1, initializing: 0, running: 1, stopping: 0 },
  },
  recentRuns: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
      runType: "debug",
      sourceType: "debug_scenario",
      sourceName: "Debug calibration",
      state: "finished",
      validity: "invalid",
      slaResult: "not_evaluated",
      createdAt: "2030-06-07T10:00:00.000Z",
      startedAt: "2030-06-07T10:00:05.000Z",
      endedAt: "2030-06-07T10:02:00.000Z",
      durationMs: null,
      artifactCount: 0,
      hasArtifactsZip: false,
    },
  ],
  resourceSummary: {
    totalVisibleNodes: 3,
    byStatus: {
      uninitialized: 0,
      initializing: 0,
      idle: 2,
      busy: 1,
      offline: 0,
      quarantined: 0,
      disabled: 0,
    },
  },
};

function emptyOverview() {
  return {
    ...baseOverview,
    runStats: {
      resultRuns: {
        total: 0,
        byState: { finished: 0, failed: 0, aborted: 0 },
        bySlaResult: { passed: 0, failed: 0, notEvaluated: 0 },
      },
      activeRuns: { total: 0, initializing: 0, running: 0, stopping: 0 },
    },
    recentRuns: [],
    resourceSummary: {
      totalVisibleNodes: 0,
      byStatus: {
        uninitialized: 0,
        initializing: 0,
        idle: 0,
        busy: 0,
        offline: 0,
        quarantined: 0,
        disabled: 0,
      },
    },
  };
}

const setupStatus = {
  needsBootstrap: false,
  allowSignup: true,
  hasDefaultWorkspace: true,
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

function mockFetch(body: unknown, role: "admin" | "user" = "admin") {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession(role));
    if (url.includes("/api/v1/overview")) return jsonResponse(body);
    if (url.endsWith("/api/v1/admin/setup-status")) {
      return role === "admin"
        ? jsonResponse(setupStatus)
        : jsonResponse(
            {
              code: "FORBIDDEN",
              message: "Admin access is required.",
              requestId: "req",
            },
            { status: 403 },
          );
    }
    return jsonResponse(setupStatus);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  window.history.pushState({}, "", path);
  return render(<App />);
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("P0-08 overview", () => {
  it("renders workspace context, Last 30 days scope, and Valid Standard result labels", async () => {
    mockFetch(baseOverview);

    renderAt("/overview");

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Default Workspace").length).toBeGreaterThan(0);
    expect(screen.getByText(/Last 30 days/i)).toBeInTheDocument();
    expect(await screen.findByText("Valid Standard Runs")).toBeInTheDocument();
    expect(screen.getByText("Failed State")).toBeInTheDocument();
    expect(screen.getByText("SLA Failed")).toBeInTheDocument();
    expect(screen.getByText("Not Evaluated")).toBeInTheDocument();
    expect(screen.getAllByText("0").length).toBeGreaterThan(0);
  });

  it("labels Debug and Invalid recent runs and uses safe unavailable copy", async () => {
    mockFetch(baseOverview);

    renderAt("/overview");

    const row = await screen.findByRole("link", { name: /Debug calibration/i });
    expect(row).toHaveAttribute("href", "/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R");
    expect(within(row).getByText("Debug")).toBeInTheDocument();
    expect(within(row).getByText("Invalid")).toBeInTheDocument();
    expect(within(row).getByText("SLA Not Evaluated")).toBeInTheDocument();
    expect(within(row).getByText("N/A")).toBeInTheDocument();
  });

  it("keeps empty states and quick actions P0-scoped", async () => {
    mockFetch(emptyOverview());

    renderAt("/overview");

    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open Test Plans" }),
    ).toHaveAttribute("href", "/test-plans");
    expect(
      screen.getByRole("link", { name: "Register Load Node" }),
    ).toHaveAttribute("href", "/resources/load-nodes/new");
    expect(
      screen.getByRole("link", { name: /Create Scenario/i }),
    ).toHaveAttribute("href", "/scenarios");
    expect(
      screen.getByRole("link", { name: /Create Test Plan/i }),
    ).toHaveAttribute("href", "/test-plans");
    expect(
      screen
        .getAllByRole("link", { name: /View Runs/i })
        .some((link) => link.getAttribute("href") === "/runs"),
    ).toBe(true);
    const main = screen.getByRole("main");
    expect(
      within(main).queryByText(
        /Schedule|Grafana|Help|Upcoming Scheduled Jobs/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders loading state", async () => {
    const pendingFetch = vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me"))
        return Promise.resolve(jsonResponse(authSession("admin")));
      if (url.includes("/api/v1/overview"))
        return new Promise<Response>(() => {});
      return Promise.resolve(jsonResponse(setupStatus));
    });
    vi.stubGlobal("fetch", pendingFetch);

    renderAt("/overview");

    expect(
      await screen.findByRole("status", { name: /loading overview/i }),
    ).toBeInTheDocument();
  });

  it("renders safe error state", async () => {
    const errorFetch = vi.fn((input: RequestInfo | URL) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me"))
        return jsonResponse(authSession("admin"));
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(
          {
            code: "WORKSPACE_REQUIRED",
            message: "Workspace is required.",
            requestId: "req-overview",
          },
          { status: 400 },
        );
      }
      return jsonResponse(setupStatus);
    });
    vi.stubGlobal("fetch", errorFetch);

    renderAt("/overview");

    expect(
      await screen.findByText("Unable to load Overview"),
    ).toBeInTheDocument();
    expect(screen.getByText(/WORKSPACE_REQUIRED/)).toBeInTheDocument();
    expect(screen.getByText(/req-overview/)).toBeInTheDocument();
    expect(
      screen.queryByText(/Traceback|SELECT \\*|storageKey|privateKey/i),
    ).not.toBeInTheDocument();
  });

  it("hides Admin navigation for non-Admin users", async () => {
    mockFetch(baseOverview, "user");

    renderAt("/overview");

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).queryByText("Admin")).not.toBeInTheDocument();
    expect(
      within(navigation).queryByRole("link", { name: /setup status/i }),
    ).not.toBeInTheDocument();
  });

  it("shows only Setup Status under Admin for Admin users", async () => {
    mockFetch(baseOverview, "admin");

    renderAt("/overview");

    const navigation = await screen.findByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).getByText("Admin")).toBeInTheDocument();
    expect(
      within(navigation).getByRole("link", { name: /setup status/i }),
    ).toHaveAttribute("href", "/admin/setup-status");
    expect(
      within(navigation).queryByRole("link", { name: /workspaces/i }),
    ).not.toBeInTheDocument();
    expect(
      within(navigation).queryByRole("link", { name: /users/i }),
    ).not.toBeInTheDocument();
    expect(
      within(navigation).queryByRole("link", { name: /system settings/i }),
    ).not.toBeInTheDocument();
  });

  it("renders Admin Setup Status for Admin users only", async () => {
    const fetchMock = mockFetch(baseOverview, "admin");

    renderAt("/admin/setup-status");

    expect(
      await screen.findByRole("heading", { name: "Setup Status" }),
    ).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(await within(main).findByText("Available")).toBeInTheDocument();
    expect(within(main).getByText("Default Workspace")).toBeInTheDocument();
    expect(within(main).getByText("Local Signup")).toBeInTheDocument();
    expect(within(main).getByText("Bootstrap")).toBeInTheDocument();
    expect(within(main).getByText("Enabled")).toBeInTheDocument();
    expect(within(main).getByText("Completed")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          requestUrl(input).endsWith("/api/v1/admin/setup-status"),
        ),
      ).toBe(true),
    );
  });

  it("renders 403 for non-Admin users on Admin Setup Status without loading Admin data", async () => {
    const fetchMock = mockFetch(baseOverview, "user");

    renderAt("/admin/setup-status");

    expect(
      await screen.findByRole("heading", { name: "Admin access required" }),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).endsWith("/api/v1/admin/setup-status"),
      ),
    ).toBe(false);
  });
});
