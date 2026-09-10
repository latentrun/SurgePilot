import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "scenario@example.com",
    displayName: "Scenario User",
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

const scenarioDetail = {
  id: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  name: "Checkout flow",
  description: "Critical checkout APIs",
  tags: ["checkout"],
  scenarioType: "visual",
  baseUrlExpression: "${base_url}",
  defaultSettings: {
    thinkTimeMs: 0,
    timeoutMs: 30000,
    followRedirects: true,
    keepAlive: true,
    storeCache: true,
    storeCookie: true,
    retrieveResources: false,
  },
  dataSources: [],
  steps: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
      enabled: true,
      name: "List users",
      method: "GET",
      path: "/v1/users",
      queryParams: [],
      headers: [],
      body: { type: "none", contentType: null, rawText: null, formFields: [] },
      uploadFiles: [],
      extractors: [],
      assertions: [],
      scripts: [],
      settings: {
        thinkTimeMs: null,
        timeoutMs: null,
        followRedirects: null,
        keepAlive: null,
      },
    },
  ],
  stepCount: 1,
  enabledStepCount: 1,
  dependencyFileCount: 0,
  revision: 3,
  createdAt: "2030-06-01T12:00:00.000Z",
  updatedAt: "2030-06-01T12:30:00.000Z",
};

const scenarioList = {
  items: [
    {
      id: scenarioDetail.id,
      name: scenarioDetail.name,
      description: scenarioDetail.description,
      tags: scenarioDetail.tags,
      scenarioType: "visual",
      stepCount: 1,
      enabledStepCount: 1,
      dependencyFileCount: 0,
      revision: scenarioDetail.revision,
      createdAt: scenarioDetail.createdAt,
      updatedAt: scenarioDetail.updatedAt,
    },
  ],
  page: 1,
  pageSize: 20,
  total: 1,
};

const envListResponse = {
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

const dependencyFileListResponse = {
  items: [],
  page: 1,
  pageSize: 20,
  total: 0,
};

const nodeListResponse = { items: [], limit: 100, offset: 0, total: 0 };

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

describe("P1-04 scenarios polish", () => {
  it("shows Clone and Archive actions, clones to the new designer, and renders empty tag state", async () => {
    const clonedScenario = {
      ...scenarioDetail,
      id: "01HZX3Y9M0E9W7Z6M5QK9S8PCL",
      name: "Copy of Checkout flow",
      revision: 1,
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/scenarios") && method === "GET") {
        return jsonResponse({
          ...scenarioList,
          items: [{ ...scenarioList.items[0], tags: [] }],
        });
      }
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}/clone`)) {
        expect(method).toBe("POST");
        expect(await requestBody(input, init)).toEqual({});
        return jsonResponse(clonedScenario, { status: 201 });
      }
      return jsonResponse({});
    });

    renderAt("/scenarios");

    expect(await screen.findByText("Checkout flow")).toBeInTheDocument();
    expect(screen.getByText("No tags")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Clone/ }));

    await waitFor(() =>
      expect(window.location.pathname).toBe(`/scenarios/${clonedScenario.id}`),
    );
  });

  it("uses Archive confirmation copy for Scenario and does not say permanent delete", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/scenarios")) return jsonResponse(scenarioList);
      return jsonResponse({});
    });

    renderAt("/scenarios");

    expect(await screen.findByText("Checkout flow")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Archive/ }));

    expect(
      screen.getByRole("dialog", { name: "Archive Scenario" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/hidden from active lists/i)).toBeInTheDocument();
    expect(screen.getByText(/historical Run Reports keep/i)).toBeInTheDocument();
    expect(screen.queryByText(/permanent/i)).not.toBeInTheDocument();
  });

  it("hides the generated YAML preview on the Scenario designer", async () => {
    const fetchMock = mockFetch((input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(scenarioDetail);
      }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envListResponse);
      if (url.includes("/api/v1/dependency-files"))
        return jsonResponse(dependencyFileListResponse);
      if (url.includes("/api/v1/load-nodes"))
        return jsonResponse(nodeListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Generated YAML Preview" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Preview YAML" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Apply YAML|Save YAML|Edit generated YAML|Run from preview/i),
    ).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).includes("/execution-preview"),
      ),
    ).toBe(false);
  });

  it("exposes Clone and Archive affordances on the Scenario designer detail", async () => {
    const clonedScenario = {
      ...scenarioDetail,
      id: "01HZX3Y9M0E9W7Z6M5QK9S8PCDT",
      name: "Copy of Checkout flow",
      revision: 1,
    };
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}/clone`) &&
        method === "POST"
      ) {
        expect(await requestBody(input, init)).toEqual({});
        return jsonResponse(clonedScenario, { status: 201 });
      }
      if (
        url.endsWith(`/api/v1/scenarios/${clonedScenario.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(clonedScenario);
      }
      if (
        url.endsWith(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      ) {
        return jsonResponse(scenarioDetail);
      }
      if (
        url.endsWith(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "DELETE"
      ) {
        return new Response(null, { status: 204 });
      }
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      if (url.includes("/api/v1/dependency-files"))
        return jsonResponse(dependencyFileListResponse);
      if (url.includes("/api/v1/load-nodes"))
        return jsonResponse(nodeListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Archive Checkout flow" }),
    );
    expect(
      screen.getByRole("dialog", { name: "Archive Scenario" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/hidden from active lists/i)).toBeInTheDocument();
    expect(screen.getByText(/historical Run Reports keep/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByRole("dialog", { name: "Archive Scenario" }),
    ).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Clone Checkout flow" }),
    );
    await waitFor(() =>
      expect(window.location.pathname).toBe(`/scenarios/${clonedScenario.id}`),
    );
  });
});
