import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "plan@example.com",
    displayName: "Plan User",
    role: "admin",
    status: "active",
  },
  currentWorkspace: {
    id: "01HZW000000000000000000000",
    name: "Default Workspace",
  },
  defaultWorkspace: {
    id: "01HZW000000000000000000000",
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

const scenarioSummary = {
  id: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  name: "Checkout flow",
  description: null,
  tags: ["checkout"],
  scenarioType: "visual",
  stepCount: 1,
  enabledStepCount: 1,
  dependencyFileCount: 0,
  revision: 3,
  createdAt: "2030-06-01T12:00:00.000Z",
  updatedAt: "2030-06-01T12:00:00.000Z",
};

const planDetail = {
  id: "01HZX3Y9M0E9W7Z6M5QK9S8P7P",
  name: "Checkout Load Test",
  description: "Checkout flow baseline",
  tags: ["checkout"],
  envGroupId: "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
  runMode: "sequential",
  resource: {
    mode: "manual",
    poolType: "private",
    selectedNodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
    selectedNodeIds: ["01HZX3Y9M0E9W7Z6M5QK9S8P7N"],
    nodeCount: null,
  },
  scenarioItems: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7I",
      scenarioId: scenarioSummary.id,
      scenarioName: scenarioSummary.name,
      scenarioRevision: 3,
      enabledStepCount: 1,
      updatedAt: "2030-06-01T12:00:00.000Z",
      enabled: true,
      order: 0,
      loadSettings: {
        concurrencyPerNode: 10,
        rampUpSeconds: 60,
        holdForSeconds: 300,
        iterations: null,
        targetRps: null,
        steps: null,
        delaySeconds: 0,
      },
    },
  ],
  slaRules: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
      enabled: true,
      subject: "p95",
      label: null,
      condition: "gt",
      threshold: { value: 500, unit: "ms" },
      timeframeLogic: "for",
      timeframeSeconds: 10,
      action: "continue",
    },
  ],
  runGuard: {
    expectedConcurrencyPerNode: 10,
    softConcurrencyPerNodeLimit: 1000,
    hardConcurrencyPerNodeLimit: 10000,
    requiresHighConcurrencyConfirmation: false,
  },
  runnable: true,
  notRunnableReasons: [],
  revision: 4,
  createdAt: "2030-06-01T12:00:00.000Z",
  updatedAt: "2030-06-01T12:30:00.000Z",
};

const planList = {
  items: [
    {
      id: planDetail.id,
      name: planDetail.name,
      description: planDetail.description,
      tags: planDetail.tags,
      runMode: "sequential",
      envGroup: { id: "01HZX3Y9M0E9W7Z6M5QK9S8P7E", name: "Staging" },
      resource: {
        mode: "manual",
        poolType: "private",
        selectedNodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        selectedNodeIds: ["01HZX3Y9M0E9W7Z6M5QK9S8P7N"],
        nodeCount: null,
        selectedNodeName: "load-01",
        selectedNodeStatus: "idle",
      },
      scenarioItemCount: 1,
      enabledScenarioItemCount: 1,
      slaRuleCount: 1,
      expectedConcurrencyPerNode: 10,
      requiresHighConcurrencyConfirmation: false,
      runnable: true,
      notRunnableReasons: [],
      revision: 4,
      updatedAt: "2030-06-01T12:30:00.000Z",
      updatedBy: { id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A", displayName: "Plan User" },
    },
  ],
  page: 1,
  pageSize: 20,
  total: 1,
};

const envList = {
  items: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
      name: "Staging",
      description: null,
      variableCount: 1,
      createdAt: "2030-06-01T12:00:00.000Z",
      updatedAt: "2030-06-01T12:00:00.000Z",
    },
  ],
  page: 1,
  pageSize: 20,
  total: 1,
};

const nodeList = {
  items: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
      scope: "workspace",
      name: "load-01",
      host: "load-01.internal",
      sshPort: 22,
      sshUser: "surgepilot",
      runnerHome: "/opt/surgepilot/runner",
      authType: "password",
      status: "idle",
      maintainer: null,
      remark: null,
      lastStatusReason: null,
      lastCheckedAt: null,
      createdAt: "2030-06-01T12:00:00.000Z",
      updatedAt: "2030-06-01T12:00:00.000Z",
      archivedAt: null,
      credentialConfigured: true,
    },
  ],
  limit: 100,
  offset: 0,
  total: 1,
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
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("P1-04 test plan polish", () => {
  it("shows Clone and Archive actions, clones to the new editor, and renders empty tag state", async () => {
    const clonedPlan = {
      ...planDetail,
      id: "01HZX3Y9M0E9W7Z6M5QPCLONE",
      name: "Copy of Checkout Load Test",
      tags: [],
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/test-plans") && method === "GET") {
        return jsonResponse({
          ...planList,
          items: [{ ...planList.items[0], tags: [] }],
        });
      }
      if (url.includes(`/api/v1/test-plans/${planDetail.id}/clone`)) {
        expect(method).toBe("POST");
        expect(await requestBody(input, init)).toEqual({});
        return jsonResponse(clonedPlan, { status: 201 });
      }
      return jsonResponse({});
    });

    renderAt("/test-plans");

    expect(await screen.findByText("Checkout Load Test")).toBeInTheDocument();
    expect(screen.getByText("No tags")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Clone/ }));

    await waitFor(() =>
      expect(window.location.pathname).toBe(`/test-plans/${clonedPlan.id}`),
    );
  });

  it("uses Archive confirmation copy for Test Plan and does not say permanent delete", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/test-plans")) return jsonResponse(planList);
      return jsonResponse({});
    });

    renderAt("/test-plans");

    expect(await screen.findByText("Checkout Load Test")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Archive/ }));

    expect(
      screen.getByRole("dialog", { name: "Archive Test Plan" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/hidden from active lists/i)).toBeInTheDocument();
    expect(screen.getByText(/historical Run Reports keep/i)).toBeInTheDocument();
    expect(screen.queryByText(/permanent/i)).not.toBeInTheDocument();
  });

  it("renders read-only Test Plan execution preview and stale state for edits", async () => {
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes(`/api/v1/test-plans/${planDetail.id}/execution-preview`)) {
        expect(method).toBe("GET");
        expect(url).toContain("runType=standard");
        return jsonResponse({
          sourceType: "test_plan",
          sourceId: planDetail.id,
          sourceRevision: 4,
          mode: "standard",
          format: "yaml",
          content:
            "execution:\n- scenario: scenario_01\nreporting:\n- module: passfail\n",
          warnings: [
            {
              code: "soft_limit_exceeded",
              message:
                "Saved load settings exceed the configured single-node soft limit.",
              field: "scenarioItems",
              severity: "warning",
            },
          ],
        });
      }
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(planDetail);
      }
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        const body = (await requestBody(input, init)) as Record<string, unknown>;
        return jsonResponse({ ...planDetail, ...body, revision: planDetail.revision + 1 });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout Load Test" }),
    ).toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Preview run type"),
      "standard",
    );
    await userEvent.click(screen.getByRole("button", { name: "Preview YAML" }));

    expect(await screen.findByText(/module: passfail/)).toBeInTheDocument();
    expect(screen.getByText(/single-node soft limit/)).toBeInTheDocument();
    expect(
      screen.queryByText(
        /Apply YAML|Save YAML|Import YAML|Edit generated YAML|Run from preview/i,
      ),
    ).not.toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Preview run type"),
      "debug",
    );
    expect(screen.queryByText(/module: passfail/)).not.toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Preview run type"),
      "standard",
    );
    await userEvent.click(screen.getByRole("button", { name: "Preview YAML" }));
    expect(await screen.findByText(/module: passfail/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Test Plan name"), {
      target: { value: "Dirty" },
    });
    expect(screen.getByText(/Save before previewing/i)).toBeInTheDocument();
    expect(screen.queryByText(/module: passfail/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(screen.queryByText(/module: passfail/)).not.toBeInTheDocument(),
    );
  });

  it("explains that a Load Node is required when preview fails because resources are missing", async () => {
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/test-plans/${planDetail.id}/execution-preview`)) {
        expect(method).toBe("GET");
        return jsonResponse(
          {
            code: "TEST_PLAN_NOT_RUNNABLE",
            message: "Test Plan is missing Load Node resources.",
            requestId: "req",
          },
          { status: 409 },
        );
      }
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse({
          ...planDetail,
          resource: {
            ...planDetail.resource,
            selectedNodeId: null,
            selectedNodeIds: [],
          },
          runnable: false,
          notRunnableReasons: ["load_node_required"],
        });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout Load Test" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Preview requires a Load Node/i),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Preview YAML" }));

    expect(
      await screen.findByText(/Select a Load Node in Resource Configuration/i),
    ).toBeInTheDocument();
  });

  it("exposes Clone and Archive affordances on the Test Plan editor detail", async () => {
    const clonedPlan = {
      ...planDetail,
      id: "01HZX3Y9M0E9W7Z6M5QPCEDT",
      name: "Copy of Checkout Load Test",
      revision: 1,
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}/clone`) &&
        method === "POST"
      ) {
        expect(await requestBody(input, init)).toEqual({});
        return jsonResponse(clonedPlan, { status: 201 });
      }
      if (url.includes(`/api/v1/test-plans/${planDetail.id}/execution-preview`)) {
        return jsonResponse({
          sourceType: "test_plan",
          sourceId: planDetail.id,
          sourceRevision: 4,
          mode: "debug",
          format: "yaml",
          content: "execution: []\n",
          warnings: [],
        });
      }
      if (
        url.endsWith(`/api/v1/test-plans/${clonedPlan.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(clonedPlan);
      }
      if (
        url.endsWith(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(planDetail);
      }
      if (
        url.endsWith(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "DELETE"
      ) {
        return new Response(null, { status: 204 });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout Load Test" }),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Archive Checkout Load Test" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Archive Test Plan" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/hidden from active lists/i)).toBeInTheDocument();
    expect(screen.getByText(/historical Run Reports keep/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("dialog", { name: "Archive Test Plan" }),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Clone Checkout Load Test" }),
    );
    await waitFor(() =>
      expect(window.location.pathname).toBe(`/test-plans/${clonedPlan.id}`),
    );
  });
});
