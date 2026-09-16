import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";

const workspaceId = "01HZW000000000000000000000";
const csrfToken = "csrf-token";
const tokenId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "user@example.com",
    displayName: "Regular User",
    role: "user",
    status: "active",
  },
  defaultWorkspace: { id: workspaceId, name: "Default Workspace", status: "active" },
  availableWorkspaces: [
    {
      id: workspaceId,
      name: "Default Workspace",
      status: "active",
      membership: { kind: "member", joinedAt: null },
    },
  ],
  currentWorkspace: { id: workspaceId, name: "Default Workspace", status: "active" },
  permissions: {
    canManageWorkspaces: false,
    canManageUsers: false,
    canManageSystemSettings: false,
    canViewSetupStatus: false,
  },
  csrfToken,
};

const tokenMetadata = {
  id: tokenId,
  publicId: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
  name: "Existing automation",
  scopes: ["read"],
  workspaceAllowlist: [workspaceId],
  createdAt: "2030-06-30T08:00:00.000Z",
  expiresAt: "2030-07-30T08:00:00.000Z",
  revokedAt: null,
  lastUsedAt: null,
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

function requestJson(input: RequestInfo | URL) {
  if (!(input instanceof Request)) return null;
  return input.clone().json() as Promise<unknown>;
}

function mockFetch(sessionResponse = authSession) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const method = requestMethod(input, init);
    if (url.endsWith("/api/v1/auth/me")) return jsonResponse(sessionResponse);
    if (url.endsWith("/api/v1/auth/csrf")) return jsonResponse({ csrfToken });
    if (url.endsWith("/api/v1/account/api-tokens") && method === "GET") {
      return jsonResponse({ items: [tokenMetadata] });
    }
    if (url.endsWith("/api/v1/account/api-tokens") && method === "POST") {
      return jsonResponse(
        {
          token: {
            ...tokenMetadata,
            id: "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
            name: "CI deployer",
            scopes: ["read", "config:write"],
            plaintext: "surgepilot_pat_01HZX3Y9M0E9W7Z6M5QK9S8P7D_secret",
          },
        },
        { status: 201 },
      );
    }
    if (url.endsWith(`/api/v1/account/api-tokens/${tokenId}`) && method === "DELETE") {
      return new Response(null, { status: 204 });
    }
    return jsonResponse({ needsBootstrap: false, allowSignup: true, hasDefaultWorkspace: true, storageAvailable: true });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
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

describe("P2-02 Account API keys", () => {
  it("shows and copies the current Workspace ID with accessible feedback", async () => {
    mockFetch();
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    window.history.pushState({}, "", "/account/api-keys");

    render(<App />);

    expect(await screen.findByText("Workspace ID (x-workspace-id)")).toBeInTheDocument();
    expect(screen.getByText(workspaceId, { selector: "code" })).toBeInTheDocument();

    const timeoutSpy = vi.spyOn(window, "setTimeout");
    await userEvent.click(screen.getByRole("button", { name: "Copy Workspace ID" }));

    expect(writeText).toHaveBeenCalledWith(workspaceId);
    expect(screen.getByRole("button", { name: "Workspace ID copied" })).toHaveTextContent("Copied");

    const resetCall = timeoutSpy.mock.calls.find(([, delay]) => delay === 2000);
    expect(resetCall).toBeDefined();
    const resetCallback = resetCall?.[0];
    act(() => {
      if (typeof resetCallback === "function") resetCallback();
    });

    expect(screen.getByRole("button", { name: "Copy Workspace ID" })).toHaveTextContent("Copy");
  });

  it("announces a danger message when the Workspace ID cannot be copied", async () => {
    mockFetch();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: vi.fn(() => false),
    });
    window.history.pushState({}, "", "/account/api-keys");

    render(<App />);

    await userEvent.click(await screen.findByRole("button", { name: "Copy Workspace ID" }));

    const error = await screen.findByRole("alert");
    expect(error).toHaveTextContent(
      "Clipboard copy is unavailable. Use HTTPS or localhost, allow clipboard access, or select the text and copy it manually.",
    );
    expect(error).toHaveClass("text-danger");
    expect(screen.getByRole("button", { name: "Copy Workspace ID" })).toBeInTheDocument();
  });

  it("hides the Workspace ID controls when the session has no Workspace ID", async () => {
    mockFetch({
      ...authSession,
      currentWorkspace: { ...authSession.currentWorkspace, id: "" },
      defaultWorkspace: { ...authSession.defaultWorkspace, id: "" },
    });
    window.history.pushState({}, "", "/account/api-keys");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "API Keys" })).toBeInTheDocument();
    expect(screen.queryByText("Workspace ID (x-workspace-id)")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy Workspace ID" })).not.toBeInTheDocument();
  });

  it("lets a normal user create, view once, and revoke their own API key", async () => {
    const fetchMock = mockFetch();
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    window.history.pushState({}, "", "/account/api-keys");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "API Keys" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "API Keys" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByText("Admin")).not.toBeInTheDocument();
    expect(await screen.findByText("Existing automation")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Create API Key" }));
    const dialog = await screen.findByRole("dialog", { name: "Create API Key" });
    await userEvent.type(within(dialog).getByLabelText("Name"), "CI deployer");
    await userEvent.click(within(dialog).getByLabelText("Read"));
    await userEvent.click(within(dialog).getByLabelText("Config write"));
    await userEvent.click(within(dialog).getByLabelText("Dependency write"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Create key" }));

    await screen.findByText("Copy this token now. It will not be shown again.");
    expect(screen.getByText(/surgepilot_pat_/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith(
      "surgepilot_pat_01HZX3Y9M0E9W7Z6M5QK9S8P7D_secret",
    );
    expect(await within(dialog).findByRole("button", { name: "Copied" })).toBeInTheDocument();

    const postCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).endsWith("/api/v1/account/api-tokens") &&
        requestMethod(input, init) === "POST",
    );
    expect(postCall).toBeTruthy();
    expect(requestHeader(postCall?.[0] as Request, "x-csrf-token")).toBe(csrfToken);
    const body = (await requestJson(postCall?.[0] as Request)) as Record<string, unknown>;
    expect(body.scopes).toEqual(["read", "config:write", "dependency:write"]);
    expect(body.workspaceAllowlist).toEqual([workspaceId]);
    expect(JSON.stringify(body)).not.toMatch(/tokens:write/i);

    await userEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    await userEvent.click(screen.getByRole("button", { name: "Revoke Existing automation" }));
    const revokeDialog = await screen.findByRole("dialog", { name: "Revoke Existing automation?" });
    await userEvent.click(within(revokeDialog).getByRole("button", { name: "Revoke key" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            requestUrl(input).endsWith(`/api/v1/account/api-tokens/${tokenId}`) &&
            requestMethod(input, init) === "DELETE" &&
            requestHeader(input, "x-csrf-token") === csrfToken,
        ),
      ).toBe(true),
    );
  });
});
