import { StrictMode } from "react";

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

const setupStatus = {
  needsBootstrap: false,
  allowSignup: true,
  hasDefaultWorkspace: true,
  storageAvailable: true,
};

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "admin@example.com",
    displayName: "Admin User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: "01HZW000000000000000000000",
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

const overviewPayload = {
  generatedAt: "2030-06-07T10:30:00.000Z",
  workspace: authSession.defaultWorkspace,
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

function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input.method : init?.method;
}

async function requestBody(input: RequestInfo | URL, init?: RequestInit) {
  if (input instanceof Request) {
    return input.clone().json();
  }
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

function renderAt(path: string, options?: { strict?: boolean }) {
  window.history.pushState({}, "", path);
  return render(
    options?.strict ? (
      <StrictMode>
        <App />
      </StrictMode>
    ) : (
      <App />
    ),
  );
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("P0-00 auth workspace web flow", () => {
  it("renders the labelled animated dashboard demonstration", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(
          {
            code: "UNAUTHENTICATED",
            message: "Unauthenticated.",
            requestId: "req",
          },
          { status: 401 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/");

    await screen.findByRole("heading", {
      name: "A distributed load-testing platform built 100% by AI agents.",
    });
    expect(
      screen.getByText(/ANALYTICS_DASHBOARD_LIVE/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /ANALYTICS_DASHBOARD_LIVE · UI DEMONSTRATION · NOT BENCHMARK DATA/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA/,
      ),
    ).toBeInTheDocument();
    expect(document.querySelector('.counter[data-target="8600"]')).not.toBeNull();
    expect(document.querySelector(".counter-fast")).not.toBeNull();
    expect(screen.getByText("REQ/SEC")).toBeInTheDocument();
    expect(screen.getByText("Recent Test Runs")).toBeInTheDocument();
    expect(document.querySelectorAll("[data-run-row]")).toHaveLength(8);
  });

  it("renders the static marketing landing at root for unauthenticated visitors", async () => {
    const fetchMock = mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(
          {
            code: "UNAUTHENTICATED",
            message: "Unauthenticated.",
            requestId: "req",
          },
          { status: 401 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/");

    expect(
      await screen.findByRole("heading", {
        name: "A distributed load-testing platform built 100% by AI agents.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(screen.getByRole("link", { name: "Sign up" })).toHaveAttribute(
      "href",
      "/register",
    );
    for (const link of screen.getAllByRole("link", { name: "GitHub" })) {
      expect(link).toHaveAttribute(
        "href",
        "https://github.com/latentrun/SurgePilot",
      );
    }
    expect(screen.getByRole("link", { name: "Docs" })).toHaveAttribute(
      "href",
      "https://latentrun.github.io/SurgePilot/docs/",
    );
    expect(screen.getByText("1. Design")).toBeInTheDocument();
    expect(screen.getByText("2. Orchestrate")).toBeInTheDocument();
    expect(screen.getByText("3. Run")).toBeInTheDocument();
    expect(screen.getByText("4. Report")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("1. Design").closest(".reveal-on-scroll"),
      ).toHaveClass("active"),
    );
    expect(screen.getByText("Loop Engineering")).toBeInTheDocument();
    expect(
      screen.getByText((_, element) => element?.textContent === "Review ⇄ Fix"),
    ).toBeInTheDocument();
    expect(screen.getByText("until clean")).toBeInTheDocument();
    expect(
      screen.queryByText("SurgePilot Open Source Project."),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).includes("fonts.googleapis.com"),
      ),
    ).toBe(false);
  });

  it("redirects authenticated root visits to overview", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (requestUrl(input).includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/");

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/overview");
  });
  it("renders the login form", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(
          {
            code: "UNAUTHENTICATED",
            message: "Unauthenticated.",
            requestId: "req",
          },
          { status: 401 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/login");

    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "SurgePilot logo" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("shows service unavailable copy when setup status cannot be loaded", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(
          {
            code: "UNAUTHENTICATED",
            message: "Unauthenticated.",
            requestId: "req",
          },
          { status: 401 },
        );
      }
      return new Response("", {
        status: 500,
        headers: { "content-type": "text/plain" },
      });
    });

    renderAt("/login");

    expect(
      await screen.findByText(
        "SurgePilot service is temporarily unavailable. Try again in a moment or contact an administrator.",
      ),
    ).toBeInTheDocument();
  });

  it("renders first administrator registration copy when bootstrap is needed", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(
          {
            code: "UNAUTHENTICATED",
            message: "Unauthenticated.",
            requestId: "req",
          },
          { status: 401 },
        );
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
        return jsonResponse(
          {
            code: "UNAUTHENTICATED",
            message: "Unauthenticated.",
            requestId: "req",
          },
          { status: 401 },
        );
      }
      if (requestUrl(input).endsWith("/api/v1/auth/register")) {
        return jsonResponse(
          {
            code: "TEST_FAILURE",
            message: "Registration should not submit.",
            requestId: "req",
          },
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
        "Use at least 10 characters with a letter and a number.",
      ),
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).endsWith("/api/v1/auth/register"),
      ),
    ).toBe(false);
  });

  it("renders overview with current user and default workspace", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (requestUrl(input).includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    expect(
      await screen.findByRole("heading", { name: "Overview" }),
    ).toBeInTheDocument();
    expect(
      within(
        screen.getByRole("banner", { name: "Global top bar" }),
      ).queryByText("Admin User"),
    ).not.toBeInTheDocument();
    const userMenuTrigger = screen.getByRole("button", {
      name: "Open user menu for Admin User",
    });
    expect(userMenuTrigger).toBeInTheDocument();
    expect(screen.queryByText("admin@example.com")).not.toBeInTheDocument();
    expect(screen.queryByText("admin")).not.toBeInTheDocument();
    expect(userMenuTrigger).toHaveAttribute("title", "Admin User");
    await userEvent.click(userMenuTrigger);
    expect(
      within(await screen.findByRole("menu")).getByText("Admin User"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Default Workspace").length).toBeGreaterThan(0);
  });

  it("wraps overview in the authenticated AppShell without changing overview content", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (requestUrl(input).includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    expect(
      await screen.findByRole("banner", { name: "Global top bar" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toHaveClass("surgepilot-sidebar-scroll", "min-h-0", "overflow-y-auto");
    expect(screen.getByRole("link", { name: /overview/i })).toHaveAttribute(
      "href",
      "/overview",
    );
    expect(screen.getByRole("link", { name: /env groups/i })).toHaveAttribute(
      "href",
      "/assets/env-groups",
    );
    expect(screen.getByText("Assets")).toBeInTheDocument();
    expect(screen.getByText("Resources")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /api catalog/i })).toHaveAttribute(
      "href",
      "/api-catalog",
    );
    expect(screen.getByRole("link", { name: /monitoring/i })).toHaveAttribute(
      "href",
      "/observability/monitoring",
    );
    expect(screen.getByText(/Current execution activity/)).toBeInTheDocument();
  });

  it("uses semantic sidebar icons instead of initial-letter badges", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (requestUrl(input).includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    const navigation = await screen.findByRole("navigation", {
      name: "Primary navigation",
    });
    const overviewLink = within(navigation).getByRole("link", {
      name: /overview/i,
    });
    const scenariosLink = within(navigation).getByRole("link", {
      name: /scenarios/i,
    });
    const dependencyFilesLink = within(navigation).getByRole("link", {
      name: /dependency files/i,
    });

    expect(within(overviewLink).queryByText("O")).not.toBeInTheDocument();
    expect(within(scenariosLink).queryByText("S")).not.toBeInTheDocument();
    expect(
      within(dependencyFilesLink).queryByText("D"),
    ).not.toBeInTheDocument();
    expect(overviewLink.querySelector("svg")).toBeInTheDocument();
    expect(scenariosLink.querySelector("svg")).toBeInTheDocument();
    expect(dependencyFilesLink.querySelector("svg")).toBeInTheDocument();
  });

  it("uses a compact top-bar user menu for long names", async () => {
    const longNameSession = {
      ...authSession,
      user: {
        ...authSession.user,
        displayName: "Administrator With Very Long Display Name",
      },
    };
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(longNameSession);
      }
      if (requestUrl(input).includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview");

    const userMenuTrigger = await screen.findByRole("button", {
      name: "Open user menu for Administrator With Very Long Display Name",
    });
    expect(within(userMenuTrigger).queryByText("AU")).not.toBeInTheDocument();
    expect(userMenuTrigger.querySelector("svg")).toBeInTheDocument();
    expect(
      within(
        screen.getByRole("banner", { name: "Global top bar" }),
      ).queryByText("Administrator With Very Long Display Name"),
    ).not.toBeInTheDocument();
    expect(
      within(userMenuTrigger).queryByText("admin@example.com"),
    ).not.toBeInTheDocument();
    expect(userMenuTrigger).toHaveAttribute(
      "title",
      "Administrator With Very Long Display Name",
    );

    await userEvent.click(userMenuTrigger);
    expect(
      within(await screen.findByRole("menu")).getByText(
        "Administrator With Very Long Display Name",
      ),
    ).toBeInTheDocument();
  });

  it("highlights Assets Env Groups on its route", async () => {
    mockFetch((input) => {
      if (requestUrl(input).endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (requestUrl(input).includes("/api/v1/env-groups")) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    const envGroupsLink = await screen.findByRole("link", {
      name: /env groups/i,
    });
    expect(envGroupsLink).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("heading", { name: "Env Groups" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("No Env Groups yet")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "New Env Group" }),
    ).not.toHaveClass("font-mono");
    expect(
      screen.getByRole("button", { name: "New Env Group" }),
    ).not.toHaveClass("uppercase");
  });

  it("creates an Env Group and sends variables through the generated API route", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (
        url.includes("/api/v1/env-groups") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      if (
        url.endsWith("/api/v1/env-groups") &&
        requestMethod(input, init) === "POST"
      ) {
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
            name: "Staging",
            description: "Staging variables",
            variables: {
              BASE_URL: { type: "plain", value: "https://example.test" },
            },
            variableCount: 1,
            inUse: false,
            createdBy: authSession.user.id,
            updatedBy: authSession.user.id,
            createdAt: "2030-05-28T00:00:00Z",
            updatedAt: "2030-05-28T00:00:00Z",
          },
          { status: 201 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("No Env Groups yet");
    await userEvent.click(
      screen.getByRole("button", { name: /new env group/i }),
    );
    await userEvent.type(screen.getByLabelText("Name"), "Staging");
    await userEvent.type(
      screen.getByLabelText("Description"),
      "Staging variables",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add variable/i }),
    );
    await userEvent.type(screen.getByLabelText("Key"), "BASE_URL");
    await userEvent.type(
      screen.getByLabelText("Value"),
      "https://example.test",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /save env group/i }),
    );

    await waitFor(async () => {
      const createCall = fetchMock.mock.calls.find(
        ([input, init]) =>
          requestUrl(input).endsWith("/api/v1/env-groups") &&
          requestMethod(input, init) === "POST",
      );
      expect(createCall).toBeDefined();
      expect((createCall?.[0] as Request).headers.get("x-workspace-id")).toBe(
        authSession.defaultWorkspace.id,
      );
      expect(await requestBody(createCall?.[0] as Request)).toMatchObject({
        name: "Staging",
        description: "Staging variables",
        variables: {
          BASE_URL: { type: "plain", value: "https://example.test" },
        },
      });
    });
  });

  it("keeps Env Group variable rows in user order while typing keys", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (
        url.includes("/api/v1/env-groups") &&
        requestMethod(input) === "GET"
      ) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("No Env Groups yet");
    await userEvent.click(
      screen.getByRole("button", { name: /new env group/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add variable/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /add variable/i }),
    );

    await userEvent.type(screen.getAllByLabelText("Key")[0], "d");
    expect(
      screen
        .getAllByLabelText<HTMLInputElement>("Key")
        .map((input) => input.value),
    ).toEqual(["d", ""]);

    await userEvent.click(
      screen.getByRole("button", { name: /add variable/i }),
    );
    expect(
      screen
        .getAllByLabelText<HTMLInputElement>("Key")
        .map((input) => input.value),
    ).toEqual(["", "d", ""]);
  });

  it("loads edit detail and submits full variable replacement", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (
        url.includes("/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7A") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({
          id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
          name: "Staging",
          description: "Staging variables",
          variables: {
            TOKEN: { type: "plain", value: "fake-token" },
            BASE_URL: { type: "plain", value: "https://example.test" },
          },
          variableCount: 2,
          inUse: false,
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-05-28T00:00:00Z",
          updatedAt: "2030-05-28T00:00:00Z",
        });
      }
      if (
        url.includes("/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7A") &&
        requestMethod(input, init) === "PATCH"
      ) {
        return jsonResponse({
          id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
          name: "Staging",
          description: "Staging variables",
          variables: {
            BASE_URL: { type: "plain", value: "https://staging.example.test" },
          },
          variableCount: 1,
          inUse: false,
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-05-28T00:00:00Z",
          updatedAt: "2030-05-28T00:00:00Z",
        });
      }
      if (
        url.includes("/api/v1/env-groups") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
              name: "Staging",
              description: "Staging variables",
              variableCount: 2,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-05-28T00:00:00Z",
              updatedAt: "2030-05-28T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("Staging");
    await userEvent.click(
      screen.getByRole("button", { name: /edit staging/i }),
    );
    expect(await screen.findByDisplayValue("BASE_URL")).toBeInTheDocument();
    const baseUrlValue = screen.getByDisplayValue("https://example.test");
    await userEvent.clear(baseUrlValue);
    await userEvent.type(baseUrlValue, "https://staging.example.test");
    await userEvent.click(
      screen.getByRole("button", { name: /remove token/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: /save env group/i }),
    );

    await waitFor(async () => {
      const patchCall = fetchMock.mock.calls.find(
        ([input, init]) =>
          requestUrl(input).includes(
            "/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7A",
          ) && requestMethod(input, init) === "PATCH",
      );
      expect(patchCall).toBeDefined();
      expect(await requestBody(patchCall?.[0] as Request)).toMatchObject({
        variables: {
          BASE_URL: { type: "plain", value: "https://staging.example.test" },
        },
      });
    });
  });

  it("opens the Env Group edit form when crypto randomUUID is unavailable", async () => {
    vi.stubGlobal("crypto", {});
    mockFetch((input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (
        url.includes("/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7A") &&
        method === "GET"
      ) {
        return jsonResponse({
          id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
          name: "Staging",
          description: "Staging variables",
          variables: {
            BASE_URL: { type: "plain", value: "https://example.test" },
          },
          variableCount: 1,
          inUse: false,
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-05-28T00:00:00Z",
          updatedAt: "2030-05-28T00:00:00Z",
        });
      }
      if (url.includes("/api/v1/env-groups") && method === "GET") {
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
              name: "Staging",
              description: "Staging variables",
              variableCount: 1,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-05-28T00:00:00Z",
              updatedAt: "2030-05-28T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("Staging");
    await userEvent.click(
      screen.getByRole("button", { name: /edit staging/i }),
    );

    expect(await screen.findByDisplayValue("BASE_URL")).toBeInTheDocument();
    expect(
      screen.getByDisplayValue("https://example.test"),
    ).toBeInTheDocument();
  });

  it("rehydrates the edit form when reopening the same cached Env Group detail", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (
        url.includes("/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7A") &&
        method === "GET"
      ) {
        return jsonResponse({
          id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
          name: "Staging",
          description: "Staging variables",
          variables: {
            BASE_URL: { type: "plain", value: "https://example.test" },
          },
          variableCount: 1,
          inUse: false,
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-05-28T00:00:00Z",
          updatedAt: "2030-05-28T00:00:00Z",
        });
      }
      if (url.includes("/api/v1/env-groups") && method === "GET") {
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
              name: "Staging",
              description: "Staging variables",
              variableCount: 1,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-05-28T00:00:00Z",
              updatedAt: "2030-05-28T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("Staging");
    await userEvent.click(
      screen.getByRole("button", { name: /edit staging/i }),
    );
    expect(await screen.findByDisplayValue("Staging")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await userEvent.click(
      screen.getByRole("button", { name: /edit staging/i }),
    );

    expect(screen.getByLabelText<HTMLInputElement>("Name").value).toBe(
      "Staging",
    );
    expect(screen.getByLabelText<HTMLInputElement>("Description").value).toBe(
      "Staging variables",
    );
    expect(screen.getByLabelText<HTMLInputElement>("Key").value).toBe(
      "BASE_URL",
    );
  });

  it("handles duplicate and delete in-use errors", async () => {
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (url.endsWith("/duplicate") && requestMethod(input, init) === "POST") {
        return jsonResponse({ id: "copy" }, { status: 201 });
      }
      if (
        url.includes("/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7A") &&
        requestMethod(input, init) === "DELETE"
      ) {
        return jsonResponse(
          {
            code: "ENV_GROUP_IN_USE",
            message: "Env Group is in use.",
            requestId: "req",
          },
          { status: 409 },
        );
      }
      if (
        url.includes("/api/v1/env-groups") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
              name: "Staging",
              description: null,
              variableCount: 0,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-05-28T00:00:00Z",
              updatedAt: "2030-05-28T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("Staging");
    await userEvent.click(
      screen.getByRole("button", { name: /duplicate staging/i }),
    );
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) =>
          requestUrl(input).endsWith("/duplicate"),
        ),
      ).toBe(true);
    });
    await userEvent.click(
      screen.getByRole("button", { name: /delete staging/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByText(
        "This Env Group is used by a scenario or test plan and cannot be deleted yet.",
      ),
    ).toBeInTheDocument();
  });

  it("requests the next Env Group page when more results exist", async () => {
    const fetchMock = mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.includes("/api/v1/env-groups")) {
        const request = new URL(url);
        const page = request.searchParams.get("page") ?? "1";
        return jsonResponse({
          items: [
            {
              id:
                page === "1"
                  ? "01HZX3Y9M0E9W7Z6M5QK9S8P7A"
                  : "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
              name: page === "1" ? "Page One" : "Page Two",
              description: null,
              variableCount: 0,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-05-28T00:00:00Z",
              updatedAt: "2030-05-28T00:00:00Z",
            },
          ],
          page: Number(page),
          pageSize: 20,
          total: 21,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    expect(await screen.findByText("Page One")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /next page/i }));

    expect(await screen.findByText("Page Two")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) => {
        const url = new URL(requestUrl(input));
        return (
          url.pathname.endsWith("/api/v1/env-groups") &&
          url.searchParams.get("page") === "2"
        );
      }),
    ).toBe(true);
  });

  it("returns to the previous Env Group page after deleting the last item on the current page", async () => {
    let deleted = false;
    let requestedPageOneAfterDelete = false;
    mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (
        url.includes("/api/v1/env-groups/01HZX3Y9M0E9W7Z6M5QK9S8P7B") &&
        requestMethod(input, init) === "DELETE"
      ) {
        deleted = true;
        return emptyResponse();
      }
      if (
        url.includes("/api/v1/env-groups") &&
        requestMethod(input, init) === "GET"
      ) {
        const request = new URL(url);
        const page = request.searchParams.get("page") ?? "1";
        if (deleted && page === "1") {
          requestedPageOneAfterDelete = true;
        }
        if (page === "2") {
          if (deleted) {
            return jsonResponse({
              items: [],
              page: 2,
              pageSize: 20,
              total: 20,
            });
          }
          return jsonResponse({
            items: [
              {
                id: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
                name: "Last Page Two",
                description: null,
                variableCount: 0,
                inUse: false,
                createdBy: authSession.user.id,
                updatedBy: authSession.user.id,
                createdAt: "2030-05-28T00:00:00Z",
                updatedAt: "2030-05-28T00:00:00Z",
              },
            ],
            page: 2,
            pageSize: 20,
            total: 21,
          });
        }
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
              name: "Page One",
              description: null,
              variableCount: 0,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-05-28T00:00:00Z",
              updatedAt: "2030-05-28T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: deleted ? 20 : 21,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    expect(await screen.findByText("Page One")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /next page/i }));
    expect(await screen.findByText("Last Page Two")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /delete last page two/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(await screen.findByText("Page One")).toBeInTheDocument();
    expect(screen.queryByText("No Env Groups yet")).not.toBeInTheDocument();
    expect(requestedPageOneAfterDelete).toBe(true);
  });

  it("maps API variable validation errors back to the matching row field", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (
        url.endsWith("/api/v1/env-groups") &&
        requestMethod(input, init) === "POST"
      ) {
        return jsonResponse(
          {
            code: "VALIDATION_ERROR",
            message: "Validation failed.",
            requestId: "req",
            details: [
              {
                field: "variables.BASE_URL",
                code: "INVALID_FIELD",
                message: "Check this value and try again.",
              },
            ],
          },
          { status: 422 },
        );
      }
      if (
        url.includes("/api/v1/env-groups") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/env-groups");

    await screen.findByText("No Env Groups yet");
    await userEvent.click(
      screen.getByRole("button", { name: /new env group/i }),
    );
    await userEvent.type(screen.getByLabelText("Name"), "Staging");
    await userEvent.click(
      screen.getByRole("button", { name: /add variable/i }),
    );
    await userEvent.type(screen.getByLabelText("Key"), "BASE_URL");
    await userEvent.type(
      screen.getByLabelText("Value"),
      "https://example.test",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /save env group/i }),
    );

    expect(
      await screen.findByText("Check this value and try again."),
    ).toBeInTheDocument();
  });

  it("logs out and routes back to an activated marketing landing", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (
        url.endsWith("/api/v1/auth/logout") &&
        requestMethod(input, init) === "POST"
      ) {
        return emptyResponse();
      }
      if (url.includes("/api/v1/overview")) {
        return jsonResponse(overviewPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/overview", { strict: true });

    await screen.findAllByText("Default Workspace");
    await user.click(
      screen.getByRole("button", { name: "Open user menu for Admin User" }),
    );
    await user.click(await screen.findByRole("menuitem", { name: /logout/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
    });
    expect(
      await screen.findByRole("link", { name: /^get started$/i }),
    ).toBeInTheDocument();

    expect(document.querySelector(".counter, .counter-fast")).not.toBeNull();
    expect(
      screen.getByText("1. Design").closest(".reveal-on-scroll"),
    ).toHaveClass("active");
    expect(
      screen.getByText(
        /ANALYTICS_DASHBOARD_LIVE · UI DEMONSTRATION · NOT BENCHMARK DATA/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA/,
      ),
    ).toBeInTheDocument();

    window.history.pushState(null, "", "/overview");
    window.dispatchEvent(new PopStateEvent("popstate"));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/login");
    });
    expect(
      await screen.findByRole("heading", { name: "Sign in" }),
    ).toBeInTheDocument();

    const logoutCall = fetchMock.mock.calls.find(([input]) =>
      requestUrl(input).endsWith("/api/v1/auth/logout"),
    );
    expect(logoutCall).toBeDefined();
    expect(logoutCall?.[0]).toBeInstanceOf(Request);
    expect((logoutCall?.[0] as Request).method).toBe("POST");
    expect((logoutCall?.[0] as Request).headers.get("x-csrf-token")).toBe(
      "csrf-token",
    );
  });
});

describe("P0-02 Dependency Files web flow", () => {
  const dependencyFile = {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
    filename: "users.csv",
    contentType: "text/csv",
    sizeBytes: 14,
    sha256: "7f83b1657ff1fc53b92dc18148a1d65dfa135d0f2b018d8c828b4c5f7d2f2f12",
    inUse: false,
    createdBy: authSession.user.id,
    createdAt: "2030-05-30T00:00:00Z",
  };

  it("highlights Assets Dependency Files and renders the empty state without P1/P2 navigation", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.includes("/api/v1/dependency-files")) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    const dependencyFilesLink = await screen.findByRole("link", {
      name: /dependency files/i,
    });
    expect(dependencyFilesLink).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("heading", { name: "Dependency Files" }),
    ).toBeInTheDocument();
    expect(
      await screen.findByText("No Dependency Files yet"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Upload Dependency File" }),
    ).not.toHaveClass("font-mono");
    expect(
      screen.getByRole("button", { name: "Upload Dependency File" }),
    ).not.toHaveClass("uppercase");
    expect(screen.getByRole("link", { name: /api catalog/i })).toHaveAttribute(
      "href",
      "/api-catalog",
    );
    expect(screen.queryByText(/preview/i)).not.toBeInTheDocument();
  });

  it("shows English file picker copy before a file is selected", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.includes("/api/v1/dependency-files")) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    await screen.findByText("No Dependency Files yet");
    await userEvent.click(
      screen.getByRole("button", { name: /upload dependency file/i }),
    );

    expect(screen.getByText("Choose file")).toBeInTheDocument();
    expect(screen.getByText("No file selected")).toBeInTheDocument();
  });

  it("uploads a file, sends workspace and csrf headers, and refreshes the list", async () => {
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (
        url.endsWith("/api/v1/dependency-files") &&
        requestMethod(input, init) === "POST"
      ) {
        return jsonResponse(dependencyFile, { status: 201 });
      }
      if (
        url.includes("/api/v1/dependency-files") &&
        requestMethod(input, init) === "GET"
      ) {
        const uploaded = fetchMock.mock.calls.some(
          ([callInput, callInit]) =>
            requestUrl(callInput).endsWith("/api/v1/dependency-files") &&
            requestMethod(callInput, callInit) === "POST",
        );
        return jsonResponse({
          items: uploaded ? [dependencyFile] : [],
          page: 1,
          pageSize: 20,
          total: uploaded ? 1 : 0,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    await screen.findByText("No Dependency Files yet");
    await userEvent.click(
      screen.getByRole("button", { name: /upload dependency file/i }),
    );
    const file = new File(["id,name\n1,Ada\n"], "users.csv", {
      type: "text/csv",
    });
    await userEvent.upload(screen.getByLabelText("File"), file);
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByText("users.csv")).toBeInTheDocument();
    const uploadCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).endsWith("/api/v1/dependency-files") &&
        requestMethod(input, init) === "POST",
    );
    expect(uploadCall).toBeDefined();
    expect(uploadCall?.[0]).toBeInstanceOf(Request);
    expect((uploadCall?.[0] as Request).headers.get("x-workspace-id")).toBe(
      authSession.defaultWorkspace.id,
    );
    expect((uploadCall?.[0] as Request).headers.get("x-csrf-token")).toBe(
      "csrf-token",
    );
  });

  it("shows upload validation and API error branches", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (
        url.endsWith("/api/v1/dependency-files") &&
        requestMethod(input, init) === "POST"
      ) {
        return jsonResponse(
          {
            code: "DEPENDENCY_FILE_NAME_CONFLICT",
            message: "Dependency File filename already exists.",
            requestId: "req",
          },
          { status: 409 },
        );
      }
      if (
        url.includes("/api/v1/dependency-files") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    await screen.findByText("No Dependency Files yet");
    await userEvent.click(
      screen.getByRole("button", { name: /upload dependency file/i }),
    );
    await userEvent.upload(
      screen.getByLabelText("File"),
      new File(["x"], "bad name.csv"),
    );
    expect(
      await screen.findByText(
        "Use A-Z, a-z, numbers, dots, underscores, or dashes only.",
      ),
    ).toBeInTheDocument();

    await userEvent.upload(
      screen.getByLabelText("File"),
      new File(["x"], "users.csv", { type: "text/csv" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(
      await screen.findByText(
        "A Dependency File with this filename already exists.",
      ),
    ).toBeInTheDocument();
  });

  it("shows file-level upload validation details returned by the API", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (
        url.endsWith("/api/v1/dependency-files") &&
        requestMethod(input, init) === "POST"
      ) {
        return jsonResponse(
          {
            code: "VALIDATION_ERROR",
            message: "Validation failed.",
            requestId: "req",
            details: [
              {
                field: "file",
                code: "UNSUPPORTED_FILE_EXTENSION",
                message: "Only .csv files are allowed.",
              },
            ],
          },
          { status: 422 },
        );
      }
      if (
        url.includes("/api/v1/dependency-files") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    await screen.findByText("No Dependency Files yet");
    await userEvent.click(
      screen.getByRole("button", { name: /upload dependency file/i }),
    );
    await userEvent.upload(
      screen.getByLabelText("File"),
      new File(["x"], "users.csv", { type: "text/csv" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));

    expect(
      await screen.findByText("Only .csv files are allowed."),
    ).toBeInTheDocument();
  });

  it("downloads through the API and handles delete FILE_IN_USE", async () => {
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (url.endsWith("/download")) {
        return new Response(new Blob(["id,name\n1,Ada\n"]), {
          status: 200,
          headers: { "content-type": "application/octet-stream" },
        });
      }
      if (
        url.includes("/api/v1/dependency-files/01HZX3Y9M0E9W7Z6M5QK9S8P7D") &&
        requestMethod(input, init) === "DELETE"
      ) {
        return jsonResponse(
          { code: "FILE_IN_USE", message: "File is in use.", requestId: "req" },
          { status: 409 },
        );
      }
      if (
        url.includes("/api/v1/dependency-files") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({
          items: [dependencyFile],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    await screen.findByText("users.csv");
    await userEvent.click(
      screen.getByRole("button", { name: /download users.csv/i }),
    );
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) =>
          requestUrl(input).endsWith("/download"),
        ),
      ).toBe(true);
    });

    await userEvent.click(
      screen.getByRole("button", { name: /delete users.csv/i }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(
      await screen.findByText(
        "This file is used by a scenario or test plan and cannot be deleted yet.",
      ),
    ).toBeInTheDocument();
  });

  it("shows storage unavailable list error with retry", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.includes("/api/v1/dependency-files")) {
        return jsonResponse(
          {
            code: "STORAGE_UNAVAILABLE",
            message: "Storage is unavailable.",
            requestId: "req",
          },
          { status: 503 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/assets/dependency-files");

    expect(
      await screen.findByText(
        "File storage is temporarily unavailable. Try again later.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});

describe("P0-03 Load Nodes web flow", () => {
  const node = {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    scope: "workspace",
    workspaceId: authSession.defaultWorkspace.id,
    host: "load-node-01.internal",
    sshPort: 22,
    sshUser: "surgepilot",
    runnerHome: "/opt/surgepilot/runner",
    authType: "password",
    credentialConfigured: true,
    credentialFingerprint: "SHA256:test",
    generatedPublicKey: null,
    maintainer: "Performance Team",
    remark: "Private node",
    status: "idle",
    lastStatusReason: null,
    runnerVersion: "0.1.0",
    bundleVersion: "p0-03",
    lastInitializedAt: "2030-05-31T10:00:00Z",
    lastCheckedAt: "2030-05-31T10:00:00Z",
    lastHeartbeatAt: null,
    currentRunId: null,
    lastInitAttemptId: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
    createdAt: "2030-05-31T09:00:00Z",
    updatedAt: "2030-05-31T10:00:00Z",
  };

  it("lists, filters, initializes, and opens sanitized logs", async () => {
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        return jsonResponse({
          effectiveUrl: "http://192.168.1.50:8080",
          source: "configured",
          readiness: "ready",
          message:
            "Load Node API Base URL is statically valid. It has not been tested from a Load Node.",
        });
      }
      if (url.endsWith("/initialize")) {
        return jsonResponse(
          {
            node: { id: node.id, status: "initializing" },
            attempt: {
              id: node.lastInitAttemptId,
              status: "queued",
              message: "Initialization queued.",
            },
          },
          { status: 202 },
        );
      }
      if (
        url.endsWith(
          `/api/v1/load-nodes/${node.id}/init-attempts/${node.lastInitAttemptId}`,
        )
      ) {
        return jsonResponse({
          id: node.lastInitAttemptId,
          nodeId: node.id,
          status: "succeeded",
          startedAt: "2030-05-31T09:59:00Z",
          finishedAt: "2030-05-31T10:00:00Z",
          errorCode: null,
          message: "Initialization succeeded.",
          sanitizedLogTail: "[info] setup output sanitized",
          runnerVersion: "0.1.0",
          bundleVersion: "p0-03",
          createdAt: "2030-05-31T09:58:59Z",
          updatedAt: "2030-05-31T10:00:00Z",
        });
      }
      if (url.endsWith(`/api/v1/load-nodes/${node.id}/init-attempts`)) {
        return jsonResponse({
          items: [
            {
              id: node.lastInitAttemptId,
              nodeId: node.id,
              status: "succeeded",
              startedAt: "2030-05-31T09:59:00Z",
              finishedAt: "2030-05-31T10:00:00Z",
              errorCode: null,
              message: "Initialization succeeded.",
              createdAt: "2030-05-31T09:58:59Z",
            },
          ],
          limit: 20,
          offset: 0,
          total: 1,
        });
      }
      if (
        url.includes("/api/v1/load-nodes") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({ items: [node], limit: 20, offset: 0, total: 1 });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/resources/load-nodes");

    expect(
      await screen.findByText("load-node-01.internal"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Idle").length).toBeGreaterThan(0);
    await userEvent.selectOptions(
      screen.getByLabelText("Status filter"),
      "idle",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /initialize load-node-01/i }),
    );
    expect(
      await screen.findByRole("heading", { name: "Reinitialize Load Node?" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Load Node API")).toBeInTheDocument();
    expect(screen.getByText("http://192.168.1.50:8080")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reinitialize" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          requestUrl(input).endsWith("/initialize"),
        ),
      ).toBe(true),
    );
    const initializeCall = fetchMock.mock.calls.find(([input]) =>
      requestUrl(input).endsWith("/initialize"),
    );
    await expect(
      requestBody(initializeCall![0], initializeCall![1]),
    ).resolves.toMatchObject({ force: true });
    await userEvent.click(
      screen.getByRole("button", { name: /view logs load-node-01/i }),
    );
    expect(
      await screen.findByText("[info] setup output sanitized"),
    ).toBeInTheDocument();
  });

  it("registers a private node with generated key and shows the installation key", async () => {
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        return jsonResponse({
          effectiveUrl: null,
          source: "missing",
          readiness: "missing",
          message: "Load Node API Base URL is not configured.",
        });
      }
      if (url.endsWith("/api/v1/load-nodes/ssh-host-key/scan")) {
        return jsonResponse({
          host: "load-node-02.internal",
          sshPort: 22,
          algorithm: "ssh-ed25519",
          publicKey: "AAAAHostKey",
          fingerprintSha256: "SHA256:testHostKey",
          knownHostsLine: "load-node-02.internal ssh-ed25519 AAAAHostKey",
          scannedAt: "2030-07-07T00:00:00Z",
        });
      }
      if (
        url.endsWith("/api/v1/load-nodes") &&
        requestMethod(input, init) === "POST"
      ) {
        return jsonResponse(
          {
            ...node,
            authType: "generated_key",
            generatedPublicKey: "ssh-ed25519 AAAA surgepilot-generated",
            status: "uninitialized",
          },
          { status: 201 },
        );
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/resources/load-nodes/new");

    await screen.findByRole("heading", { name: "Register Load Node" });
    expect(screen.getByText("Load Node API")).toBeInTheDocument();
    expect(
      await screen.findByText(/future remote runs will be blocked/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open System Settings" }),
    ).toHaveAttribute("href", "/admin/system-settings");
    await userEvent.type(
      screen.getByLabelText("Host/IP"),
      "load-node-02.internal",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Authentication method"),
      "generated_key",
    );
    await userEvent.click(screen.getByRole("button", { name: "Scan key" }));
    expect(await screen.findByText("SHA256:testHostKey")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Register Load Node" }),
    );

    expect(await screen.findByText("Load Node Registered")).toBeInTheDocument();
    expect(screen.getByText(/ssh-ed25519 AAAA/)).toBeInTheDocument();
    expect(
      screen.getByText(/Before initializing, confirm the host meets/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Initialization does not use this URL/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Ubuntu 24.04\+ or Debian 12\+/),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith(
      "ssh-ed25519 AAAA surgepilot-generated",
    );
    expect(await screen.findByText("Copied.")).toBeInTheDocument();

    await waitFor(async () => {
      const createCall = fetchMock.mock.calls.find(
        ([input, init]) =>
          requestUrl(input).endsWith("/api/v1/load-nodes") &&
          requestMethod(input, init) === "POST",
      );
      expect(createCall).toBeDefined();
      expect(await requestBody(createCall?.[0] as Request)).toMatchObject({
        scope: "workspace",
        host: "load-node-02.internal",
        credential: { authType: "generated_key" },
      });
    });
  });

  it("shows contact-admin connectivity guidance to non-admin Load Node users", async () => {
    const memberSession = {
      ...authSession,
      user: {
        ...authSession.user,
        role: "user",
      },
      permissions: {
        canManageWorkspaces: false,
        canManageUsers: false,
        canManageSystemSettings: false,
        canViewSetupStatus: false,
      },
    };
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(memberSession);
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        return jsonResponse({
          effectiveUrl: null,
          source: "missing",
          readiness: "missing",
          message: "Load Node API Base URL is not configured.",
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/resources/load-nodes/new");

    await screen.findByRole("heading", { name: "Register Load Node" });
    expect(
      await screen.findByText(
        "Contact an administrator to update System Settings.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Open System Settings" }),
    ).not.toBeInTheDocument();
  });

  it("shows load node host requirements and copies the verification command", async () => {
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        return jsonResponse({
          effectiveUrl: "http://192.168.1.50:8080",
          source: "configured",
          readiness: "ready",
          message:
            "Load Node API Base URL is statically valid. It has not been tested from a Load Node.",
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/resources/load-nodes/new");

    await screen.findByRole("heading", { name: "Register Load Node" });
    expect(
      screen.getByRole("heading", { name: "Requirements" }),
    ).toBeInTheDocument();
    expect(screen.getByText("OS:")).toBeInTheDocument();
    expect(screen.getByText("Ubuntu 24.04+ or Debian 12+")).toBeInTheDocument();
    expect(screen.getByText("CPU:")).toBeInTheDocument();
    expect(
      screen.getByText("x86_64 (amd64) or aarch64 (arm64)"),
    ).toBeInTheDocument();
    expect(screen.getByText("Access:")).toBeInTheDocument();
    expect(
      screen.getByText("SSH reachable from the SurgePilot API"),
    ).toBeInTheDocument();
    expect(screen.getByText("Dependencies:")).toBeInTheDocument();
    expect(screen.getByText("tar and a POSIX shell")).toBeInTheDocument();
    expect(screen.getByText("Base runtime:")).toBeInTheDocument();
    expect(screen.getByText("Java 11+ and python3 3.12+")).toBeInTheDocument();
    expect(screen.getByText("Verify on host")).toBeInTheDocument();
    expect(
      screen.getByText(
        'uname -m && (. /etc/os-release; echo "$PRETTY_NAME") && java -version && python3 --version && tar --version',
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(writeText).toHaveBeenCalledWith(
      'uname -m && (. /etc/os-release; echo "$PRETTY_NAME") && java -version && python3 --version && tar --version',
    );
    expect(await screen.findByText("Copied.")).toBeInTheDocument();
  });

  it("updates credentials and surfaces busy archive errors", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.endsWith("/credentials"))
        return jsonResponse({ ...node, status: "uninitialized" });
      if (
        url.includes("/api/v1/load-nodes") &&
        requestMethod(input, init) === "DELETE"
      ) {
        return jsonResponse(
          { code: "LOAD_NODE_BUSY", message: "Busy.", requestId: "req" },
          { status: 409 },
        );
      }
      if (
        url.includes("/api/v1/load-nodes") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({
          items: [{ ...node, status: "busy" }],
          limit: 20,
          offset: 0,
          total: 1,
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/resources/load-nodes");

    expect(
      await screen.findByText("load-node-01.internal"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Running").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /archive load-node-01/i }),
    ).toBeDisabled();
  });
});

describe("P1-03 admin system settings", () => {
  const settingsPayload = {
    settings: {
      allowSignup: true,
      loadSoftLimitWarningConcurrency: 1000,
      jmeterMemoryXmx: "4G",
      maxScenarioItemsPerTestPlan: 20,
      maxSlaRulesPerTestPlan: 5,
      maxRunDurationSeconds: 86400,
      maxRampUpSeconds: 86400,
      maxDelaySeconds: 86400,
      maxIterations: 1000000,
      maxTargetRps: 100000,
      dependencyFileMaxBytes: 104857600,
      dependencyFileAllowedExtensions: [".csv", ".txt"],
      dependencyFilePreviewMaxBytes: 65536,
      dependencyFilePreviewBinaryDenyExtensions: [".png", ".zip"],
      loadNodeApiBaseUrl: "http://192.168.1.50:8080",
    },
    sensitiveStatus: {
      runnerInternalTokenConfigured: true,
      sshCredentialEncryptionKeyConfigured: false,
      minioCredentialsConfigured: true,
    },
  };

  it("renders editable policy settings and read-only deployment status without sensitive controls", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        return jsonResponse({
          effectiveUrl: "http://192.168.1.50:8080",
          source: "configured",
          readiness: "ready",
          message:
            "Load Node API Base URL is statically valid. It has not been tested from a Load Node.",
        });
      }
      if (url.endsWith("/api/v1/admin/system-settings")) {
        if (requestMethod(input, init) === "PATCH") {
          return jsonResponse(settingsPayload);
        }
        return jsonResponse(settingsPayload);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/admin/system-settings");

    expect(
      await screen.findByRole("heading", { name: "System Settings" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByLabelText("Dependency file allowed extensions"),
      ).toHaveValue(".csv, .txt"),
    );
    expect(screen.getByLabelText("Allow local signup")).toBeChecked();
    expect(screen.getByLabelText("JMeter memory Xmx")).toHaveValue("4G");
    expect(screen.getByLabelText("Load Node API Base URL")).toHaveValue(
      "http://192.168.1.50:8080",
    );
    expect(
      screen.getByLabelText("Max Scenario items per Test Plan"),
    ).toHaveValue(20);
    expect(screen.getByText("Runner internal token")).toBeInTheDocument();
    expect(screen.getAllByText("Configured")).toHaveLength(2);
    expect(
      screen.getByText("SSH credential encryption key"),
    ).toBeInTheDocument();
    expect(screen.getByText("Missing")).toBeInTheDocument();
    expect(
      screen.queryByText(/single node concurrency hard limit/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/grafana/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/influx/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/monitoring token/i)).not.toBeInTheDocument();
  });

  it("submits normalized System Settings payload", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        return jsonResponse({
          effectiveUrl: "http://192.168.1.50:8080",
          source: "configured",
          readiness: "ready",
          message:
            "Load Node API Base URL is statically valid. It has not been tested from a Load Node.",
        });
      }
      if (url.endsWith("/api/v1/admin/system-settings")) {
        if (requestMethod(input, init) === "PATCH") {
          return jsonResponse(settingsPayload);
        }
        return jsonResponse(settingsPayload);
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/admin/system-settings");

    await waitFor(() =>
      expect(
        screen.getByLabelText("Dependency file allowed extensions"),
      ).toHaveValue(".csv, .txt"),
    );
    await userEvent.clear(screen.getByLabelText("JMeter memory Xmx"));
    await userEvent.type(screen.getByLabelText("JMeter memory Xmx"), "6G");
    await userEvent.clear(screen.getByLabelText("Load Node API Base URL"));
    await userEvent.type(
      screen.getByLabelText("Load Node API Base URL"),
      "https://surgepilot.example.test",
    );
    await userEvent.clear(
      screen.getByLabelText("Dependency file allowed extensions"),
    );
    await userEvent.type(
      screen.getByLabelText("Dependency file allowed extensions"),
      "csv, .TXT,  .json",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save Settings" }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            requestUrl(input).endsWith("/api/v1/admin/system-settings") &&
            requestMethod(input, init) === "PATCH",
        ),
      ).toBe(true),
    );
    const patchCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).endsWith("/api/v1/admin/system-settings") &&
        requestMethod(input, init) === "PATCH",
    );
    expect(patchCall).toBeDefined();
    await expect(
      requestBody(patchCall![0], patchCall![1]),
    ).resolves.toMatchObject({
      jmeterMemoryXmx: "6G",
      dependencyFileAllowedExtensions: [".csv", ".txt", ".json"],
      loadSoftLimitWarningConcurrency: 1000,
      maxScenarioItemsPerTestPlan: 20,
      dependencyFilePreviewBinaryDenyExtensions: [".png", ".zip"],
      loadNodeApiBaseUrl: "https://surgepilot.example.test",
    });
  });

  it("refreshes Load Node connectivity summary after saving settings", async () => {
    let summaryRequests = 0;
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) {
        return jsonResponse(authSession);
      }
      if (url.endsWith("/api/v1/auth/csrf")) {
        return jsonResponse({ csrfToken: "csrf-token" });
      }
      if (url.endsWith("/api/v1/load-nodes/connectivity-summary")) {
        summaryRequests += 1;
        if (summaryRequests === 1) {
          return jsonResponse({
            effectiveUrl: null,
            source: "missing",
            readiness: "missing",
            message: "Load Node API Base URL is not configured.",
          });
        }
        return jsonResponse({
          effectiveUrl: "https://surgepilot.example.test",
          source: "configured",
          readiness: "ready",
          message:
            "Load Node API Base URL is statically valid. It has not been tested from a Load Node.",
        });
      }
      if (url.endsWith("/api/v1/admin/system-settings")) {
        if (requestMethod(input, init) === "PATCH") {
          return jsonResponse({
            ...settingsPayload,
            settings: {
              ...settingsPayload.settings,
              loadNodeApiBaseUrl: "https://surgepilot.example.test",
            },
          });
        }
        return jsonResponse({
          ...settingsPayload,
          settings: { ...settingsPayload.settings, loadNodeApiBaseUrl: null },
        });
      }
      return jsonResponse(setupStatus);
    });

    renderAt("/admin/system-settings");

    await screen.findByText("Not configured");
    await userEvent.type(
      screen.getByLabelText("Load Node API Base URL"),
      "https://surgepilot.example.test",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save Settings" }),
    );

    await waitFor(() =>
      expect(
        screen.getByText("https://surgepilot.example.test"),
      ).toBeInTheDocument(),
    );
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        requestUrl(input).endsWith("/api/v1/load-nodes/connectivity-summary"),
      ),
    ).toHaveLength(2);
  });
});
