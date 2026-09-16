import { afterEach, describe, expect, it, vi } from "vitest";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL) {
  return input instanceof Request ? input.url : String(input);
}

describe("api client base URL", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("uses VITE_API_BASE_URL when configured", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/custom-api");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return Promise.resolve(
        jsonResponse({
          needsBootstrap: false,
          allowSignup: true,
          hasDefaultWorkspace: true,
          storageAvailable: true,
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { getSetupStatus } = await import("./api-client");
    await getSetupStatus();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(requestUrl(fetchMock.mock.calls[0][0])).toBe(
      "https://api.example.test/custom-api/v1/setup/status",
    );
  });
});
