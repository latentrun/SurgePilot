import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { apiCatalogScalarConfiguration } from "./components/scalar-reference";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("P2-00 API Catalog renderer boundary", () => {
  it("routes the active API Catalog list page through the authenticated App shell", async () => {
    const workspace = { id: "01HZW000000000000000000000", name: "Default Workspace" };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/auth/me")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              user: { id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U", email: "catalog@example.com", displayName: "Catalog", role: "admin", status: "active" },
              defaultWorkspace: workspace,
              currentWorkspace: workspace,
              availableWorkspaces: [workspace],
              csrfToken: "csrf-token",
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          ),
        );
      }
      if (url.includes("/api/v1/api-catalog/specs")) {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], total: 0, limit: 50, offset: 0 }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.pushState({}, "", "/api-catalog");

    render(<App />);

    expect(await screen.findByRole("heading", { name: "API Catalog" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "API Catalog" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText(/documentation only/i)).toBeInTheDocument();
    expect(screen.queryByText(/Scenario generation|Test Plan generation/i)).not.toBeInTheDocument();
  });

  it("disables request sending and external integrations", () => {
    const configuration = apiCatalogScalarConfiguration(
      "/api/v1/api-catalog/specs/01HZX3Y9M0E9W7Z6M5QK9S8P7A/content",
    );
    expect(configuration).toMatchObject({
      hideTestRequestButton: true,
      hideClientButton: true,
      documentDownloadType: "none",
      persistAuth: false,
      telemetry: false,
      showDeveloperTools: "never",
      agent: { disabled: true, hideAddApi: true },
      mcp: { disabled: true },
    });
    expect(configuration).not.toHaveProperty("proxyUrl");
    expect(configuration.url).toMatch(/^\/api\/v1\/api-catalog\/specs\//);
  });

  it("rejects external renderer inputs and never receives storage internals", () => {
    expect(() => apiCatalogScalarConfiguration("https://minio.example.invalid/spec")).toThrow(
      "same-origin",
    );
    expect(JSON.stringify(apiCatalogScalarConfiguration("/api/v1/api-catalog/specs/id/content"))).not.toMatch(
      /minio|storageBucket|storageObjectKey|presigned|serverPath/i,
    );
  });
});
