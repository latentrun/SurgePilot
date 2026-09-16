import { focusManager } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import {
  apiCatalogScalarConfiguration,
  apiCatalogScalarHashCandidates,
  apiCatalogScalarHashIsTagOnly,
  apiCatalogScalarRootStyles,
  apiCatalogScalarTeleportStyles,
} from "./components/scalar-reference";

const scalarMockState = vi.hoisted(() => ({
  configuration: null as Record<string, unknown> | null,
  createHashTarget: false,
  mutateBodyMode: null as "light-mode" | "dark-mode" | null,
  throwOnRender: false,
}));

vi.mock("@scalar/api-reference-react/style.css?inline", () => ({
  default:
    ':root{--scalar-border-width:.5px;--scalar-radius:3px;--scalar-font:"Inter",ui-sans-serif}.dark-mode{color-scheme:dark}.light-mode{color-scheme:light}:where(.scalar-app){color:inherit}body{margin:0}',
}));

vi.mock("@scalar/api-reference-react", () => ({
  ApiReferenceReact: ({ configuration }: { configuration: unknown }) => {
    scalarMockState.configuration = configuration as Record<string, unknown>;
    if (scalarMockState.throwOnRender) {
      throw new Error("Scalar render failed");
    }
    if (scalarMockState.mutateBodyMode) {
      window.setTimeout(() => {
        const teleport = document.createElement("div");
        teleport.className = "scalar-app";
        teleport.textContent = "Client Libraries";
        document.body.append(teleport);
        document.body.classList.add(scalarMockState.mutateBodyMode ?? "light-mode");
        document.body.style.colorScheme =
          scalarMockState.mutateBodyMode === "dark-mode" ? "dark" : "light";
      }, 0);
    }
    return (
      <div data-testid="scalar-reference">
        {JSON.stringify(configuration)}
        {scalarMockState.createHashTarget ? (
          <>
            <div id="api-1/tag/orders">Orders tag</div>
            <div id="api-1/tag/orders/get">List orders operation</div>
          </>
        ) : null}
      </div>
    );
  },
}));

const workspaceId = "01HZW000000000000000000000";
const alternateWorkspaceId = "01HZW000000000000000000001";
const csrfToken = "csrf-token";
const specId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "api-catalog@example.com",
    displayName: "API Catalog User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: { id: workspaceId, name: "Default Workspace" },
  availableWorkspaces: [{ id: workspaceId, name: "Default Workspace", status: "active" }],
  currentWorkspace: { id: workspaceId, name: "Default Workspace", status: "active" },
  csrfToken,
};

const switchedWorkspaceSession = {
  ...authSession,
  availableWorkspaces: [
    { id: workspaceId, name: "Default Workspace", status: "active" },
    { id: alternateWorkspaceId, name: "Active Workspace", status: "active" },
  ],
  currentWorkspace: { id: alternateWorkspaceId, name: "Active Workspace", status: "active" },
};

const specSummary = {
  id: specId,
  name: "Orders docs",
  filename: "orders-openapi.yaml",
  sourceFormat: "openapi_yaml",
  documentTitle: "Orders API",
  documentVersion: "1.0.0",
  sizeBytes: 48152,
  sha256: "a".repeat(64),
  status: "available",
  createdAt: "2030-06-24T05:00:00.000Z",
  updatedAt: "2030-06-24T05:00:00.000Z",
};

const specDetail = {
  ...specSummary,
  openapiVersion: "3.1.0",
  contentUrl: `/api/v1/api-catalog/specs/${specId}/content`,
  validationMessage: null,
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
  if (input instanceof Request) return input.method;
  return init?.method ?? "GET";
}

function requestHeader(input: RequestInfo | URL, name: string) {
  return input instanceof Request ? input.headers.get(name) : null;
}

function mockFetch(session: typeof authSession = authSession) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const method = requestMethod(input, init);
    if (url.endsWith("/api/v1/auth/me")) return jsonResponse(session);
    if (url.endsWith("/api/v1/auth/csrf")) return jsonResponse({ csrfToken });
    if (url.includes("/api/v1/api-catalog/specs?") && method === "GET") {
      return jsonResponse({ items: [specSummary], total: 1, limit: 50, offset: 0 });
    }
    if (url.endsWith("/api/v1/api-catalog/specs") && method === "POST") {
      return jsonResponse(
        { ...specDetail, id: "01HZX3Y9M0E9W7Z6M5QK9S8P7B", name: "Inventory docs" },
        { status: 201 },
      );
    }
    if (url.endsWith(`/api/v1/api-catalog/specs/${specId}`) && method === "GET") {
      return jsonResponse(specDetail);
    }
    if (url.endsWith(`/api/v1/api-catalog/specs/${specId}`) && method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return jsonResponse({
      needsBootstrap: false,
      allowSignup: true,
      hasDefaultWorkspace: true,
      storageAvailable: true,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function scalarShadowText() {
  const host = screen.getByLabelText("API Reference");
  return host.shadowRoot?.textContent ?? "";
}

function scalarMockConfigurationText() {
  const host = screen.getByLabelText("API Reference");
  const reference = host.shadowRoot?.querySelector("[data-testid='scalar-reference']");
  return reference?.firstChild?.textContent ?? "{}";
}

beforeEach(() => {
  scalarMockState.configuration = null;
  scalarMockState.createHashTarget = false;
  scalarMockState.mutateBodyMode = null;
  scalarMockState.throwOnRender = false;
  document.body.className = "";
  document.body.removeAttribute("style");
  window.history.pushState({}, "", "/");
  window.localStorage.clear();
});

afterEach(() => {
  focusManager.setFocused(undefined);
  cleanup();
  vi.unstubAllGlobals();
});

describe("P2-00 API Catalog web flow", () => {
  it("renders navigation, list metadata, upload states, and delete confirmation", async () => {
    const fetchMock = mockFetch();
    window.history.pushState({}, "", "/api-catalog");

    render(<App />);

    await screen.findByRole("heading", { name: "API Catalog" });
    expect(screen.getByRole("link", { name: "API Catalog" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(document.querySelector("aside")?.className).toContain("bg-surface-container-low");
    expect(document.querySelector("aside")?.className).not.toContain("bg-surface-container-low/");
    expect(screen.getByLabelText("Global top bar").className).toContain("bg-surface-container-low");
    expect(screen.getByLabelText("Global top bar").className).not.toContain("bg-surface-container-low/");
    expect(await screen.findByText("Orders docs")).toBeInTheDocument();
    expect(
      screen.getByText(/documentation only and does not create Scenarios or Test Plans/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Scenario generation|Test Plan generation/i)).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "SHA-256" })).toBeInTheDocument();
    expect(screen.getByText(specSummary.sha256)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Orders docs" })).toHaveAttribute(
      "href",
      `/api-catalog/${specId}`,
    );

    await userEvent.click(screen.getByRole("button", { name: "Upload API Spec" }));
    const uploadDialog = await screen.findByRole("dialog", { name: "Upload API Spec" });
    expect(within(uploadDialog).getByRole("button", { name: "Choose file" })).toBeInTheDocument();
    expect(within(uploadDialog).getByText("No file chosen")).toBeInTheDocument();
    const file = new File(
      ["openapi: 3.1.0\ninfo:\n  title: Inventory API\n  version: 1\npaths: {}\n"],
      "inventory.yaml",
      { type: "text/yaml" },
    );
    await userEvent.upload(within(uploadDialog).getByLabelText("API spec file"), file);
    expect(within(uploadDialog).getByText("inventory.yaml")).toBeInTheDocument();
    await userEvent.type(within(uploadDialog).getByLabelText(/Display name/), "Inventory docs");
    await userEvent.click(within(uploadDialog).getByRole("button", { name: "Upload" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            requestUrl(input).endsWith("/api/v1/api-catalog/specs") &&
            requestMethod(input, init) === "POST",
        ),
      ).toBe(true),
    );
    const postCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).endsWith("/api/v1/api-catalog/specs") &&
        requestMethod(input, init) === "POST",
    );
    const postRequest = postCall?.[0] instanceof Request ? postCall[0] : null;
    expect(postRequest?.headers.get("x-csrf-token")).toBe(csrfToken);
    expect(postRequest?.headers.get("x-workspace-id")).toBe(workspaceId);

    await userEvent.click(screen.getByRole("button", { name: "Delete Orders docs" }));
    const deleteDialog = await screen.findByRole("dialog", { name: "Delete Orders docs?" });
    expect(
      within(deleteDialog).getByText(/does not affect Scenarios, Test Plans, Runs, or Artifacts/),
    ).toBeInTheDocument();
    await userEvent.click(within(deleteDialog).getByRole("button", { name: "Delete" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) => requestUrl(input).endsWith(specId) && requestMethod(input, init) === "DELETE",
        ),
      ).toBe(true),
    );
  });

  it("uses the selected current workspace instead of the default workspace", async () => {
    const fetchMock = mockFetch(switchedWorkspaceSession);
    window.history.pushState({}, "", "/api-catalog");

    render(<App />);

    await screen.findByRole("heading", { name: "API Catalog" });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input]) =>
            requestUrl(input).includes("/api/v1/api-catalog/specs?") &&
            requestHeader(input, "x-workspace-id") === alternateWorkspaceId,
        ),
      ).toBe(true),
    );
  });

  it("renders detail metadata and passes only same-origin contentUrl to the hardened Scalar wrapper", async () => {
    scalarMockState.mutateBodyMode = "dark-mode";
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    render(<App />);

    await screen.findByLabelText("API Reference");
    expect(document.querySelector("main")).toHaveClass("px-0");
    expect(document.querySelector("main")).not.toHaveClass("pt-24");
    expect(screen.queryByRole("heading", { name: "Orders docs" })).not.toBeInTheDocument();
    expect(screen.queryByText("Documentation only")).not.toBeInTheDocument();
    expect(screen.queryByText(/No request sending, API client, Agent, MCP/)).not.toBeInTheDocument();
    await waitFor(() => expect(scalarShadowText()).toContain("hideTestRequestButton"));
    const config = JSON.parse(scalarMockConfigurationText());
    expect(config.url).toBe(`/api/v1/api-catalog/specs/${specId}/content`);
    expect(config.url).not.toContain("minio");
    expect(config.url).not.toContain("http://");
    expect(config.hideTestRequestButton).toBe(true);
    expect(config.hideClientButton).toBe(true);
    expect(config.hiddenClients).toBeUndefined();
    expect(config.documentDownloadType).toBe("none");
    expect(config.darkMode).toBe(true);
    expect(config.hideDarkModeToggle).toBe(false);
    expect(config.forceDarkModeState).toBeUndefined();
    expect(config.persistAuth).toBe(false);
    expect(config.telemetry).toBe(false);
    expect(config.showDeveloperTools).toBe("never");
    expect(config.agent.disabled).toBe(true);
    expect(config.mcp.disabled).toBe(true);
    expect(config.mcp.url).toBeUndefined();
    expect(JSON.stringify(config)).not.toContain("proxyUrl");
    await waitFor(() => expect(document.body.classList.contains("dark-mode")).toBe(false));
    expect(document.body.style.colorScheme).toBe("");
    const scalarHost = screen.getByLabelText("API Reference");
    await waitFor(() =>
      expect(
        scalarHost.shadowRoot?.querySelector(".dark-mode")?.textContent,
      ).toContain("hideTestRequestButton"),
    );
    const teleportedScalarApp = Array.from(document.body.children).find(
      (node): node is HTMLElement =>
        node instanceof HTMLElement && node.classList.contains("scalar-app"),
    );
    expect(teleportedScalarApp).toBeTruthy();
    expect(teleportedScalarApp?.classList.contains("dark-mode")).toBe(true);
    const headStyle = document.head.querySelector("style[data-surgepilot-scalar-teleport-styles]");
    expect(headStyle?.textContent).toContain(".scalar-app");
    expect(headStyle?.textContent).toContain("--scalar-border-width:.5px");
    expect(headStyle?.textContent).not.toMatch(/(^|})\s*body\s*\{/);
  });

  it("defaults the Scalar reference canvas to dark mode", async () => {
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    render(<App />);

    const scalarHost = await screen.findByLabelText("API Reference");
    await waitFor(() => expect(scalarShadowText()).toContain("hideTestRequestButton"));
    expect(scalarHost).toHaveClass("bg-black");
    expect(scalarHost.shadowRoot?.querySelector(".surgepilot-scalar-root")).toHaveClass(
      "dark-mode",
      "bg-black",
    );
    expect(JSON.parse(scalarMockConfigurationText())).toMatchObject({
      darkMode: true,
      hideDarkModeToggle: false,
    });
  });

  it("keeps an initial Scalar URL fragment at the top without replacing History methods", async () => {
    scalarMockState.createHashTarget = true;
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}#tag/orders/get`);
    const originalPushState = window.history.pushState;
    const originalReplaceState = window.history.replaceState;

    try {
      render(<App />);

      await screen.findByLabelText("API Reference");
      await new Promise((resolve) => window.setTimeout(resolve, 75));
      expect(scrollIntoView).not.toHaveBeenCalled();
      expect(window.history.pushState).toBe(originalPushState);
      expect(window.history.replaceState).toBe(originalReplaceState);
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("does not turn Scalar passive hash synchronization into forced scrolling", async () => {
    scalarMockState.createHashTarget = true;
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    try {
      render(<App />);

      await screen.findByLabelText("API Reference");
      window.history.replaceState({}, "", `/api-catalog/${specId}#tag/orders/get`);
      await new Promise((resolve) => window.setTimeout(resolve, 25));
      expect(scrollIntoView).not.toHaveBeenCalled();
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("adapts explicit Scalar sidebar navigation inside the ShadowRoot", async () => {
    scalarMockState.createHashTarget = true;
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    try {
      render(<App />);

      await screen.findByLabelText("API Reference");
      const onSidebarClick = scalarMockState.configuration?.onSidebarClick;
      expect(onSidebarClick).toBeTypeOf("function");
      (onSidebarClick as (href: string) => void)(
        `http://localhost/api-catalog/${specId}#tag/orders/get`,
      );
      await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" }));
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("leaves tag-only sidebar clicks to Scalar but scrolls operation clicks", async () => {
    scalarMockState.createHashTarget = true;
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    try {
      render(<App />);

      await screen.findByLabelText("API Reference");
      const onSidebarClick = scalarMockState.configuration?.onSidebarClick;
      expect(onSidebarClick).toBeTypeOf("function");

      (onSidebarClick as (href: string) => void)(
        `http://localhost/api-catalog/${specId}#tag/orders`,
      );
      (onSidebarClick as (href: string) => void)(
        `http://localhost/api-catalog/${specId}#api-1/tag/orders`,
      );
      expect(scrollIntoView).not.toHaveBeenCalled();

      (onSidebarClick as (href: string) => void)(
        `http://localhost/api-catalog/${specId}#tag/orders/get`,
      );
      await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" }));
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("waits for a lazily rendered Scalar sidebar target", async () => {
    const scrollIntoView = vi.fn();
    const originalScrollIntoView = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = scrollIntoView;
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    try {
      render(<App />);

      const scalarHost = await screen.findByLabelText("API Reference");
      const onSidebarClick = scalarMockState.configuration?.onSidebarClick;
      expect(onSidebarClick).toBeTypeOf("function");
      (onSidebarClick as (href: string) => void)(
        `http://localhost/api-catalog/${specId}#tag/orders/get`,
      );
      window.setTimeout(() => {
        const target = document.createElement("div");
        target.id = "api-1/tag/orders/get";
        scalarHost.shadowRoot?.append(target);
      }, 1_100);

      await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" }), {
        timeout: 2_000,
      });
    } finally {
      Element.prototype.scrollIntoView = originalScrollIntoView;
    }
  });

  it("keeps Scalar render failures local to the detail page", async () => {
    scalarMockState.throwOnRender = true;
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    mockFetch();
    window.history.pushState({}, "", `/api-catalog/${specId}`);

    render(<App />);

    expect(await screen.findByText(/API reference rendering is unavailable/i)).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it("keeps the exported Scalar configuration request-disabled", () => {
    const config = apiCatalogScalarConfiguration("/api/v1/api-catalog/specs/test/content");
    const configRecord = config as Record<string, unknown>;
    expect(JSON.stringify(config)).not.toContain("proxyUrl");
    expect(JSON.stringify(config)).not.toContain("persistAuth\":true");
    expect(configRecord.hiddenClients).toBeUndefined();
    expect(configRecord.forceDarkModeState).toBeUndefined();
    expect(configRecord.mcp).toEqual({ disabled: true });
    expect(config).toMatchObject({
      hideTestRequestButton: true,
      hideClientButton: true,
      documentDownloadType: "none",
      darkMode: true,
      hideDarkModeToggle: false,
      persistAuth: false,
      telemetry: false,
      showDeveloperTools: "never",
    });
  });

  it("keeps Scalar adapter helpers scoped to API Catalog needs", () => {
    expect(apiCatalogScalarHashCandidates("#tag/orders/get")).toEqual([
      "tag/orders/get",
      "api-1/tag/orders/get",
    ]);
    expect(apiCatalogScalarHashCandidates("#api-1/tag/orders/get")).toEqual([
      "api-1/tag/orders/get",
    ]);
    expect(apiCatalogScalarHashIsTagOnly("#tag/orders")).toBe(true);
    expect(apiCatalogScalarHashIsTagOnly("#api-1/tag/orders")).toBe(true);
    expect(apiCatalogScalarHashIsTagOnly("#tag/orders/get")).toBe(false);
    expect(apiCatalogScalarHashIsTagOnly("#api-1/tag/orders/get")).toBe(false);
    expect(apiCatalogScalarRootStyles).toContain(".surgepilot-scalar-root");
    expect(apiCatalogScalarRootStyles).toContain("--scalar-border-width:.5px");
    expect(apiCatalogScalarTeleportStyles).toContain(".scalar-app");
    expect(apiCatalogScalarTeleportStyles).toContain("--scalar-border-width:.5px");
    expect(apiCatalogScalarTeleportStyles).not.toMatch(/(^|})\s*body\s*\{/);
  });
});
