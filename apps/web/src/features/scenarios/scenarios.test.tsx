import { focusManager } from "@tanstack/react-query";
import {
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

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "scenario@example.com",
    displayName: "Scenario User",
    role: "admin",
    status: "active",
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
  globalHeaders: [],
  variables: [],
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
  items: [
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
      filename: "avatar.png",
      contentType: "image/png",
      sizeBytes: 1234,
      sha256: "0".repeat(64),
      createdAt: "2030-06-01T12:00:00.000Z",
      updatedAt: "2030-06-01T12:00:00.000Z",
    },
    {
      id: "01HZX3Y9M0E9W7Z6M5QK9S8P8S",
      filename: "setup.groovy",
      contentType: "text/x-groovy",
      sizeBytes: 42,
      sha256: "1".repeat(64),
      createdAt: "2030-06-01T12:00:00.000Z",
      updatedAt: "2030-06-01T12:00:00.000Z",
    },
  ],
  page: 1,
  pageSize: 20,
  total: 1,
};

type CapturedChild = Record<string, unknown> & { id: string };

type CapturedStep = Record<string, unknown> & {
  id: string;
  name: string;
  queryParams?: CapturedChild[];
  headers?: CapturedChild[];
  assertions?: CapturedChild[];
};

type CapturedScenarioPatch = Record<string, unknown> & {
  steps: CapturedStep[];
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

function requestHeader(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  name: string,
) {
  if (input instanceof Request) return input.headers.get(name);
  const headers = new Headers(init?.headers);
  return headers.get(name);
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
  focusManager.setFocused(undefined);
  cleanup();
  vi.unstubAllGlobals();
});

describe("P0-05 scenarios web flow", () => {
  it("renders Scenarios navigation and empty list state", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });

    renderAt("/scenarios");

    expect(
      await screen.findByRole("heading", { name: "Scenarios" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Visual testing")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /scenarios/i })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(await screen.findByText("No scenarios yet")).toBeInTheDocument();
  });

  it("formats Scenario updated time consistently with other list pages", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/scenarios"))
        return jsonResponse({
          items: [scenarioDetail],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });

    renderAt("/scenarios");

    await screen.findByText("Checkout flow");
    const formattedUpdatedAt = new Intl.DateTimeFormat("en", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(scenarioDetail.updatedAt));

    expect(screen.getByText(formattedUpdatedAt)).toBeInTheDocument();
    expect(
      screen.queryByText(scenarioDetail.updatedAt),
    ).not.toBeInTheDocument();
  });

  it("creates a Scenario and navigates to the designer", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes("/api/v1/scenarios") &&
        requestMethod(input, init) === "GET"
      ) {
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      }
      if (
        url.endsWith("/api/v1/scenarios") &&
        requestMethod(input, init) === "POST"
      ) {
        const body = await requestBody(input, init);
        expect(body.name).toBe("Checkout flow");
        expect(body.tags).toEqual(["checkout", "smoke"]);
        return jsonResponse(scenarioDetail, { status: 201 });
      }
      return jsonResponse({});
    });

    renderAt("/scenarios");

    await screen.findByText("No scenarios yet");
    await userEvent.click(
      screen.getAllByRole("button", { name: "Create Scenario" })[0],
    );
    await userEvent.type(
      screen.getByLabelText("Scenario name"),
      "Checkout flow",
    );
    await userEvent.type(screen.getByLabelText("Tags"), "checkout, smoke");
    await userEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(window.location.pathname).toBe(`/scenarios/${scenarioDetail.id}`),
    );
    expect(fetchMock).toHaveBeenCalled();
  });

  it("renames a Scenario from the header and saves the existing revision", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
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
        return jsonResponse({
          ...scenarioDetail,
          ...patchBody,
          revision: 4,
        });
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
    await userEvent.click(
      screen.getByRole("button", { name: "Rename Scenario" }),
    );
    const nameInput = screen.getByRole("textbox", {
      name: "Scenario title",
    });
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Checkout smoke");

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    expect(patchBody).toMatchObject({
      name: "Checkout smoke",
      expectedRevision: 3,
    });
  });

  it("saves dirty changes before creating a Debug Run", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "PATCH"
      ) {
        const body = await requestBody(input, init);
        expect(body.expectedRevision).toBe(3);
        return jsonResponse({
          ...scenarioDetail,
          revision: 4,
          name: "Checkout smoke",
        });
      }
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse({
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
        });
      if (url.includes("/api/v1/load-nodes"))
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
              scope: "workspace",
              workspaceId: authSession.defaultWorkspace.id,
              host: "node.internal",
              sshPort: 22,
              sshUser: "surgepilot",
              runnerHome: "/opt/surgepilot/runner",
              authType: "password",
              credentialConfigured: true,
              credentialFingerprint: null,
              generatedPublicKey: null,
              maintainer: null,
              remark: null,
              status: "idle",
              lastStatusReason: null,
              runnerVersion: null,
              bundleVersion: null,
              lastInitializedAt: null,
              lastCheckedAt: null,
              lastHeartbeatAt: null,
              currentRunId: null,
              lastInitAttemptId: null,
              createdAt: "2030-06-01T12:00:00.000Z",
              updatedAt: "2030-06-01T12:00:00.000Z",
            },
          ],
          limit: 20,
          offset: 0,
          total: 1,
        });
      if (url.endsWith("/api/v1/runs") && method === "POST") {
        const body = await requestBody(input, init);
        expect(body.expectedSourceRevision).toBe(4);
        return jsonResponse(
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            state: "initializing",
            runType: "debug",
            sourceType: "debug_scenario",
            sourceId: scenarioDetail.id,
            selectedNodeId: "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            createdAt: "2030-06-01T12:40:00.000Z",
            deduplicated: false,
          },
          { status: 201 },
        );
      }
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Path"));
    await userEvent.type(screen.getByLabelText("Path"), "/v1/users-smoke");
    await userEvent.click(screen.getByRole("button", { name: "Debug" }));
    await userEvent.selectOptions(
      await screen.findByLabelText("Load Node"),
      "01HZX3Y9M0E9W7Z6M5QK9S8P7N",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Start Debug Run" }),
    );

    await waitFor(() =>
      expect(window.location.pathname).toBe("/runs/01HZX3Y9M0E9W7Z6M5QK9S8P7R"),
    );
    expect(
      fetchMock.mock.calls.map(([input]) => requestUrl(input)).join("\n"),
    ).not.toContain("runner/callbacks");
  });

  it("does not overwrite dirty Scenario draft after a detail refetch", async () => {
    let scenarioGetCount = 0;
    mockFetch((input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      ) {
        scenarioGetCount += 1;
        return jsonResponse(
          scenarioGetCount === 1
            ? scenarioDetail
            : {
                ...scenarioDetail,
                name: "Server refetch",
                tags: ["server"],
                steps: [
                  {
                    ...scenarioDetail.steps[0],
                    path: "/v1/server-refetch",
                  },
                ],
              },
        );
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
    const pathInput = screen.getByLabelText<HTMLInputElement>("Path");
    await userEvent.clear(pathInput);
    await userEvent.type(pathInput, "/v1/local-draft");
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();

    focusManager.setFocused(false);
    focusManager.setFocused(true);

    await waitFor(() => expect(scenarioGetCount).toBeGreaterThanOrEqual(2));
    expect(
      screen.getByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText<HTMLInputElement>("Path").value).toBe(
      "/v1/local-draft",
    );
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
  });

  it("uses a compact Scenario Designer header with clear Global Config and tabbed Step panels", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}`))
        return jsonResponse(scenarioDetail);
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
    expect(screen.queryByText("Visual Scenario")).not.toBeInTheDocument();
    expect(screen.getByText("Revision 3")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Global Config" }),
    ).toBeInTheDocument();
    const scenarioHeader = screen.getByTestId("scenario-designer-header");
    expect(
      within(scenarioHeader).getByLabelText("Environment"),
    ).toBeInTheDocument();
    expect(
      within(scenarioHeader).getByRole("button", { name: "Global Config" }),
    ).toBeInTheDocument();
    const scenarioSummary = screen.getByTestId("scenario-designer-summary");
    expect(
      within(scenarioSummary).getByText("Global Config"),
    ).toBeInTheDocument();
    expect(
      within(scenarioSummary).queryByRole("button", { name: "Global Config" }),
    ).not.toBeInTheDocument();
    const requestBar = screen.getByTestId("step-request-bar");
    expect(within(requestBar).getByLabelText("Method")).toBeInTheDocument();
    expect(within(requestBar).getByLabelText("Path")).toBeInTheDocument();
    expect(
      within(requestBar).getByRole("button", { name: "Disable" }),
    ).toBeInTheDocument();
    expect(
      within(requestBar).getByRole("button", { name: "Duplicate" }),
    ).toBeInTheDocument();
    expect(
      within(requestBar).getByRole("button", { name: "Delete" }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Scenario name")).not.toBeInTheDocument();

    const tabs = [
      "Params",
      "Headers",
      "Body",
      "Files",
      "Extractors",
      "Assertions",
      "Scripts",
      "Settings",
    ];
    for (const tab of tabs) {
      expect(
        screen.getByRole("tab", { name: new RegExp(tab) }),
      ).toBeInTheDocument();
    }
    expect(screen.getByRole("tab", { name: /Params/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.queryByRole("button", { name: "Add header" }),
    ).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Headers/ }));
    expect(
      screen.getByRole("button", { name: "Add header" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Add query param" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/Taurus/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/runner bundle/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/P0 exposes/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Settings/ }));
    expect(screen.getByTestId("step-settings-fields")).not.toHaveClass(
      "md:grid-cols-4",
    );
  });

  it("edits the P0-05 Step request fields and saves them through the Scenario contract", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
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

    await userEvent.click(
      screen.getByRole("button", { name: "Add query param" }),
    );
    await userEvent.type(screen.getByLabelText("Query param 1 name"), "page");
    await userEvent.type(screen.getByLabelText("Query param 1 value"), "1");

    await userEvent.click(screen.getByRole("tab", { name: /Headers/ }));
    await userEvent.click(screen.getByRole("button", { name: "Add header" }));
    await userEvent.type(
      screen.getByLabelText("Header 1 name"),
      "Authorization",
    );
    fireEvent.change(screen.getByLabelText("Header 1 value"), {
      target: { value: "Bearer ${token}" },
    });

    await userEvent.click(screen.getByRole("tab", { name: /Body/ }));
    await userEvent.selectOptions(screen.getByLabelText("Body type"), "raw");
    await userEvent.type(
      screen.getByLabelText("Raw content type"),
      "application/json",
    );
    fireEvent.change(screen.getByLabelText("Raw request body"), {
      target: { value: '{"sku":"${sku}"}' },
    });

    await userEvent.click(screen.getByRole("tab", { name: /Files/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add upload file" }),
    );
    await userEvent.type(
      screen.getByLabelText("Upload file 1 field name"),
      "avatar",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Upload file 1 dependency file"),
      "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
    );
    await userEvent.type(
      screen.getByLabelText("Upload file 1 MIME type"),
      "image/png",
    );

    await userEvent.click(screen.getByRole("tab", { name: /Extractors/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add JSONPath extractor" }),
    );
    await userEvent.type(
      screen.getByLabelText("Extractor 1 variable name"),
      "user_id",
    );
    fireEvent.change(screen.getByLabelText("Extractor 1 expression"), {
      target: { value: "$.data[0].id" },
    });

    await userEvent.click(screen.getByRole("tab", { name: /Assertions/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add Body Contains assertion" }),
    );
    await userEvent.type(
      screen.getByLabelText("Assertion 1 contains"),
      "success",
    );

    await userEvent.click(screen.getByRole("tab", { name: /Scripts/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add Groovy before script" }),
    );
    expect(screen.queryByLabelText("Script 1 text")).not.toBeInTheDocument();
    await userEvent.selectOptions(
      screen.getByLabelText("Script 1 Groovy file"),
      "01HZX3Y9M0E9W7Z6M5QK9S8P8S",
    );

    await userEvent.click(screen.getByRole("tab", { name: /Settings/ }));
    await userEvent.type(
      screen.getByLabelText("Step think time override (ms)"),
      "250",
    );
    await userEvent.type(
      screen.getByLabelText("Step timeout override (ms)"),
      "5000",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Step follow redirects override"),
      "false",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Step keep alive override"),
      "false",
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as CapturedScenarioPatch;
    const step = body.steps[0];
    expect(step.queryParams).toMatchObject([
      { name: "page", value: "1", enabled: true },
    ]);
    expect(step.headers).toMatchObject([
      { name: "Authorization", value: "Bearer ${token}", enabled: true },
    ]);
    expect(step.body).toMatchObject({
      type: "raw",
      contentType: "application/json",
      rawText: '{"sku":"${sku}"}',
    });
    expect(step.uploadFiles).toMatchObject([
      {
        fieldName: "avatar",
        dependencyFileId: "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        mimeType: "image/png",
        enabled: true,
      },
    ]);
    expect(step.extractors).toMatchObject([
      {
        type: "jsonpath",
        variableName: "user_id",
        expression: "$.data[0].id",
        matchNo: 1,
        subject: "body",
        enabled: true,
      },
    ]);
    expect(step.assertions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "body_contains",
          contains: "success",
          regexp: false,
          not: false,
          enabled: true,
        }),
      ]),
    );
    expect(step.scripts).toMatchObject([
      {
        execute: "before",
        language: "groovy",
        dependencyFileId: "01HZX3Y9M0E9W7Z6M5QK9S8P8S",
        enabled: true,
      },
    ]);
    expect(JSON.stringify(step.scripts)).not.toContain("scriptText");
    expect(step.settings).toMatchObject({
      thinkTimeMs: 250,
      timeoutMs: 5000,
      followRedirects: false,
      keepAlive: false,
    });
  });

  it("edits Scenario metadata and CSV data sources through the Scenario contract", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
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
    await userEvent.click(
      screen.getByRole("button", { name: "Global Config" }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Global Configuration",
    });
    const description = await screen.findByLabelText("Scenario description");
    await userEvent.clear(description);
    await userEvent.type(description, "Smoke checkout dependencies");
    await userEvent.clear(screen.getByLabelText("Tags"));
    await userEvent.type(screen.getByLabelText("Tags"), "checkout, smoke");
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "Data Sources" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Add CSV data source" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Data source 1 dependency file"),
      "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
    );
    await userEvent.clear(screen.getByLabelText("Data source 1 display name"));
    await userEvent.type(
      screen.getByLabelText("Data source 1 display name"),
      "Users CSV",
    );
    await userEvent.clear(
      screen.getByLabelText("Data source 1 variable names"),
    );
    await userEvent.type(
      screen.getByLabelText("Data source 1 variable names"),
      "user_id, token",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as CapturedScenarioPatch;
    expect(body.description).toBe("Smoke checkout dependencies");
    expect(body.tags).toEqual(["checkout", "smoke"]);
    expect(body.globalHeaders).toEqual([]);
    expect(body.variables).toEqual([]);
    expect(body.dataSources).toEqual([
      expect.objectContaining({
        dependencyFileId: "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        displayName: "Users CSV",
        delimiter: ",",
        variableNames: ["user_id", "token"],
        loop: true,
        randomOrder: false,
        enabled: true,
      }),
    ]);
  });

  it("edits global headers and non-secret Scenario variables without persisting until Save", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
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
    await userEvent.click(
      screen.getByRole("button", { name: "Global Config" }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Global Configuration",
    });
    expect(
      within(dialog).getByRole("tab", { name: "Settings" }),
    ).toHaveAttribute("aria-selected", "true");
    await userEvent.click(within(dialog).getByRole("tab", { name: "Headers" }));
    expect(within(dialog).getByText("No global headers.")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Add global header" }),
    );
    await userEvent.type(
      screen.getByLabelText("Global header 1 name"),
      "X-API-Version",
    );
    fireEvent.change(screen.getByLabelText("Global header 1 value"), {
      target: { value: "${api_version}" },
    });
    await userEvent.click(
      within(dialog).getByRole("tab", { name: "Variables" }),
    );
    expect(
      within(dialog).getByText(
        /ordinary non-secret Scenario defaults. Env Group variables override/i,
      ),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("No scenario variables."),
    ).toBeInTheDocument();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add variable" }),
    );
    await userEvent.type(
      screen.getByLabelText("Scenario variable 1 name"),
      "api_version",
    );
    await userEvent.type(
      screen.getByLabelText("Scenario variable 1 value"),
      "v1",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(patchBody).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as Record<string, unknown>;
    expect(body.globalHeaders).toEqual([
      expect.objectContaining({
        name: "X-API-Version",
        value: "${api_version}",
        enabled: true,
      }),
    ]);
    expect(body.variables).toEqual([
      expect.objectContaining({
        name: "api_version",
        value: "v1",
        enabled: true,
      }),
    ]);
    expect(
      screen.queryByText(/Apply YAML|Edit YAML|Import YAML|globalScripts/i),
    ).not.toBeInTheDocument();
  });

  it("cancels Global Configuration draft edits without marking the Scenario dirty", async () => {
    let patchCount = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "PATCH"
      ) {
        patchCount += 1;
        return jsonResponse({ ...scenarioDetail, revision: 4 });
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
    await userEvent.click(
      screen.getByRole("button", { name: "Global Config" }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Global Configuration",
    });
    await userEvent.click(within(dialog).getByRole("tab", { name: "Headers" }));
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Add global header" }),
    );
    await userEvent.type(
      screen.getByLabelText("Global header 1 name"),
      "X-Canceled",
    );
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Cancel" }),
    );

    expect(screen.queryByText("Unsaved changes")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Global Config" }),
    );
    const reopenedDialog = screen.getByRole("dialog", {
      name: "Global Configuration",
    });
    await userEvent.click(
      within(reopenedDialog).getByRole("tab", { name: "Headers" }),
    );
    expect(
      within(reopenedDialog).getByText("No global headers."),
    ).toBeInTheDocument();
    expect(patchCount).toBe(0);
  });

  it("routes global configuration save errors to the first invalid tab", async () => {
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "PATCH"
      ) {
        return jsonResponse(
          {
            code: "VALIDATION_ERROR",
            message: "Validation failed.",
            details: [
              {
                field: "globalHeaders[0].name",
                code: "invalid_header_name",
                message: "Header name is invalid.",
              },
            ],
          },
          { status: 422 },
        );
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
    await userEvent.click(
      screen.getByRole("button", { name: "Global Config" }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Global Configuration",
    });
    await userEvent.click(within(dialog).getByRole("tab", { name: "Headers" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add global header" }),
    );
    await userEvent.type(
      screen.getByLabelText("Global header 1 name"),
      "Bad Header",
    );
    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        "Scenario needs attention before it can be saved.",
      ),
    ).toBeInTheDocument();
    const reopenedDialog = screen.getByRole("dialog", {
      name: "Global Configuration",
    });
    expect(
      within(reopenedDialog).getByRole("tab", { name: /Headers/ }),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("edits form bodies and regexp or JSONPath assertion fields without exposing unsupported Taurus options", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse({
          ...scenarioDetail,
          steps: [{ ...scenarioDetail.steps[0], method: "POST" }],
        });
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
    await userEvent.click(screen.getByRole("tab", { name: /Body/ }));
    await userEvent.selectOptions(screen.getByLabelText("Body type"), "form");
    await userEvent.click(
      screen.getByRole("button", { name: "Add form field" }),
    );
    await userEvent.type(screen.getByLabelText("Form field 1 name"), "sku");
    fireEvent.change(screen.getByLabelText("Form field 1 value"), {
      target: { value: "${sku}" },
    });

    await userEvent.click(screen.getByRole("tab", { name: /Extractors/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add Regexp extractor" }),
    );
    await userEvent.type(
      screen.getByLabelText("Extractor 1 variable name"),
      "csrf",
    );
    await userEvent.type(
      screen.getByLabelText("Extractor 1 expression"),
      "csrf=(\\w+)",
    );
    fireEvent.change(screen.getByLabelText("Extractor 1 template"), {
      target: { value: "1" },
    });

    await userEvent.click(screen.getByRole("tab", { name: /Assertions/ }));
    await userEvent.click(
      screen.getByRole("button", { name: "Add JSONPath Equals assertion" }),
    );
    fireEvent.change(screen.getByLabelText("Assertion 1 JSONPath"), {
      target: { value: "$.ok" },
    });
    await userEvent.type(
      screen.getByLabelText("Assertion 1 expected value"),
      "true",
    );

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as CapturedScenarioPatch;
    const step = body.steps[0];
    expect(step.body).toMatchObject({
      type: "form",
      formFields: [{ name: "sku", value: "${sku}", enabled: true }],
    });
    expect(step.extractors).toMatchObject([
      {
        type: "regexp",
        variableName: "csrf",
        expression: "csrf=(\\w+)",
        template: "1",
      },
    ]);
    expect(step.assertions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          type: "jsonpath_equals",
          jsonpath: "$.ok",
          expectedValue: "true",
        }),
      ]),
    );
    expect(screen.queryByText(/body-file/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/XPath extractor/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /Apply YAML|Save YAML|Edit generated YAML|Run from preview/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("duplicates nested Step fields with fresh child IDs and reorders Steps by array order", async () => {
    const firstStep = {
      ...scenarioDetail.steps[0],
      id: "01HZX3Y9M0E9W7Z6M5QK9S8PAA",
      name: "First",
      queryParams: [
        {
          id: "01HZX3Y9M0E9W7Z6M5QK9S8PAB",
          name: "page",
          value: "1",
          enabled: true,
        },
      ],
      headers: [
        {
          id: "01HZX3Y9M0E9W7Z6M5QK9S8PAC",
          name: "Accept",
          value: "application/json",
          enabled: true,
        },
      ],
      assertions: [
        {
          id: "01HZX3Y9M0E9W7Z6M5QK9S8PAD",
          type: "status_code",
          expectedStatus: 200,
          not: false,
          regexp: false,
          enabled: true,
        },
      ],
    };
    const secondStep = {
      ...scenarioDetail.steps[0],
      id: "01HZX3Y9M0E9W7Z6M5QK9S8PAE",
      name: "Second",
      path: "/v1/second",
    };
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse({
          ...scenarioDetail,
          steps: [firstStep, secondStep],
          stepCount: 2,
          enabledStepCount: 2,
        });
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

    expect(await screen.findByText(/1\. First/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
    expect(
      screen.queryByRole("button", { name: "Move down" }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Move First down" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as CapturedScenarioPatch;
    expect(body.steps.map((step) => step.name)).toEqual([
      "Second",
      "First",
      "First copy",
    ]);
    const duplicate = body.steps[2];
    expect(duplicate.id).not.toBe(firstStep.id);
    expect(duplicate.queryParams![0].id).not.toBe(firstStep.queryParams[0].id);
    expect(duplicate.headers![0].id).not.toBe(firstStep.headers[0].id);
    expect(duplicate.assertions![0].id).not.toBe(firstStep.assertions[0].id);
  });

  it("blocks in-app navigation while Scenario drafts are dirty", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      const method = requestMethod(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}`))
        return jsonResponse(scenarioDetail);
      if (url.endsWith("/api/v1/scenarios") && method === "GET")
        return jsonResponse({ items: [], page: 1, pageSize: 20, total: 0 });
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Path"));
    await userEvent.type(screen.getByLabelText("Path"), "/v1/draft");
    await userEvent.click(screen.getByRole("link", { name: /scenarios/i }));

    expect(
      await screen.findByRole("heading", { name: "Leave without saving?" }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe(`/scenarios/${scenarioDetail.id}`);

    await userEvent.click(screen.getByRole("button", { name: "Stay" }));
    expect(screen.queryByText("Leave without saving?")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: /scenarios/i }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Discard and leave" }),
    );

    await waitFor(() => expect(window.location.pathname).toBe("/scenarios"));
  });

  it("persists the Environment selection without displaying variable values", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}`))
        return jsonResponse(scenarioDetail);
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      if (url.includes("/api/v1/load-nodes"))
        return jsonResponse({ items: [], limit: 20, offset: 0, total: 0 });
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    await userEvent.selectOptions(
      screen.getByLabelText("Environment"),
      "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
    );

    expect(
      window.localStorage.getItem(`surgepilot:scenario:${scenarioDetail.id}:env`),
    ).toBe("01HZX3Y9M0E9W7Z6M5QK9S8P7E");
    await userEvent.click(screen.getByRole("button", { name: "Debug" }));

    expect(screen.getAllByText("Staging").length).toBeGreaterThan(0);
    expect(
      screen.queryByText("https://secret.example.test"),
    ).not.toBeInTheDocument();

    await userEvent.selectOptions(
      screen.getByLabelText("Debug Environment"),
      "",
    );
    expect(screen.getByLabelText<HTMLSelectElement>("Environment").value).toBe(
      "",
    );
    expect(
      window.localStorage.getItem(`surgepilot:scenario:${scenarioDetail.id}:env`),
    ).toBeNull();
  });

  it("disables Debug when no enabled Step is available", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes(`/api/v1/scenarios/${scenarioDetail.id}`))
        return jsonResponse({
          ...scenarioDetail,
          enabledStepCount: 0,
          steps: scenarioDetail.steps.map((step) => ({
            ...step,
            enabled: false,
          })),
        });
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      return jsonResponse({});
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Debug" })).toBeDisabled();
  });
  it("previews a cURL import and appends the imported Step without auto-saving", async () => {
    let patchBody: Record<string, unknown> | null = null;
    let parseCalls = 0;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
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
    expect(screen.queryByText("Saved", { exact: true })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Import Step" }));
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(parseCalls).toBe(1);

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as CapturedScenarioPatch;
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

  it("generates OpenAPI Step drafts in the current Workspace without auto-saving", async () => {
    const activeWorkspaceId = "01HZW000000000000000000001";
    const currentWorkspaceSession = {
      ...authSession,
      availableWorkspaces: [
        { ...authSession.defaultWorkspace, status: "active" },
        { id: activeWorkspaceId, name: "Active Workspace", status: "active" },
      ],
      currentWorkspace: {
        id: activeWorkspaceId,
        name: "Active Workspace",
        status: "active",
      },
    };
    let patchBody: Record<string, unknown> | null = null;
    let draftRequest: Record<string, unknown> | null = null;
    const openApiWorkspaceHeaders: Array<string | null> = [];
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.includes("/openapi-step-generation/")) {
        openApiWorkspaceHeaders.push(
          requestHeader(input, init, "x-workspace-id"),
        );
      }
      if (url.endsWith("/api/v1/auth/me"))
        return jsonResponse(currentWorkspaceSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.endsWith(
          `/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/specs`,
        )
      )
        return jsonResponse({
          items: [
            {
              id: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
              name: "Orders API",
              filename: "orders.json",
              sourceFormat: "openapi_json",
              documentTitle: "Orders API",
              documentVersion: "1.0.0",
              status: "available",
              updatedAt: "2030-06-24T05:00:00Z",
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        });
      if (
        url.endsWith(
          `/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/specs/01HZX3Y9M0E9W7Z6M5QK9S8P7S/operations`,
        )
      )
        return jsonResponse({
          spec: {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            name: "Orders API",
            filename: "orders.json",
            sourceFormat: "openapi_json",
            documentTitle: "Orders API",
            documentVersion: "1.0.0",
            status: "available",
            updatedAt: "2030-06-24T05:00:00Z",
          },
          items: [
            {
              ref: {
                method: "GET",
                path: "/orders/{orderId}",
                operationId: "getOrder",
              },
              method: "GET",
              path: "/orders/{orderId}",
              operationId: "getOrder",
              summary: "Get one order",
              tags: ["orders"],
              displayName: "Get one order",
              hasRequestBody: false,
              supportedForGeneration: true,
              warningCodes: [],
            },
            {
              ref: {
                method: "POST",
                path: "/orders",
                operationId: "createOrder",
              },
              method: "POST",
              path: "/orders",
              operationId: "createOrder",
              summary: "Create order",
              tags: ["orders"],
              displayName: "Create order",
              hasRequestBody: true,
              supportedForGeneration: true,
              warningCodes: [],
            },
          ],
          warnings: [],
        });
      if (
        url.endsWith(
          `/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/drafts`,
        )
      ) {
        draftRequest = await requestBody(input, init);
        return jsonResponse({
          spec: {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            name: "Orders API",
            filename: "orders.json",
            sourceFormat: "openapi_json",
            documentTitle: "Orders API",
            documentVersion: "1.0.0",
            status: "available",
            updatedAt: "2030-06-24T05:00:00Z",
          },
          insert: {
            mode: "after_step",
            stepId: scenarioDetail.steps[0].id,
          },
          items: [
            {
              operationRef: {
                method: "POST",
                path: "/orders",
                operationId: "createOrder",
              },
              step: {
                enabled: true,
                name: "Create order",
                method: "POST",
                path: "/orders",
                queryParams: [],
                headers: [],
                body: {
                  type: "raw",
                  contentType: "application/json",
                  rawText: '{"sku":"SKU-1"}',
                  formFields: [],
                },
                settings: {
                  timeoutMs: null,
                  followRedirects: null,
                  keepAlive: null,
                  thinkTimeMs: null,
                },
              },
              source: { operationId: "createOrder", summary: "Create order" },
              warnings: [
                {
                  code: "JSON_BODY_EXAMPLE_GENERATED",
                  message:
                    "A JSON body example was generated from the API spec.",
                  field: "step.body.rawText",
                },
              ],
            },
            {
              operationRef: {
                method: "GET",
                path: "/orders/{orderId}",
                operationId: "getOrder",
              },
              step: {
                enabled: true,
                name: "Get one order",
                method: "GET",
                path: "/orders/${orderId}",
                queryParams: [
                  { name: "include", value: "items", enabled: true },
                ],
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
              source: { operationId: "getOrder", summary: "Get one order" },
              warnings: [
                {
                  code: "PATH_VARIABLE_PLACEHOLDER_REQUIRED",
                  message: "Fill orderId before running this Step.",
                  field: "step.path",
                },
              ],
            },
          ],
          warnings: [],
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
    expect(
      screen.getByRole("button", { name: "Add Step" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Import cURL" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Add Step" }));
    await userEvent.click(screen.getByRole("button", { name: "From OpenAPI" }));

    const dialog = await screen.findByRole("dialog", {
      name: "Generate from OpenAPI",
    });
    await userEvent.selectOptions(
      within(dialog).getByLabelText("API Catalog spec"),
      "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
    );
    await within(dialog).findByText("Get one order");
    const operationCheckboxes = within(dialog).getAllByRole("checkbox");
    await userEvent.click(operationCheckboxes[0]);
    await userEvent.click(operationCheckboxes[1]);
    await userEvent.click(
      within(dialog).getAllByRole("button", { name: "Up" })[1],
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Preview Step drafts" }),
    );

    expect(await within(dialog).findByText("POST /orders")).toBeInTheDocument();
    const postDraftMatches = within(dialog).getAllByText(/POST \/orders/);
    const postDraftCard =
      postDraftMatches[postDraftMatches.length - 1].closest("div");
    expect(postDraftCard).not.toBeNull();
    expect(
      within(postDraftCard as HTMLElement).getByText("application/json body"),
    ).toBeInTheDocument();
    expect(
      within(postDraftCard as HTMLElement).queryByText("no body"),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByText(/GET \/orders\/\$\{orderId\}/),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Fill orderId before running this Step."),
    ).toBeInTheDocument();
    expect(draftRequest).toMatchObject({
      specId: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
      operationRefs: [
        { method: "POST", path: "/orders", operationId: "createOrder" },
        { method: "GET", path: "/orders/{orderId}", operationId: "getOrder" },
      ],
      insert: { mode: "after_step" },
    });
    expect(
      (draftRequest as { insert?: { stepId?: string } } | null)?.insert?.stepId,
    ).not.toBe(scenarioDetail.steps[0].id);
    expect(openApiWorkspaceHeaders).not.toHaveLength(0);
    expect(new Set(openApiWorkspaceHeaders)).toEqual(
      new Set([activeWorkspaceId]),
    );
    expect(openApiWorkspaceHeaders).not.toContain(
      authSession.defaultWorkspace.id,
    );

    await userEvent.click(
      within(dialog).getByRole("button", { name: "Insert Step drafts" }),
    );
    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    expect(patchBody).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(patchBody).not.toBeNull());
    const body = patchBody as unknown as CapturedScenarioPatch;
    expect(body.steps).toHaveLength(4);
    expect(body.steps.map((step) => step.name)).toEqual([
      "List users",
      "New request",
      "Create order",
      "Get one order",
    ]);
    expect(body.steps[2]).toMatchObject({
      method: "POST",
      path: "/orders",
      body: { type: "raw", contentType: "application/json" },
    });
    expect(body.steps[3]).toMatchObject({
      method: "GET",
      path: "/orders/${orderId}",
      queryParams: [{ name: "include", value: "items", enabled: true }],
    });
    expect(body.steps[2].assertions).toEqual([]);
    expect(body.steps[3].assertions).toEqual([]);
    expect(body.steps[2].id).not.toBe(scenarioDetail.steps[0].id);
  });

  it("shows OpenAPI loading states and reuses fresh modal queries", async () => {
    let specRequests = 0;
    let operationRequests = 0;
    let resolveSpecs!: (response: Response) => void;
    let resolveOperations!: (response: Response) => void;
    const specsResponse = new Promise<Response>((resolve) => {
      resolveSpecs = resolve;
    });
    const operationsResponse = new Promise<Response>((resolve) => {
      resolveOperations = resolve;
    });
    mockFetch((input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.endsWith(
          `/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/specs`,
        )
      ) {
        specRequests += 1;
        return specsResponse;
      }
      if (
        url.endsWith(
          `/api/v1/scenarios/${scenarioDetail.id}/openapi-step-generation/specs/01HZX3Y9M0E9W7Z6M5QK9S8P7S/operations`,
        )
      ) {
        operationRequests += 1;
        return operationsResponse;
      }
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
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
    await userEvent.click(screen.getByRole("button", { name: "From OpenAPI" }));

    const firstDialog = await screen.findByRole("dialog", {
      name: "Generate from OpenAPI",
    });
    const loadingSpecSelect =
      within(firstDialog).getByLabelText("API Catalog spec");
    expect(loadingSpecSelect).toBeDisabled();
    expect(
      within(firstDialog).getByRole("option", {
        name: "Loading API Catalog specs…",
      }),
    ).toBeInTheDocument();

    resolveSpecs(
      jsonResponse({
        items: [
          {
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
            name: "Orders API",
            filename: "orders.json",
            sourceFormat: "openapi_json",
            documentTitle: "Orders API",
            documentVersion: "1.0.0",
            status: "available",
            updatedAt: "2030-06-24T05:00:00Z",
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      }),
    );
    const firstSpecSelect = await within(firstDialog).findByRole("combobox", {
      name: "API Catalog spec",
    });
    await waitFor(() => expect(firstSpecSelect).toBeEnabled());
    await userEvent.selectOptions(
      firstSpecSelect,
      "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
    );
    expect(
      await within(firstDialog).findByText("Loading operations…"),
    ).toBeInTheDocument();
    expect(
      within(firstDialog).getByRole("button", { name: "Preview Step drafts" }),
    ).toBeDisabled();

    resolveOperations(
      jsonResponse({
        spec: {
          id: "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
          name: "Orders API",
          filename: "orders.json",
          sourceFormat: "openapi_json",
          documentTitle: "Orders API",
          documentVersion: "1.0.0",
          status: "available",
          updatedAt: "2030-06-24T05:00:00Z",
        },
        items: [
          {
            ref: {
              method: "GET",
              path: "/orders/{orderId}",
              operationId: "getOrder",
            },
            method: "GET",
            path: "/orders/{orderId}",
            operationId: "getOrder",
            summary: "Get one order",
            tags: ["orders"],
            displayName: "Get one order",
            hasRequestBody: false,
            supportedForGeneration: true,
            warningCodes: [],
          },
        ],
        warnings: [],
      }),
    );
    expect(
      await within(firstDialog).findByText("Get one order"),
    ).toBeInTheDocument();

    await userEvent.click(
      within(firstDialog).getByRole("button", { name: "Close" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "From OpenAPI" }));
    const secondDialog = await screen.findByRole("dialog", {
      name: "Generate from OpenAPI",
    });
    const secondSpecSelect = within(secondDialog).getByRole("combobox", {
      name: "API Catalog spec",
    });
    expect(secondSpecSelect).toBeEnabled();
    expect(specRequests).toBe(1);

    await userEvent.selectOptions(
      secondSpecSelect,
      "01HZX3Y9M0E9W7Z6M5QK9S8P7S",
    );
    expect(
      await within(secondDialog).findByText("Get one order"),
    ).toBeInTheDocument();
    expect(operationRequests).toBe(1);
  });

  it("replaces the selected Step and applies the base URL only after explicit confirmation", async () => {
    let patchBody: Record<string, unknown> | null = null;
    mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
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
    const body = patchBody as unknown as CapturedScenarioPatch;
    expect(body.baseUrlExpression).toBe("https://replace.example.test");
    expect(body.steps).toHaveLength(1);
    expect(body.steps[0]).toMatchObject({
      id: scenarioDetail.steps[0].id,
      name: "GET /v1/replaced",
      method: "GET",
      path: "/v1/replaced",
    });
    expect(body.steps[0].assertions?.length).toBeGreaterThan(0);
  });
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
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (url.includes("/api/v1/scenarios") && method === "GET") {
        return jsonResponse({
          items: [{ ...scenarioDetail, tags: [] }],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      if (url.endsWith(`/api/v1/scenarios/${scenarioDetail.id}/clone`)) {
        const body = await requestBody(input, init);
        expect(method).toBe("POST");
        expect(body).toEqual({});
        return jsonResponse(clonedScenario, { status: 201 });
      }
      return jsonResponse({});
    });

    renderAt("/scenarios");

    expect(await screen.findByText("Checkout flow")).toBeInTheDocument();
    expect(screen.getByText("No tags")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clone" }));

    await waitFor(() =>
      expect(window.location.pathname).toBe(`/scenarios/${clonedScenario.id}`),
    );
  });

  it("uses Archive confirmation copy for Scenario and does not say permanent delete", async () => {
    mockFetch((input) => {
      const url = requestUrl(input);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/scenarios")) {
        return jsonResponse({
          items: [scenarioDetail],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      return jsonResponse({});
    });

    renderAt("/scenarios");

    expect(await screen.findByText("Checkout flow")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    expect(
      screen.getByRole("dialog", { name: "Archive Scenario" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/hidden from active lists/i)).toBeInTheDocument();
    expect(
      screen.getByText(/historical Run Reports keep/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/permanent/i)).not.toBeInTheDocument();
  });

  it("hides the generated YAML preview on the Scenario designer", async () => {
    const fetchMock = mockFetch(async (input, init) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.endsWith("/api/v1/auth/csrf"))
        return jsonResponse({ csrfToken: "csrf-token" });
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "GET"
      )
        return jsonResponse(scenarioDetail);
      if (
        url.includes(`/api/v1/scenarios/${scenarioDetail.id}`) &&
        method === "PATCH"
      ) {
        const body = (await requestBody(input, init)) as typeof scenarioDetail;
        return jsonResponse({
          ...scenarioDetail,
          ...body,
          revision: scenarioDetail.revision + 1,
        });
      }
      if (url.includes("/api/v1/env-groups"))
        return jsonResponse(envListResponse);
      if (url.includes("/api/v1/dependency-files"))
        return jsonResponse(dependencyFileListResponse);
      return jsonResponse({ items: [], limit: 100, offset: 0, total: 0 });
    });

    renderAt(`/scenarios/${scenarioDetail.id}`);

    expect(
      await screen.findByRole("heading", { name: "Checkout flow" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Generated YAML Preview" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Preview environment"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Preview YAML" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/scenario: surgepilot_scenario/)).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).includes("/execution-preview"),
      ),
    ).toBe(false);
    expect(fetchMock).toHaveBeenCalled();
  });
});
