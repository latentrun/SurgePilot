import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

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

const setupStatus = {
  needsBootstrap: false,
  allowSignup: true,
  hasDefaultWorkspace: true,
};

const overviewPayload = {
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

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: {
      "content-type": "application/json",
      ...init.headers,
    },
  });
}

function emptyResponse(init: ResponseInit = {}) {
  return new Response(null, {
    status: init.status ?? 204,
    headers: init.headers,
  });
}

function requestUrl(input: RequestInfo | URL) {
  return input instanceof Request ? input.url : String(input);
}

function unauthenticated() {
  return jsonResponse(
    { code: "UNAUTHENTICATED", message: "Unauthenticated.", requestId: "req" },
    { status: 401 },
  );
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
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("P0 final acceptance", () => {
  it("renders the login form for unauthenticated visitors", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return unauthenticated();
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/login");

    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Create an account" }),
    ).toHaveAttribute("href", "/register");
  });

  it("shows service unavailable copy when setup status cannot be loaded", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return unauthenticated();
      }
      return new Response("", {
        status: 500,
        headers: { "content-type": "text/plain" },
      });
    });

    renderAt("/login");

    expect(
      await screen.findByText(
        "SurgePilot service is temporarily unavailable. Try again in a moment.",
      ),
    ).toBeInTheDocument();
  });

  it("renders first administrator registration copy when bootstrap is needed", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return unauthenticated();
      }
      return jsonResponse({ ...setupStatus, needsBootstrap: true });
    });

    renderAt("/register");

    expect(
      await screen.findByRole("heading", { name: "Create administrator" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create administrator/i }),
    ).toBeInTheDocument();
  });

  it("validates registration fields before submitting to the API", async () => {
    const fetchMock = mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return unauthenticated();
      }
      if (
        requestUrl(input).endsWith("/api/v1/auth/register") ||
        requestUrl(input).includes("/api/v1/overview")
      ) {
        return jsonResponse(
          { code: "TEST_FAILURE", message: "Unexpected submission." },
          { status: 400 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/register");

    await screen.findByRole("heading", { name: "Create account" });
    await userEvent.type(
      screen.getByLabelText("Email"),
      "engineer@example.com",
    );
    await userEvent.type(screen.getByLabelText("Display name"), "Engineer");
    await userEvent.type(screen.getByLabelText("Password"), "short");
    await userEvent.click(
      screen.getByRole("button", { name: /create account/i }),
    );

    expect(
      await screen.findByText(
        "Password must have at least 10 characters, one letter, and one number.",
      ),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).endsWith("/api/v1/auth/register"),
      ),
    ).toBe(false);
  });

  it("signs in and lands on the P0 Overview", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return unauthenticated();
      }
      if (url.endsWith("/api/v1/auth/login")) {
        return jsonResponse(authSession("admin"));
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/login");

    await screen.findByRole("heading", { name: "Sign in" });
    await userEvent.type(screen.getByLabelText("Email"), "admin@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/overview");
    expect(screen.getAllByText(/Last 30 days/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Default Workspace").length,
    ).toBeGreaterThan(0);
  });

  it("completes first administrator registration and lands on Overview", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return unauthenticated();
      }
      if (url.endsWith("/api/v1/auth/register")) {
        return jsonResponse(authSession("admin"));
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse({ ...setupStatus, needsBootstrap: true });
    });

    renderAt("/register");

    await screen.findByRole("heading", { name: "Create administrator" });
    await userEvent.type(
      screen.getByLabelText("Display name"),
      "Admin User",
    );
    await userEvent.type(screen.getByLabelText("Email"), "admin@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password123");
    await userEvent.click(
      screen.getByRole("button", { name: /create administrator/i }),
    );

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/overview");
  });

  it("renders Overview for an authenticated root visit with P0-scoped quick actions", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession("admin"));
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: /Create Scenario/i }),
    ).toHaveAttribute("href", "/scenarios");
    expect(
      screen.getByText(/Last 30 days/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Create Test Plan/i }),
    ).toHaveAttribute("href", "/test-plans");
    expect(
      screen.getByRole("link", { name: /Manage Load Nodes/i }),
    ).toHaveAttribute("href", "/resources/load-nodes");
    const main = screen.getByRole("main");
    expect(
      within(main).queryByText(/Schedule|Grafana|Help|API Catalog/i),
    ).not.toBeInTheDocument();
  });

  it("keeps the authenticated navigation P0-scoped with only Setup Status under Admin", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession("admin"));
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    await screen.findByRole("heading", { name: "Overview" });

    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    for (const label of [
      "Overview",
      "Scenarios",
      "Test Plans",
      "Runs",
      "Env Groups",
      "Dependency Files",
      "Load Nodes",
    ]) {
      expect(
        within(navigation).getByRole("link", { name: label }),
      ).toBeInTheDocument();
    }
    expect(within(navigation).getByText("Admin")).toBeInTheDocument();
    expect(
      within(navigation).getByRole("link", { name: /setup status/i }),
    ).toHaveAttribute("href", "/admin/setup-status");
    for (const label of [
      "Workspaces",
      "Users",
      "System Settings",
      "Schedule",
      "Monitoring",
      "Help",
      "API Catalog",
    ]) {
      expect(
        within(navigation).queryByRole("link", { name: label }),
      ).not.toBeInTheDocument();
    }
  });

  it("hides Admin navigation and blocks direct Admin access for non-Admin users", async () => {
    const fetchMock = mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession("user"));
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    await screen.findByRole("heading", { name: "Overview" });
    const navigation = screen.getByRole("navigation", {
      name: "Primary navigation",
    });
    expect(within(navigation).queryByText("Admin")).not.toBeInTheDocument();
    expect(
      within(navigation).queryByRole("link", { name: /setup status/i }),
    ).not.toBeInTheDocument();

    window.history.pushState({}, "", "/admin/setup-status");
    window.dispatchEvent(new PopStateEvent("popstate"));

    expect(
      await screen.findByRole("heading", { name: "Admin access required" }),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).endsWith("/api/v1/admin/setup-status"),
      ),
    ).toBe(false);
  });

  it("renders Admin Setup Status readiness cards for Admin users only", async () => {
    const fetchMock = mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession("admin"));
      }
      if (url.endsWith("/api/v1/admin/setup-status")) {
        return jsonResponse(setupStatus);
      }
      return jsonResponse(setupStatus);
    });

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

  it("signs out and routes back to the login page", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession("admin"));
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (url.endsWith("/api/v1/auth/logout")) {
        return emptyResponse();
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    await screen.findByRole("heading", { name: "Overview" });
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });
});
