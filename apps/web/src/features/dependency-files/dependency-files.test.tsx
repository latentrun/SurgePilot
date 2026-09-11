import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";

const workspace = {
  id: "01HZW000000000000000000000",
  name: "Default Workspace",
};

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "dependency-preview@example.com",
    displayName: "Dependency Preview User",
    role: "admin",
    status: "active",
  },
  currentWorkspace: workspace,
  defaultWorkspace: workspace,
  csrfToken: "csrf-token",
};

const files = [
  {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
    filename: "users.html",
    contentType: "text/html",
    sizeBytes: 42,
    sha256: "a".repeat(64),
    inUse: false,
    createdBy: authSession.user.id,
    createdAt: "2030-06-01T12:00:00.000Z",
  },
  {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
    filename: "image.png",
    contentType: "image/png",
    sizeBytes: 2048,
    sha256: "b".repeat(64),
    inUse: false,
    createdBy: authSession.user.id,
    createdAt: "2030-06-01T12:01:00.000Z",
  },
  {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
    filename: "invalid.txt",
    contentType: "text/plain",
    sizeBytes: 3,
    sha256: "c".repeat(64),
    inUse: false,
    createdBy: authSession.user.id,
    createdAt: "2030-06-01T12:02:00.000Z",
  },
];

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...init.headers },
  });
}

function requestUrl(input: RequestInfo | URL) {
  return input instanceof Request ? input.url : String(input);
}

function mockFetch(
  previewHandler: (dependencyFileId: string) => Response | Promise<Response>,
) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.includes("/api/v1/auth/me")) return jsonResponse(authSession);
    if (url.includes("/api/v1/dependency-files?")) {
      return jsonResponse({ items: files, page: 1, pageSize: 20, total: files.length });
    }
    const match = url.match(/\/api\/v1\/dependency-files\/([^/]+)\/preview$/);
    if (match) return previewHandler(match[1]);
    return jsonResponse({});
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderDependencyFilesPage() {
  window.history.pushState({}, "", "/assets/dependency-files");
  return render(<App />);
}

beforeEach(() => {
  window.history.pushState({}, "", "/");
  window.localStorage.clear();
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("P1-06 Dependency File preview web flow", () => {
  it("opens a lazy preview drawer, renders HTML as text, shows truncation, and copies preview text", async () => {
    let resolvePreview: (response: Response) => void = () => undefined;
    const previewResponse = new Promise<Response>((resolve) => {
      resolvePreview = resolve;
    });
    const fetchMock = mockFetch((dependencyFileId) => {
      expect(dependencyFileId).toBe(files[0].id);
      return previewResponse;
    });

    renderDependencyFilesPage();

    await screen.findByRole("heading", { name: "Dependency Files" });
    await screen.findByText("users.html");
    expect(
      fetchMock.mock.calls.filter(([input]) => requestUrl(input).includes("/preview")),
    ).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: "Preview users.html" }));

    const dialog = await screen.findByRole("dialog", { name: "Preview users.html" });
    expect(within(dialog).getByText("Loading preview for users.html...")).toBeInTheDocument();
    resolvePreview(
      jsonResponse({
        id: files[0].id,
        filename: "users.html",
        contentType: "text/html",
        sizeBytes: 42,
        sha256: files[0].sha256,
        previewKind: "text",
        canPreview: true,
        truncated: true,
        maxBytes: 16,
        text: "<strong>not bold</strong>",
        reason: null,
      }),
    );
    expect(await within(dialog).findByText("<strong>not bold</strong>")).toBeInTheDocument();
    expect(dialog.querySelector("strong")).toBeNull();
    expect(within(dialog).getByText("Preview truncated at 16 B.")).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Copy preview text" }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("<strong>not bold</strong>");
  });

  it("shows a visible copy error and disables empty preview copy", async () => {
    const writeText = vi.fn(() => Promise.reject(new Error("denied")));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    mockFetch((dependencyFileId) =>
      jsonResponse({
        id: dependencyFileId,
        filename: "users.html",
        contentType: "text/html",
        sizeBytes: 42,
        sha256: files[0].sha256,
        previewKind: "text",
        canPreview: true,
        truncated: false,
        maxBytes: 16,
        text: dependencyFileId === files[0].id ? "copy me" : "",
        reason: null,
      }),
    );

    renderDependencyFilesPage();
    await screen.findByRole("heading", { name: "Dependency Files" });
    await screen.findByText("users.html");
    await userEvent.click(screen.getByRole("button", { name: "Preview users.html" }));
    let dialog = await screen.findByRole("dialog", { name: "Preview users.html" });
    await screen.findByText("copy me");
    await userEvent.click(within(dialog).getByRole("button", { name: "Copy preview text" }));
    expect(
      await within(dialog).findByText("Clipboard access is unavailable."),
    ).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Close preview" }));
    await userEvent.click(screen.getByRole("button", { name: "Preview image.png" }));
    dialog = await screen.findByRole("dialog", { name: "Preview image.png" });
    expect(
      await within(dialog).findByRole("button", { name: "Copy preview text" }),
    ).toBeDisabled();
  });

  it("renders unsupported and storage-error states while keeping Download available", async () => {
    mockFetch((dependencyFileId) => {
      if (dependencyFileId === files[1].id) {
        return jsonResponse({
          id: files[1].id,
          filename: "image.png",
          contentType: "image/png",
          sizeBytes: 2048,
          sha256: files[1].sha256,
          previewKind: "unsupported",
          canPreview: false,
          truncated: false,
          maxBytes: 65536,
          text: null,
          reason: "binary_content",
        });
      }
      return jsonResponse(
        {
          code: "STORAGE_UNAVAILABLE",
          message: "Storage is unavailable.",
          requestId: "req_preview",
        },
        { status: 503 },
      );
    });

    renderDependencyFilesPage();
    await screen.findByRole("heading", { name: "Dependency Files" });
    await screen.findByText("image.png");

    await userEvent.click(screen.getByRole("button", { name: "Preview image.png" }));
    let dialog = await screen.findByRole("dialog", { name: "Preview image.png" });
    expect(
      await within(dialog).findByText("This file looks binary, so inline preview is disabled."),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Download image.png" })).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Close preview" }));
    await userEvent.click(screen.getByRole("button", { name: "Preview invalid.txt" }));
    dialog = await screen.findByRole("dialog", { name: "Preview invalid.txt" });
    expect(
      await within(dialog).findByText("File storage is temporarily unavailable. Try again later."),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Retry preview" })).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Download invalid.txt" }),
    ).toBeInTheDocument();
  });

  it("does not show stale preview content after switching files", async () => {
    let resolveSlow: (response: Response) => void = () => undefined;
    const slowResponse = new Promise<Response>((resolve) => {
      resolveSlow = resolve;
    });
    mockFetch((dependencyFileId) => {
      if (dependencyFileId === files[0].id) return slowResponse;
      return jsonResponse({
        id: files[1].id,
        filename: "image.png",
        contentType: "image/png",
        sizeBytes: 2048,
        sha256: files[1].sha256,
        previewKind: "unsupported",
        canPreview: false,
        truncated: false,
        maxBytes: 65536,
        text: null,
        reason: "binary_content",
      });
    });

    renderDependencyFilesPage();
    await screen.findByRole("heading", { name: "Dependency Files" });
    await screen.findByText("users.html");
    await userEvent.click(screen.getByRole("button", { name: "Preview users.html" }));
    const firstDialog = await screen.findByRole("dialog", { name: "Preview users.html" });
    await userEvent.click(within(firstDialog).getByRole("button", { name: "Close preview" }));
    await userEvent.click(screen.getByRole("button", { name: "Preview image.png" }));

    const dialog = await screen.findByRole("dialog", { name: "Preview image.png" });
    expect(
      await within(dialog).findByText("This file looks binary, so inline preview is disabled."),
    ).toBeInTheDocument();

    resolveSlow(
      jsonResponse({
        id: files[0].id,
        filename: "users.html",
        contentType: "text/html",
        sizeBytes: 42,
        sha256: files[0].sha256,
        previewKind: "text",
        canPreview: true,
        truncated: false,
        maxBytes: 65536,
        text: "stale users content",
        reason: null,
      }),
    );
    await waitFor(() =>
      expect(within(dialog).queryByText("stale users content")).not.toBeInTheDocument(),
    );
  });
});
