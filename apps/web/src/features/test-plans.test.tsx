import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { focusManager } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import type { TestPlanDetail, TestPlanPatchRequest } from "../app/api-client";
import {
  canRunDraft,
  expectedConcurrency,
  needsEnabledStateMigration,
  newSlaRule,
  toPatchPayload,
  validateTestPlanDraft,
  validateLoadSettings,
} from "./test-plans/model";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "plan@example.com",
    displayName: "Plan User",
    role: "admin",
    status: "active",
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
const alternateScenarioSummary = {
  ...scenarioSummary,
  id: "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
  name: "Search flow",
  revision: 2,
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
  focusManager.setFocused(undefined);
  vi.unstubAllGlobals();
});

describe("P0-06 test plan model", () => {
  it("defaults new SLA rules to whole-test evaluation", () => {
    const rule = newSlaRule();

    expect(rule.timeframeLogic).toBeNull();
    expect(rule.timeframeSeconds).toBeNull();
  });

  it("migrates disabled Scenario items and SLA rules to enabled in the saved payload", () => {
    const disabledDetail = {
      ...planDetail,
      scenarioItems: [
        {
          ...planDetail.scenarioItems[0],
          enabled: false,
          loadSettings: {
            ...planDetail.scenarioItems[0].loadSettings,
            concurrencyPerNode: 7,
          },
        },
      ],
      slaRules: [{ ...planDetail.slaRules[0], enabled: false }],
    } as TestPlanDetail;

    const payload = toPatchPayload(disabledDetail);

    expect(payload.scenarioItems?.[0]?.enabled).toBe(true);
    expect(payload.slaRules?.[0]?.enabled).toBe(true);
    expect(canRunDraft(disabledDetail)).toBe(true);
    expect(expectedConcurrency(disabledDetail)).toBe(7);
    expect(validateLoadSettings(disabledDetail)).toEqual([]);
    expect(validateTestPlanDraft(disabledDetail)).toEqual([]);
    expect(needsEnabledStateMigration(disabledDetail)).toBe(true);
  });

  it("validates response-code SLA patterns before saving", () => {
    const invalidDetail = {
      ...planDetail,
      slaRules: [
        {
          ...planDetail.slaRules[0],
          subject: "rc",
          threshold: { value: 1, unit: "percent" },
        },
      ],
    } as TestPlanDetail;

    expect(validateTestPlanDraft(invalidDetail)).toEqual([
      "SLA Rule 1: use a response code pattern like 500, 4??, or *.",
    ]);
  });
});

describe("P0-06 test plans web flow", () => {
  it("renders navigation, populated list, empty state, and forbids P1 labels", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/test-plans?empty=1"))
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      if (url.includes("/api/v1/test-plans")) return jsonResponse(planList);
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });

    renderAt("/test-plans");

    expect(
      await screen.findByRole("heading", { name: "Test Plans" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /test plans/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(await screen.findByText("Checkout Load Test")).toBeInTheDocument();
    expect(
      screen.queryByText(
        /Schedule Run|Bulk Apply/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("shows Updated before Actions without Env or Node columns", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/test-plans")) return jsonResponse(planList);
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });

    renderAt("/test-plans");

    await screen.findByText("Checkout Load Test");
    const updatedHeader = screen.getByText("Updated");
    const actionsHeader = screen.getByText("Actions");
    const headerGrid = updatedHeader.parentElement;
    const listGrid = headerGrid?.parentElement;
    const formattedUpdatedAt = new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(planList.items[0].updatedAt));

    expect(screen.queryByText("Env")).not.toBeInTheDocument();
    expect(screen.queryByText("Node")).not.toBeInTheDocument();
    expect(screen.queryByText("Staging")).not.toBeInTheDocument();
    expect(screen.queryByText("load-01")).not.toBeInTheDocument();
    expect(screen.getByText(formattedUpdatedAt)).toBeInTheDocument();
    expect(
      Array.from(headerGrid?.children ?? []).map((cell) => cell.textContent),
    ).toEqual(["Name", "Mode", "Scenarios", "Concurrency", "Updated", "Actions"]);
    expect(updatedHeader.nextElementSibling).toBe(actionsHeader);
    expect(listGrid).toHaveAttribute("data-testid", "test-plan-list-grid");
    expect(listGrid).toHaveClass("overflow-x-auto");
    expect(headerGrid).toHaveClass("min-w-[900px]");
  });

  it("stacks Run Mode below Env Group in Global Context", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/test-plans/${planDetail.id}`))
        return jsonResponse(planDetail);
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    const envGroupSelect = await screen.findByLabelText("Env Group");
    const runModeSelect = screen.getByLabelText("Run Mode");
    const contextGrid = envGroupSelect.closest("div");

    expect(contextGrid).toBe(runModeSelect.closest("div"));
    expect(contextGrid).toHaveClass("grid");
    expect(contextGrid?.className).not.toMatch(/grid-cols-2/);
    expect(
      envGroupSelect.compareDocumentPosition(runModeSelect) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("creates a Test Plan and navigates to the editor", async () => {
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes("/api/v1/test-plans") && method === "GET")
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      if (url.endsWith("/api/v1/test-plans") && method === "POST") {
        const body = await requestBody(input, init);
        expect(body.name).toBe("Checkout Load Test");
        return jsonResponse(planDetail, { status: 201 });
      }
      return jsonResponse({});
    });

    renderAt("/test-plans");
    await screen.findByText("No test plans yet");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Create Test Plan" })[0],
    );
    await userEvent.type(
      screen.getByLabelText("Test Plan name"),
      "Checkout Load Test",
    );
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(window.location.pathname).toBe(`/test-plans/${planDetail.id}`),
    );
  });

  it("renames a Test Plan from the header and saves the existing revision", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(planDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        patchBody = await requestBody(input, init);
        return jsonResponse({
          ...planDetail,
          ...patchBody,
          revision: 5,
        });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
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
      screen.getByRole("button", { name: "Rename Test Plan" }),
    );
    const nameInput = screen.getByRole("textbox", {
      name: "Test Plan title",
    });
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Checkout Baseline");

    expect(
      screen.getByText("Revision 4 · Unsaved changes"),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    expect(patchBody).toMatchObject({
      name: "Checkout Baseline",
      expectedRevision: 4,
    });
  });

  it("saves dirty editor changes before Run Now and sends standard test_plan run", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(planDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        const body = await requestBody(input, init);
        expect(body.expectedRevision).toBe(4);
        return jsonResponse({
          ...planDetail,
          name: "Checkout Baseline",
          revision: 5,
        });
      }
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        const body = await requestBody(input, init);
        expect(body.runType).toBe("standard");
        expect(body.sourceType).toBe("test_plan");
        expect(body.expectedSourceRevision).toBe(5);
        expect(body.resourceRequest).toEqual({
          mode: "manual",
          selectedNodeIds: ["01HZX3Y9M0E9W7Z6M5QK9S8P7N"],
          concurrencyPerNode: 10,
        });
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "standard",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "valid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    fireEvent.change(screen.getByLabelText("Test Plan name"), {
      target: { value: "Checkout Baseline" },
    });
    await userEvent.click(
      screen.getAllByRole("button", { name: "Save and Run Now" })[0],
    );

    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R"),
    );
    expect(fetchMock).toHaveBeenCalled();
  });

  it("disables non-idle manual node options and does not submit them", async () => {
    const busyNodeId = "01HZX3Y9M0E9W7Z6M5QK9S8P7M";
    const mixedNodeList = {
      ...nodeList,
      items: [
        ...nodeList.items,
        {
          ...nodeList.items[0],
          id: busyNodeId,
          name: "load-02",
          host: "load-02.internal",
          status: "busy",
        },
      ],
      total: 2,
    };
    let runBody: unknown = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(planDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        const body = await requestBody(input, init);
        expect(body.resource.selectedNodeIds).toEqual([
          planDetail.resource.selectedNodeId,
        ]);
        return jsonResponse({
          ...planDetail,
          resource: {
            ...planDetail.resource,
            selectedNodeIds: [planDetail.resource.selectedNodeId],
          },
          revision: 5,
        });
      }
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        runBody = await requestBody(input, init);
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "standard",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "valid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(mixedNodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    await userEvent.click(screen.getByRole("button", { name: /select nodes/i }));
    const dialog = await screen.findByRole("dialog", { name: "Select Load Nodes" });
    expect(
      within(dialog).getByRole("checkbox", { name: /load-01\.internal · idle/i }),
    ).toBeChecked();
    expect(
      within(dialog).queryByRole("checkbox", { name: /load-02\.internal/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("1 node selected")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    await userEvent.click(screen.getAllByRole("button", { name: /run now/i })[0]);

    await waitFor(() =>
      expect(runBody).toMatchObject({
        resourceRequest: {
          mode: "manual",
          selectedNodeIds: [planDetail.resource.selectedNodeId],
          concurrencyPerNode: 10,
        },
      }),
    );
  });

  it("filters manual node picker by selected pool type", async () => {
    const publicNodeId = "01HZX3Y9M0E9W7Z6M5QK9S8P7Q";
    const mixedNodeList = {
      ...nodeList,
      items: [
        ...nodeList.items,
        {
          ...nodeList.items[0],
          id: publicNodeId,
          scope: "public",
          name: "public-01",
          host: "public-01.internal",
          status: "idle",
        },
      ],
      total: 2,
    };
    let savedBody: TestPlanPatchRequest | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(planDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        savedBody = (await requestBody(input, init)) as TestPlanPatchRequest;
        return jsonResponse({ ...planDetail, ...savedBody, revision: 5 });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(mixedNodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    await userEvent.selectOptions(screen.getByLabelText("Pool Type"), "public");
    await userEvent.click(screen.getByRole("button", { name: /select nodes/i }));
    const dialog = await screen.findByRole("dialog", { name: "Select Load Nodes" });

    expect(
      within(dialog).queryByRole("checkbox", { name: /load-01\.internal/i }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      within(dialog).getByRole("checkbox", { name: /public-01\.internal · idle/i }),
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    expect(screen.getByText("1 node selected")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(savedBody?.resource).toMatchObject({
        poolType: "public",
        selectedNodeIds: [publicNodeId],
      }),
    );
  });

  it("sends auto node count only for Standard Run resource requests", async () => {
    const autoPlan = {
      ...planDetail,
      resource: {
        mode: "auto",
        poolType: "private",
        selectedNodeId: null,
        selectedNodeIds: [],
        nodeCount: 2,
      },
    } as TestPlanDetail;
    let runBody: unknown = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(autoPlan);
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        runBody = await requestBody(input, init);
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "standard",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            validity: "valid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    expect(screen.getByLabelText("Node Count")).toHaveValue(2);
    await userEvent.click(screen.getAllByRole("button", { name: "Run Now" })[0]);

    await waitFor(() =>
      expect(runBody).toMatchObject({
        resourceRequest: {
          mode: "auto",
          nodeCount: 2,
          concurrencyPerNode: 10,
        },
      }),
    );
    expect(
      (runBody as { resourceRequest: { selectedNodeIds?: string[] } })
        .resourceRequest.selectedNodeIds,
    ).toBeUndefined();
  });

  it("migrates disabled Scenario items and SLA rules before Run Now", async () => {
    const legacyDetail = {
      ...planDetail,
      scenarioItems: [{ ...planDetail.scenarioItems[0], enabled: false }],
      slaRules: [{ ...planDetail.slaRules[0], enabled: false }],
    };
    let patchedBody: TestPlanPatchRequest | null = null;
    let runBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(legacyDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        patchedBody = await requestBody(input, init);
        return jsonResponse({
          ...planDetail,
          scenarioItems: [{ ...planDetail.scenarioItems[0], enabled: true }],
          slaRules: [{ ...planDetail.slaRules[0], enabled: true }],
          revision: 5,
        });
      }
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        runBody = await requestBody(input, init);
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "standard",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "valid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    expect(
      screen.getAllByRole("button", { name: "Save and Run Now" })[0],
    ).not.toBeDisabled();
    await userEvent.click(
      screen.getAllByRole("button", { name: "Save and Run Now" })[0],
    );

    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R"),
    );
    expect(patchedBody).not.toBeNull();
    expect(runBody).not.toBeNull();
    const body = patchedBody as unknown as TestPlanPatchRequest;
    const createRunBody = runBody as unknown as {
      expectedSourceRevision?: number;
    };
    expect(body.scenarioItems?.[0]?.enabled).toBe(true);
    expect(body.slaRules?.[0]?.enabled).toBe(true);
    expect(createRunBody.expectedSourceRevision).toBe(5);
  });

  it("shows the load error instead of an endless loading fallback", async () => {
    mockFetch((input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(
          {
            code: "RESOURCE_NOT_FOUND",
            message: "Resource was not found.",
            requestId: "req",
          },
          { status: 404 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(
      await screen.findByText("Unable to load Test Plan."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Loading Test Plan…")).not.toBeInTheDocument();
  });

  it("keeps dirty editor changes when a background refetch returns saved data", async () => {
    let detailGets = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      ) {
        detailGets += 1;
        return jsonResponse(
          detailGets === 1
            ? planDetail
            : { ...planDetail, name: "Server Copy" },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    fireEvent.change(screen.getByLabelText("Test Plan name"), {
      target: { value: "Local Draft" },
    });

    focusManager.setFocused(false);
    focusManager.setFocused(true);

    await waitFor(() => expect(detailGets).toBeGreaterThan(1));
    expect(screen.getByDisplayValue("Local Draft")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Server Copy")).not.toBeInTheDocument();
  });

  it("enables Save and Run Now for a dirty draft after required run fields are selected", async () => {
    const blankDetail = {
      ...planDetail,
      envGroupId: null,
      resource: { poolType: null, selectedNodeId: null },
      scenarioItems: [],
      slaRules: [],
      runGuard: {
        expectedConcurrencyPerNode: 0,
        softConcurrencyPerNodeLimit: 1000,
        hardConcurrencyPerNodeLimit: 10000,
        requiresHighConcurrencyConfirmation: false,
      },
      runnable: false,
      notRunnableReasons: ["no_enabled_scenarios", "load_node_required"],
      revision: 1,
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(blankDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        const body = await requestBody(input, init);
        expect(body.resource).toEqual({
          mode: "manual",
          poolType: "private",
          selectedNodeId: planDetail.resource.selectedNodeId,
          selectedNodeIds: [planDetail.resource.selectedNodeId],
          nodeCount: null,
        });
        expect(body.scenarioItems).toHaveLength(1);
        return jsonResponse({
          ...planDetail,
          revision: 2,
          resource: {
            mode: "manual",
            poolType: "private",
            selectedNodeId: planDetail.resource.selectedNodeId,
            selectedNodeIds: [planDetail.resource.selectedNodeId],
            nodeCount: null,
          },
          scenarioItems: [
            {
              ...planDetail.scenarioItems[0],
              scenarioId: scenarioSummary.id,
              scenarioName: scenarioSummary.name,
            },
          ],
          runnable: true,
          notRunnableReasons: [],
        });
      }
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        const body = await requestBody(input, init);
        expect(body.runType).toBe("standard");
        expect(body.expectedSourceRevision).toBe(2);
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "standard",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "valid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    await userEvent.selectOptions(
      screen.getByLabelText("Pool Type"),
      "private",
    );
    await userEvent.click(screen.getByRole("button", { name: /select nodes/i }));
    const selectedNodeDialog = await screen.findByRole("dialog", {
      name: "Select Load Nodes",
    });
    await userEvent.click(
      within(selectedNodeDialog).getByRole("checkbox", {
        name: /load-01\.internal · idle/i,
      }),
    );
    await userEvent.click(
      within(selectedNodeDialog).getByRole("button", { name: "Done" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Add Scenario" }));

    const runButtons = screen.getAllByRole("button", {
      name: "Save and Run Now",
    });
    expect(runButtons[0]).not.toBeDisabled();
    await userEvent.click(runButtons[0]);

    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R"),
    );
  });

  it("keeps Debug enabled when only Standard Run hard-limit guard blocks the saved plan", async () => {
    const hardLimitDetail = {
      ...planDetail,
      runMode: "parallel",
      runGuard: {
        expectedConcurrencyPerNode: 12000,
        softConcurrencyPerNodeLimit: 1000,
        hardConcurrencyPerNodeLimit: 10000,
        requiresHighConcurrencyConfirmation: true,
      },
      runnable: false,
      notRunnableReasons: ["single_node_concurrency_hard_limit"],
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(hardLimitDetail);
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        const body = await requestBody(input, init);
        expect(body.runType).toBe("debug");
        expect(body.sourceType).toBe("test_plan");
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P8R",
            state: "initializing",
            runType: "debug",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "invalid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    expect(
      screen.getAllByRole("button", { name: "Run Now" })[0],
    ).toBeDisabled();
    const debugButtons = screen.getAllByRole("button", { name: "Debug" });
    expect(debugButtons[0]).not.toBeDisabled();
    await userEvent.click(debugButtons[0]);

    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P8R"),
    );
  });

  it("keeps Debug enabled when only Standard Run SLA-count guard blocks the saved plan", async () => {
    const tooManySlaRulesDetail = {
      ...planDetail,
      runnable: false,
      notRunnableReasons: ["too_many_sla_rules"],
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(tooManySlaRulesDetail);
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        const body = await requestBody(input, init);
        expect(body.runType).toBe("debug");
        expect(body.sourceType).toBe("test_plan");
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P9R",
            state: "initializing",
            runType: "debug",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "invalid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    expect(
      screen.getAllByRole("button", { name: "Run Now" })[0],
    ).toBeDisabled();
    const debugButtons = screen.getAllByRole("button", { name: "Debug" });
    expect(debugButtons[0]).not.toBeDisabled();
    await userEvent.click(debugButtons[0]);

    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P9R"),
    );
  });

  it("does not start a Standard Run when saving a dirty draft returns a not-runnable plan", async () => {
    const blankDetail = {
      ...planDetail,
      envGroupId: null,
      resource: { poolType: null, selectedNodeId: null },
      scenarioItems: [],
      slaRules: [],
      runGuard: {
        expectedConcurrencyPerNode: 0,
        softConcurrencyPerNodeLimit: 1000,
        hardConcurrencyPerNodeLimit: 10000,
        requiresHighConcurrencyConfirmation: false,
      },
      runnable: false,
      notRunnableReasons: ["no_enabled_scenarios", "load_node_required"],
      revision: 1,
    };
    const savedNotRunnable = {
      ...planDetail,
      revision: 2,
      resource: {
        poolType: "private",
        selectedNodeId: planDetail.resource.selectedNodeId,
      },
      scenarioItems: [
        {
          ...planDetail.scenarioItems[0],
          scenarioId: scenarioSummary.id,
          scenarioName: scenarioSummary.name,
        },
      ],
      runGuard: {
        expectedConcurrencyPerNode: 12000,
        softConcurrencyPerNodeLimit: 1000,
        hardConcurrencyPerNodeLimit: 10000,
        requiresHighConcurrencyConfirmation: true,
      },
      runnable: false,
      notRunnableReasons: ["single_node_concurrency_hard_limit"],
    };
    let runCreateCount = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(blankDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      )
        return jsonResponse(savedNotRunnable);
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        runCreateCount += 1;
        return jsonResponse(
          { id: "01HZX3Y9M0E9W7Z6M5QK9S8P9R" },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    await userEvent.selectOptions(
      screen.getByLabelText("Pool Type"),
      "private",
    );
    await userEvent.click(screen.getByRole("button", { name: /select nodes/i }));
    const nodeDialog = await screen.findByRole("dialog", {
      name: "Select Load Nodes",
    });
    await userEvent.click(
      within(nodeDialog).getByRole("checkbox", {
        name: /load-01\.internal · idle/i,
      }),
    );
    await userEvent.click(
      within(nodeDialog).getByRole("button", { name: "Done" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Add Scenario" }));
    await userEvent.click(
      screen.getAllByRole("button", { name: "Save and Run Now" })[0],
    );

    await screen.findByText(
      "Complete the required sections before starting a Run.",
    );
    expect(runCreateCount).toBe(0);
    expect(window.location.pathname).toBe(`/test-plans/${planDetail.id}`);
  });

  it("shows high-concurrency confirmation and retries only after confirmation", async () => {
    let attempts = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse({
          ...planDetail,
          runGuard: {
            ...planDetail.runGuard,
            expectedConcurrencyPerNode: 1200,
            softConcurrencyPerNodeLimit: 1000,
            requiresHighConcurrencyConfirmation: true,
          },
        });
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        attempts += 1;
        const body = await requestBody(input, init);
        if (!body.confirmHighConcurrency) {
          return jsonResponse(
            {
              code: "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED",
              message:
                "Expected single-node concurrency exceeds the configured soft limit.",
              details: [
                {
                  field: "scenarioItems",
                  code: "single_node_concurrency_soft_limit",
                  message: "Confirm high concurrency.",
                  meta: { expectedConcurrencyPerNode: 1200, softLimit: 1000 },
                },
              ],
              requestId: "req",
            },
            { status: 409 },
          );
        }
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "standard",
            sourceType: "test_plan",
            sourceId: planDetail.id,
            selectedNodeId: planDetail.resource.selectedNodeId,
            validity: "valid",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Run Now" })[0],
    );
    expect(
      await screen.findByRole("dialog", { name: "Confirm high concurrency" }),
    ).toBeInTheDocument();
    expect(attempts).toBe(1);
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm and run" }),
    );
    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R"),
    );
    expect(attempts).toBe(2);
  });

  it("adds a Scenario row first and saves the Scenario selected inside that row", async () => {
    let patchedBody: TestPlanPatchRequest | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse({ ...planDetail, scenarioItems: [] });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        patchedBody = await requestBody(input, init);
        return jsonResponse({
          ...planDetail,
          scenarioItems: [
            {
              ...planDetail.scenarioItems[0],
              scenarioId: alternateScenarioSummary.id,
              scenarioName: alternateScenarioSummary.name,
              scenarioRevision: alternateScenarioSummary.revision,
            },
          ],
          revision: 5,
        });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary, alternateScenarioSummary],
          page: 1,
          pageSize: 100,
          total: 2,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    expect(
      screen.queryByLabelText("Scenario selector"),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add Scenario" }));
    const rowScenarioSelect = screen.getByRole("combobox", {
      name: "Scenario name",
    });
    expect(rowScenarioSelect).toHaveValue(scenarioSummary.id);
    await userEvent.selectOptions(
      rowScenarioSelect,
      alternateScenarioSummary.id,
    );
    await userEvent.click(screen.getAllByRole("button", { name: "Save" })[0]);

    await screen.findByText("Revision 5 · Saved");
    expect(patchedBody).not.toBeNull();
    const body = patchedBody as unknown as TestPlanPatchRequest;
    expect(body.scenarioItems).toHaveLength(1);
    expect(body.scenarioItems?.[0]?.scenarioId).toBe(
      alternateScenarioSummary.id,
    );
  });

  it("matches SLA threshold defaults and units to the selected metric", async () => {
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(planDetail);
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    expect(screen.getByText(/rules define failure conditions for Standard Runs/i)).toBeInTheDocument();
    expect(
      screen.getByText(/fail > 1%, avg_rt > 1000ms, and p95 > 2000ms/i),
    ).toBeInTheDocument();

    const metricSelect = screen.getByRole("combobox", { name: "SLA metric" });
    await userEvent.selectOptions(metricSelect, "fail");

    expect(screen.getByLabelText("Fail when")).toHaveValue("gt");
    expect(screen.getByLabelText("SLA threshold")).toHaveValue(1);
    const failUnitSelect = screen.getByRole("combobox", { name: "SLA unit" });
    expect(failUnitSelect).toHaveValue("percent");
    expect(
      within(failUnitSelect).queryByRole("option", { name: "ms" }),
    ).not.toBeInTheDocument();
    expect(
      within(failUnitSelect).getByRole("option", { name: "percent" }),
    ).toBeInTheDocument();

    await userEvent.selectOptions(metricSelect, "succ");
    expect(screen.getByLabelText("Fail when")).toHaveValue("lt");
    expect(screen.getByLabelText("SLA threshold")).toHaveValue(99);

    await userEvent.selectOptions(metricSelect, "bytes");
    const bytesUnitSelect = screen.getByRole("combobox", { name: "SLA unit" });
    expect(screen.getByLabelText("Fail when")).toHaveValue("gt");
    expect(screen.getByLabelText("SLA threshold")).toHaveValue(1);
    expect(bytesUnitSelect).toHaveValue("mb");
    expect(
      within(bytesUnitSelect).queryByRole("option", { name: "percent" }),
    ).not.toBeInTheDocument();
    expect(
      within(bytesUnitSelect).getByRole("option", { name: "MB" }),
    ).toBeInTheDocument();
  });

  it("defaults blank response-code SLA patterns to wildcard", async () => {
    let patchedBody: TestPlanPatchRequest | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(planDetail);
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        patchedBody = await requestBody(input, init);
        return jsonResponse({
          ...planDetail,
          slaRules: [
            {
              ...planDetail.slaRules[0],
              enabled: true,
              subject: "rc*",
              threshold: { value: 500, unit: "percent" },
            },
          ],
          revision: 5,
        });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "SLA metric" }),
      "rc",
    );
    await userEvent.clear(screen.getByLabelText("Response code pattern"));
    await userEvent.click(screen.getAllByRole("button", { name: "Save" })[0]);

    await screen.findByText("Revision 5 · Saved");
    expect(patchedBody).not.toBeNull();
    const body = patchedBody as unknown as TestPlanPatchRequest;
    expect(body.slaRules?.[0]?.subject).toBe("rc*");
  });

  it("uses enabled-state migration and guided SLA metric inputs in the editor", async () => {
    let patchedBody: TestPlanPatchRequest | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse({
          ...planDetail,
          scenarioItems: [{ ...planDetail.scenarioItems[0], enabled: false }],
          slaRules: [{ ...planDetail.slaRules[0], enabled: false }],
        });
      }
      if (
        url.includes(`/api/v1/test-plans/${planDetail.id}`) &&
        method === "PATCH"
      ) {
        patchedBody = await requestBody(input, init);
        return jsonResponse({
          ...planDetail,
          scenarioItems: [{ ...planDetail.scenarioItems[0], enabled: true }],
          slaRules: [
            {
              ...planDetail.slaRules[0],
              enabled: true,
              subject: "rc4??",
              threshold: { value: 500, unit: "percent" },
            },
          ],
          revision: 5,
        });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");

    expect(
      screen.queryByRole("checkbox", { name: "Checkout flow" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "Enabled" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Actions" }),
    ).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Save" })).toHaveLength(1);

    const metricSelect = screen.getByRole("combobox", { name: "SLA metric" });
    expect(
      within(metricSelect).getByRole("option", { name: "P95 response time" }),
    ).toBeInTheDocument();
    expect(
      within(metricSelect).getByRole("option", { name: "Response code rate" }),
    ).toBeInTheDocument();

    await userEvent.selectOptions(metricSelect, "rc");
    fireEvent.change(screen.getByLabelText("Response code pattern"), {
      target: { value: "4??" },
    });
    await userEvent.selectOptions(screen.getByLabelText("SLA unit"), "percent");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Revision 5 · Saved");
    expect(patchedBody).not.toBeNull();
    const body = patchedBody as unknown as TestPlanPatchRequest;
    expect(body.scenarioItems).toHaveLength(1);
    expect(body.scenarioItems?.[0]?.enabled).toBe(true);
    expect(body.slaRules).toHaveLength(1);
    expect(body.slaRules?.[0]?.enabled).toBe(true);
    expect(body.slaRules?.[0]?.subject).toBe("rc4??");
    expect(body.slaRules?.[0]?.threshold?.unit).toBe("percent");
  });

  it("deletes with confirmation and blocks unsaved navigation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/test-plans/${planDetail.id}`))
        return jsonResponse(planDetail);
      if (url.includes("/api/v1/test-plans")) return jsonResponse(planList);
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);
    await screen.findByDisplayValue("Checkout Load Test");
    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Changed" },
    });
    await userEvent.click(screen.getByRole("link", { name: "← Test Plans" }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(window.location.pathname).toBe(`/test-plans/${planDetail.id}`);
  });
});

describe("P1-04 test plan polish", () => {
  it("shows Clone and Archive actions, clones to the new editor, and renders empty tag state", async () => {
    const clonedPlan = { ...planDetail, id: "01HZX3Y9M0E9W7Z6M5QPCLONE", name: "Copy of Checkout Load Test", tags: [] };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf")) return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes("/api/v1/test-plans") && method === "GET") {
        return jsonResponse({
          ...planList,
          items: [{ ...planList.items[0], tags: [] }],
        });
      }
      if (url.endsWith(`/api/v1/test-plans/${planDetail.id}/clone`)) {
        const body = await requestBody(input, init);
        expect(body).toEqual({});
        return jsonResponse(clonedPlan, { status: 201 });
      }
      return jsonResponse({});
    });

    renderAt("/test-plans");

    expect(await screen.findByText("Checkout Load Test")).toBeInTheDocument();
    expect(screen.getByText("No tags")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clone" }));

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
    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(screen.getByRole("dialog", { name: "Archive Test Plan" })).toBeInTheDocument();
    expect(screen.getByText(/hidden from active lists/i)).toBeInTheDocument();
    expect(screen.getByText(/historical Run Reports keep/i)).toBeInTheDocument();
    expect(screen.queryByText(/permanent/i)).not.toBeInTheDocument();
  });

  it("renders read-only Test Plan execution preview and stale state for edits", async () => {
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf")) return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes(`/api/v1/test-plans/${planDetail.id}/execution-preview`)) {
        expect(method).toBe("GET");
        expect(url).toContain("runType=standard");
        return jsonResponse({
          sourceType: "test_plan",
          sourceId: planDetail.id,
          sourceRevision: 4,
          mode: "standard",
          format: "yaml",
          content: "execution:\n- scenario: scenario_01\nreporting:\n- module: passfail\n",
          warnings: [
            {
              code: "soft_limit_exceeded",
              message: "Saved load settings exceed the configured single-node soft limit.",
              field: "scenarioItems",
              severity: "warning",
            },
          ],
        });
      }
      if (url.includes(`/api/v1/test-plans/${planDetail.id}`) && method === "GET") return jsonResponse(planDetail);
      if (url.includes(`/api/v1/test-plans/${planDetail.id}`) && method === "PATCH") {
        const body = (await requestBody(input, init)) as TestPlanPatchRequest;
        return jsonResponse({ ...planDetail, ...body, revision: planDetail.revision + 1 });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios")) return jsonResponse({ items: [scenarioSummary, alternateScenarioSummary], page: 1, pageSize: 20, total: 2 });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(await screen.findByRole("heading", { name: "Checkout Load Test" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Preview run type"), "standard");
    await userEvent.click(screen.getByRole("button", { name: "Preview YAML" }));
    expect(await screen.findByText(/module: passfail/)).toBeInTheDocument();
    expect(screen.getByText(/single-node soft limit/)).toBeInTheDocument();
    expect(screen.queryByText(/Apply YAML|Save YAML|Import YAML|Edit generated YAML|Run from preview/i)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Preview run type"), "debug");
    expect(screen.queryByText(/module: passfail/)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Preview run type"), "standard");
    await userEvent.click(screen.getByRole("button", { name: "Preview YAML" }));
    expect(await screen.findByText(/module: passfail/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Test Plan name"), { target: { value: "Dirty" } });
    expect(screen.getByText(/Save before previewing/i)).toBeInTheDocument();
    expect(screen.queryByText(/module: passfail/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.queryByText(/module: passfail/)).not.toBeInTheDocument());
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
      if (url.includes(`/api/v1/test-plans/${planDetail.id}`) && method === "GET") {
        return jsonResponse({
          ...planDetail,
          resource: { poolType: null, selectedNodeId: null },
          runnable: false,
          notRunnableReasons: ["load_node_required"],
        });
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({ items: [scenarioSummary], page: 1, pageSize: 20, total: 1 });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(await screen.findByRole("heading", { name: "Checkout Load Test" })).toBeInTheDocument();
    expect(
      screen.getByText(/Preview requires a Load Node/i),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Preview YAML" }));

    expect(
      await screen.findByText(/Select a Load Node in Resource Configuration/i),
    ).toBeInTheDocument();
  });

  it("places the generated YAML preview after editable Test Plan sections", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes(`/api/v1/test-plans/${planDetail.id}`))
        return jsonResponse(planDetail);
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envList);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioSummary, alternateScenarioSummary],
          page: 1,
          pageSize: 20,
          total: 2,
        });
      if (url.includes("/api/v1/load-nodes")) return jsonResponse(nodeList);
      return jsonResponse({});
    });

    renderAt(`/test-plans/${planDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout Load Test" }),
    ).toBeInTheDocument();
    const headingTexts = screen
      .getAllByRole("heading")
      .map((heading) => heading.textContent);

    expect(headingTexts.indexOf("Generated YAML Preview")).toBeGreaterThan(
      headingTexts.indexOf("SLA Rules"),
    );
  });
});
