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

describe("P1-05 cURL import", () => {
  it("previews a cURL import and appends the imported Step without auto-saving", async () => {
    let patchBody: Record<string, unknown> | null = null;
    let parseCalls = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.endsWith("/api/v1/scenarios/curl-import/parse")) {
        parseCalls += 1;
        const body = await requestBody(input, init);
        expect(body.rawCurl).toContain("curl");
        return jsonResponse({
          step: {
            enabled: true,
            name: "POST /v1/orders",
            method: "POST",
            path: "/v1/orders",
            queryParams: [{ name: "region", value: "sg", enabled: true }],
            headers: [
              { name: "Authorization", value: "Bearer token", enabled: true },
            ],
            body: {
              type: "raw",
              contentType: "application/json",
              rawText: '{"sku":"A1"}',
              formFields: [],
            },
            settings: {
              timeoutMs: 2500,
              followRedirects: true,
              keepAlive: null,
              thinkTimeMs: null,
            },
          },
          baseUrlSuggestion: "https://api.example.test",
          warnings: [
            {
              code: "SENSITIVE_HEADER_PRESENT",
              message:
                "A sensitive header may be saved into the Scenario if you confirm and save.",
              field: "headers[0].name",
            },
          ],
          unsupportedOptions: [
            {
              option: "--compressed",
              reasonCode: "unsupported_option",
              message: "This cURL option was not imported.",
            },
          ],
        });
      }
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "PATCH"
      ) {
        patchBody = await requestBody(input, init);
        return jsonResponse({ ...scenarioDetail, ...patchBody, revision: 4 });
      }
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      if (url.includes("/api/v1/dependency-files"))
        return jsonResponse(dependencyFileListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Import cURL" }));
    await userEvent.type(
      await screen.findByLabelText("cURL command"),
      "curl -H 'Authorization: Bearer token' https://api.example.test/v1/orders?region=sg",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Preview import" }),
    );

    expect(await screen.findByText("POST /v1/orders")).toBeInTheDocument();
    expect(screen.getByText("region=sg")).toBeInTheDocument();
    expect(screen.getByText("Authorization")).toBeInTheDocument();
    expect(
      screen.getByText("Sensitive information warning"),
    ).toBeInTheDocument();
    expect(screen.getByText("--compressed")).toBeInTheDocument();
    expect(screen.getByText("Saved", { exact: true })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Import Step" }));
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(parseCalls).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as {
      steps: Array<Record<string, unknown>>;
      baseUrlExpression: string;
    };
    expect(body.steps).toHaveLength(2);
    expect(body.steps[1]).toMatchObject({
      name: "POST /v1/orders",
      method: "POST",
      path: "/v1/orders",
      queryParams: [{ name: "region", value: "sg", enabled: true }],
      headers: [
        { name: "Authorization", value: "Bearer token", enabled: true },
      ],
      body: {
        type: "raw",
        contentType: "application/json",
        rawText: '{"sku":"A1"}',
      },
      settings: { timeoutMs: 2500, followRedirects: true },
    });
    expect(body.steps[1].id).not.toBe(scenarioDetail.steps[0].id);
    expect(body.baseUrlExpression).toBe("${base_url}");
  });

  it("replaces the selected Step and applies the base URL only after explicit confirmation", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.endsWith("/api/v1/scenarios/curl-import/parse"))
        return jsonResponse({
          step: {
            enabled: true,
            name: "GET /v1/replaced",
            method: "GET",
            path: "/v1/replaced",
            queryParams: [],
            headers: [],
            body: {
              type: "none",
              contentType: null,
              rawText: null,
              formFields: [],
            },
            settings: {
              timeoutMs: null,
              followRedirects: null,
              keepAlive: null,
              thinkTimeMs: null,
            },
          },
          baseUrlSuggestion: "https://replace.example.test",
          warnings: [],
          unsupportedOptions: [],
        });
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "PATCH"
      ) {
        patchBody = await requestBody(input, init);
        return jsonResponse({ ...scenarioDetail, ...patchBody, revision: 4 });
      }
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      if (url.includes("/api/v1/dependency-files"))
        return jsonResponse(dependencyFileListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Import cURL" }));
    await userEvent.type(
      await screen.findByLabelText("cURL command"),
      "curl https://replace.example.test/v1/replaced",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Preview import" }),
    );
    await screen.findByText("GET /v1/replaced");
    await userEvent.click(screen.getByLabelText("Replace selected Step"));
    await userEvent.click(screen.getByLabelText("Apply to Global Config"));
    await userEvent.click(screen.getByRole("button", { name: "Import Step" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as {
      steps: Array<Record<string, unknown>>;
      baseUrlExpression: string;
    };
    expect(body.baseUrlExpression).toBe("https://replace.example.test");
    expect(body.steps).toHaveLength(1);
    expect(body.steps[0]).toMatchObject({
      id: scenarioDetail.steps[0].id,
      name: "GET /v1/replaced",
      method: "GET",
      path: "/v1/replaced",
    });
    expect((body.steps[0].assertions as Array<unknown>).length).toBeGreaterThan(0);
  });

  it("previews and inserts OpenAPI drafts locally without saving or exposing Catalog actions", async () => {
    const specId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";
    let draftCalls = 0;
    let patchCalls = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf")) return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/specs/`) && url.endsWith("/operations")) {
        return jsonResponse({
          spec: { id: specId, name: "Orders API", filename: "orders.json", sourceFormat: "openapi_json", documentTitle: "Orders API", documentVersion: "1.0.0", status: "available", updatedAt: "2030-06-01T12:00:00Z" },
          items: [{ ref: { method: "POST", path: "/orders", operationId: "createOrder" }, method: "POST", path: "/orders", operationId: "createOrder", summary: "Create order", tags: [], displayName: "Create order", hasRequestBody: true, supportedForGeneration: true, warningCodes: [] }],
          warnings: [],
        });
      }
      if (url.endsWith(`/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/specs`)) {
        return jsonResponse({ items: [{ id: specId, name: "Orders API", filename: "orders.json", sourceFormat: "openapi_json", documentTitle: "Orders API", documentVersion: "1.0.0", status: "available", updatedAt: "2030-06-01T12:00:00Z" }], total: 1, limit: 50, offset: 0 });
      }
      if (url.endsWith(`/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/drafts`)) {
        draftCalls += 1;
        return jsonResponse({
          spec: { id: specId, name: "Orders API", filename: "orders.json", sourceFormat: "openapi_json", documentTitle: "Orders API", documentVersion: "1.0.0", status: "available", updatedAt: "2030-06-01T12:00:00Z" },
          items: [{ operationRef: { method: "POST", path: "/orders", operationId: "createOrder" }, step: { enabled: true, name: "Create order", method: "POST", path: "/orders", queryParams: [], headers: [], body: { type: "none", contentType: null, rawText: null, formFields: [] }, settings: { timeoutMs: null, followRedirects: null, keepAlive: null, thinkTimeMs: null } }, source: { operationId: "createOrder", summary: "Create order" }, warnings: [] }],
          insert: { mode: "after_step", stepId: scenarioDetail.steps[0].id }, warnings: [],
        });
      }
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) && method === "GET") return jsonResponse(scenarioDetail);
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) && method === "PATCH") { patchCalls += 1; return jsonResponse(scenarioDetail); }
      if (url.includes("/api/v1/env-groups")) return jsonResponse(envListResponse);
      if (url.includes("/api/v1/dependency-files")) return jsonResponse(dependencyFileListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);
    expect(await screen.findByRole("heading", { name: "Checkout flow" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Generate Scenario|Generate Test Plan|Import operations/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "From OpenAPI" }));
    await userEvent.selectOptions(await screen.findByLabelText("API Catalog spec"), specId);
    await userEvent.click(await screen.findByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Preview Step drafts" }));
    expect(await screen.findByText("Create order")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Insert Step drafts" }));
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(draftCalls).toBe(1);
    expect(patchCalls).toBe(0);
  });
});
