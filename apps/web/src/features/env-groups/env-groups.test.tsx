import { focusManager } from "@tanstack/react-query";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";

const workspaceId = "01HZW000000000000000000000";
const groupId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "env-secret@example.com",
    displayName: "Env Secret User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: { id: workspaceId, name: "Default Workspace" },
  currentWorkspace: { id: workspaceId, name: "Default Workspace" },
  availableWorkspaces: [
    {
      id: workspaceId,
      name: "Default Workspace",
      membership: { kind: "member", joinedAt: null },
    },
  ],
  permissions: {
    canManageWorkspaces: true,
    canManageUsers: true,
    canManageSystemSettings: true,
    canViewSetupStatus: true,
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

function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input.method : init?.method;
}

async function requestBody(input: RequestInfo | URL, init?: RequestInit) {
  if (input instanceof Request) {
    return input.clone().json();
  }
  return JSON.parse(String(init?.body ?? "{}"));
}

function renderEnvGroupsPage() {
  window.history.pushState({}, "", "/assets/env-groups");
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

describe("P2-03 Env Group secret web flow", () => {
  it("masks existing secrets and preserves them when the value is left blank", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/env-groups?") && method === "GET") {
        return jsonResponse({
          items: [
            {
              id: groupId,
              name: "Secret staging",
              description: "Masked variables",
              variableCount: 2,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-07-01T00:00:00Z",
              updatedAt: "2030-07-01T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      if (url.endsWith(`/api/v1/env-groups/${groupId}`) && method === "GET") {
        return jsonResponse({
          id: groupId,
          name: "Secret staging",
          description: "Masked variables",
          variableCount: 2,
          inUse: false,
          variables: {
            BASE_URL: { type: "plain", value: "https://api.example.test" },
            API_TOKEN: {
              type: "secret",
              hasValue: true,
              displayValue: "********",
            },
          },
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-07-01T00:00:00Z",
          updatedAt: "2030-07-01T00:00:00Z",
        });
      }
      if (url.endsWith(`/api/v1/env-groups/${groupId}`) && method === "PATCH") {
        return jsonResponse({
          id: groupId,
          name: "Secret staging",
          description: "Masked variables",
          variableCount: 2,
          inUse: false,
          variables: {
            BASE_URL: { type: "plain", value: "https://api.example.test" },
            API_TOKEN: {
              type: "secret",
              hasValue: true,
              displayValue: "********",
            },
          },
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-07-01T00:00:00Z",
          updatedAt: "2030-07-01T00:00:00Z",
        });
      }
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderEnvGroupsPage();

    await screen.findByRole("heading", { name: "Env Groups" });
    await screen.findByText("Secret staging");
    await userEvent.click(
      screen.getByRole("button", { name: "Edit Secret staging" }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Edit Env Group",
    });

    expect(
      within(dialog).getByPlaceholderText("******** (leave blank to keep)"),
    ).toHaveValue("");
    const secretToggles = within(dialog).getAllByRole("checkbox", {
      name: "Secret",
    });
    expect(secretToggles).toHaveLength(2);
    expect(secretToggles[0]).not.toBeChecked();
    expect(secretToggles[1]).toBeChecked();
    expect(within(dialog).queryByLabelText("Type")).toBeNull();
    expect(dialog).not.toHaveTextContent("runtime-token");
    expect(
      within(dialog).queryByRole("button", { name: /reveal/i }),
    ).toBeNull();
    expect(
      within(dialog).queryByRole("button", { name: /copy secret/i }),
    ).toBeNull();

    await userEvent.click(
      within(dialog).getByRole("button", { name: "Save Env Group" }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([input]) =>
          requestUrl(input).includes(`/api/v1/env-groups/${groupId}`),
        ),
      ).toBe(true),
    );
    const patchCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).endsWith(`/api/v1/env-groups/${groupId}`) &&
        requestMethod(input, init) === "PATCH",
    );
    expect(patchCall).toBeDefined();
    await expect(
      requestBody(patchCall![0], patchCall![1]),
    ).resolves.toMatchObject({
      variables: {
        BASE_URL: { type: "plain", value: "https://api.example.test" },
        API_TOKEN: { type: "secret" },
      },
    });
  });

  it("submits a replacement value only when the user enters a new secret", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (url.endsWith("/api/v1/auth/me")) return jsonResponse(authSession);
      if (url.includes("/api/v1/env-groups?") && method === "GET") {
        return jsonResponse({
          items: [
            {
              id: groupId,
              name: "Secret staging",
              description: "Masked variables",
              variableCount: 1,
              inUse: false,
              createdBy: authSession.user.id,
              updatedBy: authSession.user.id,
              createdAt: "2030-07-01T00:00:00Z",
              updatedAt: "2030-07-01T00:00:00Z",
            },
          ],
          page: 1,
          pageSize: 20,
          total: 1,
        });
      }
      if (url.endsWith(`/api/v1/env-groups/${groupId}`) && method === "GET") {
        return jsonResponse({
          id: groupId,
          name: "Secret staging",
          description: "Masked variables",
          variableCount: 1,
          inUse: false,
          variables: {
            API_TOKEN: {
              type: "secret",
              hasValue: true,
              displayValue: "********",
            },
          },
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-07-01T00:00:00Z",
          updatedAt: "2030-07-01T00:00:00Z",
        });
      }
      if (url.endsWith(`/api/v1/env-groups/${groupId}`) && method === "PATCH") {
        return jsonResponse({
          id: groupId,
          name: "Secret staging",
          description: "Masked variables",
          variableCount: 1,
          inUse: false,
          variables: {
            API_TOKEN: {
              type: "secret",
              hasValue: true,
              displayValue: "********",
            },
          },
          createdBy: authSession.user.id,
          updatedBy: authSession.user.id,
          createdAt: "2030-07-01T00:00:00Z",
          updatedAt: "2030-07-01T00:00:00Z",
        });
      }
      return jsonResponse({
        needsBootstrap: false,
        allowSignup: true,
        hasDefaultWorkspace: true,
        storageAvailable: true,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderEnvGroupsPage();

    await screen.findByRole("heading", { name: "Env Groups" });
    await screen.findByText("Secret staging");
    await userEvent.click(
      screen.getByRole("button", { name: "Edit Secret staging" }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: "Edit Env Group",
    });
    await userEvent.type(
      within(dialog).getByPlaceholderText("******** (leave blank to keep)"),
      "replacement-token",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Save Env Group" }),
    );

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([input, init]) =>
            requestUrl(input).endsWith(`/api/v1/env-groups/${groupId}`) &&
            requestMethod(input, init) === "PATCH",
        ),
      ).toBe(true),
    );
    const patchCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).endsWith(`/api/v1/env-groups/${groupId}`) &&
        requestMethod(input, init) === "PATCH",
    );
    expect(patchCall).toBeDefined();
    await expect(
      requestBody(patchCall![0], patchCall![1]),
    ).resolves.toMatchObject({
      variables: {
        API_TOKEN: { type: "secret", value: "replacement-token" },
      },
    });
  });
});
