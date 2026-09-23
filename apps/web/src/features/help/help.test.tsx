import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";


const workspaceId = "01HZW000000000000000000000";
const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "agent-user@example.com",
    displayName: "Agent User",
    role: "user",
    status: "active",
  },
  defaultWorkspace: {
    id: workspaceId,
    name: "Default Workspace",
    status: "active",
  },
  availableWorkspaces: [
    {
      id: workspaceId,
      name: "Default Workspace",
      status: "active",
      membership: { kind: "member", joinedAt: null },
    },
  ],
  currentWorkspace: {
    id: workspaceId,
    name: "Default Workspace",
    status: "active",
  },
  permissions: {
    canManageWorkspaces: false,
    canManageUsers: false,
    canManageSystemSettings: false,
    canViewSetupStatus: false,
  },
  csrfToken: "csrf-token",
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

function mockFetch(downloadResponse?: Response) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
    if (url.endsWith("/api/v1/account/ai-skill/download")) {
      return downloadResponse ??
        new Response(new Uint8Array([0x50, 0x4b, 0x03, 0x04]), {
          headers: { "content-type": "application/zip" },
        });
    }
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderHelp() {
  window.history.pushState({}, "", "/help");
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

describe("P2-04 Help AI Agents", () => {
  it("renders the governed authenticated tab order and agent guidance", async () => {
    mockFetch();
    renderHelp();

    expect(await screen.findByRole("heading", { name: "Help" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Help" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    const tabList = screen.getByRole("tablist", { name: "Help topics" });
    expect(within(tabList).getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Getting Started",
      "AI Agents",
      "Scripting",
      "API Catalog",
      "Troubleshooting",
      "Limits & Activation",
    ]);
    expect(screen.queryByText("Automation")).not.toBeInTheDocument();

    await userEvent.click(within(tabList).getByRole("tab", { name: "AI Agents" }));

    expect(screen.getByText("Use a user-owned local agent")).toBeInTheDocument();
    expect(screen.getByText(/explicit Workspace ID/i)).toBeInTheDocument();
    expect(screen.getByText(/bundled public-api\.openapi\.json/i)).toBeInTheDocument();
    expect(screen.getByText(/operationId allowlist/i)).toBeInTheDocument();
    expect(screen.getByText(/confirmation before write operations/i)).toBeInTheDocument();

    await userEvent.click(
      within(tabList).getByRole("tab", { name: "Limits & Activation" }),
    );
    expect(screen.getByText("System OpenAPI stays current")).toBeInTheDocument();
    expect(
      screen.getByText(/keeps that system-owned document aligned with the running SurgePilot contract on later API startups/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not automatically ingest user-provided URLs/i),
    ).toBeInTheDocument();
  });

  it("downloads the official source zip without a Workspace header", async () => {
    const fetchMock = mockFetch();
    const createObjectUrl = vi.fn(() => "blob:surgepilot-ai-skill");
    const revokeObjectUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: createObjectUrl,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: revokeObjectUrl,
    });
    let downloadedFilename = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      downloadedFilename = this.download;
    });
    renderHelp();

    await userEvent.click(await screen.findByRole("tab", { name: "AI Agents" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Download official AI skill" }),
    );

    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(downloadedFilename).toBe("surgepilot-public-api-skill.zip");
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:surgepilot-ai-skill");
    const downloadCall = fetchMock.mock.calls.find(([input]) =>
      requestUrl(input).endsWith("/api/v1/account/ai-skill/download"),
    );
    expect(downloadCall).toBeDefined();
    const request = downloadCall?.[0];
    expect(request).toBeInstanceOf(Request);
    expect((request as Request).headers.has("x-workspace-id")).toBe(false);
  });

  it("maps the route-local unavailable code to safe English copy", async () => {
    mockFetch(
      jsonResponse(
        {
          code: "AI_SKILL_SOURCE_NOT_AVAILABLE",
          message: "AI skill source is not available.",
          requestId: "01J00000000000000000000000",
        },
        { status: 503 },
      ),
    );
    renderHelp();

    await userEvent.click(await screen.findByRole("tab", { name: "AI Agents" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Download official AI skill" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Official skill source is temporarily unavailable. Try again later.",
    );
  });

  it("maps an expired session to a sign-in focused error", async () => {
    mockFetch(
      jsonResponse(
        {
          code: "UNAUTHENTICATED",
          message: "Authentication is required.",
          requestId: "01J00000000000000000000001",
        },
        { status: 401 },
      ),
    );
    renderHelp();

    await userEvent.click(await screen.findByRole("tab", { name: "AI Agents" }));
    await userEvent.click(
      screen.getByRole("button", { name: "Download official AI skill" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your session has expired. Sign in again before downloading the skill.",
    );
  });
});
