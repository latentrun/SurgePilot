import { expect, test } from "@playwright/test";

const workspaceId = "01HZW000000000000000000000";
const nodeId = "01HZX3Y9M0E9W7Z6M5QK9S8P7A";
const attemptId = "01HZX3Y9M0E9W7Z6M5QK9S8P7B";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
    email: "load-nodes@example.com",
    displayName: "Load Nodes User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: workspaceId,
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

function loadNode(status: "uninitialized" | "initializing" | "idle") {
  const initialized = status === "idle";
  return {
    id: nodeId,
    scope: "workspace",
    workspaceId,
    host: "load-node-smoke.internal",
    sshPort: 22,
    sshUser: "surgepilot",
    runnerHome: "/opt/surgepilot/runner",
    authType: "password",
    credentialConfigured: true,
    credentialFingerprint: null,
    generatedPublicKey: null,
    maintainer: null,
    remark: null,
    status,
    lastStatusReason: null,
    runnerVersion: initialized ? "0.1.0" : null,
    bundleVersion: initialized ? "p0-03" : null,
    lastInitializedAt: initialized ? "2030-07-15T10:00:00Z" : null,
    lastCheckedAt: initialized ? "2030-07-15T10:00:00Z" : null,
    lastHeartbeatAt: null,
    currentRunId: null,
    lastInitAttemptId: status === "uninitialized" ? null : attemptId,
    createdAt: "2030-07-15T09:00:00Z",
    updatedAt: "2030-07-15T10:00:00Z",
  };
}

test("registers, initializes, reads logs, and archives a Load Node after host-key confirmation", async ({
  page,
}) => {
  let currentNode: ReturnType<typeof loadNode> | null = null;
  let scanPayload: Record<string, unknown> | null = null;
  let createPayload: Record<string, unknown> | null = null;
  let initializePayload: Record<string, unknown> | null = null;
  let initializationListReads = 0;

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (url.pathname === "/api/v1/auth/me") {
      await route.fulfill({ json: authSession });
      return;
    }
    if (url.pathname === "/api/v1/setup/status") {
      await route.fulfill({
        json: {
          needsBootstrap: false,
          allowSignup: true,
          hasDefaultWorkspace: true,
          storageAvailable: true,
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/auth/csrf") {
      await route.fulfill({ json: { csrfToken: "csrf-token" } });
      return;
    }
    if (url.pathname === "/api/v1/load-nodes/ssh-host-key/scan") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      scanPayload = request.postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        json: {
          host: "load-node-smoke.internal",
          sshPort: 22,
          algorithm: "ssh-ed25519",
          publicKey: "AAAAHostKey",
          fingerprintSha256: "SHA256:testHostKey",
          knownHostsLine: "load-node-smoke.internal ssh-ed25519 AAAAHostKey",
          scannedAt: "2030-07-15T09:55:00Z",
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/load-nodes" && method === "POST") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      createPayload = request.postDataJSON() as Record<string, unknown>;
      currentNode = loadNode("uninitialized");
      await route.fulfill({ status: 201, json: currentNode });
      return;
    }
    if (
      url.pathname === `/api/v1/load-nodes/${nodeId}/initialize` &&
      method === "POST"
    ) {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      initializePayload = request.postDataJSON() as Record<string, unknown>;
      currentNode = loadNode("initializing");
      await route.fulfill({
        status: 202,
        json: {
          node: { id: nodeId, status: "initializing" },
          attempt: {
            id: attemptId,
            status: "queued",
            message: "Initialization queued.",
          },
        },
      });
      return;
    }
    if (
      url.pathname ===
        `/api/v1/load-nodes/${nodeId}/init-attempts/${attemptId}` &&
      method === "GET"
    ) {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({
        json: {
          id: attemptId,
          nodeId,
          status: "succeeded",
          startedAt: "2030-07-15T09:59:00Z",
          finishedAt: "2030-07-15T10:00:00Z",
          errorCode: null,
          message: "Initialization succeeded.",
          sanitizedLogTail: "[info] setup output sanitized",
          runnerVersion: "0.1.0",
          bundleVersion: "p0-03",
          createdAt: "2030-07-15T09:58:59Z",
          updatedAt: "2030-07-15T10:00:00Z",
        },
      });
      return;
    }
    if (
      url.pathname === `/api/v1/load-nodes/${nodeId}/init-attempts` &&
      method === "GET"
    ) {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      await route.fulfill({
        json: {
          items: [
            {
              id: attemptId,
              nodeId,
              status: "succeeded",
              startedAt: "2030-07-15T09:59:00Z",
              finishedAt: "2030-07-15T10:00:00Z",
              errorCode: null,
              message: "Initialization succeeded.",
              createdAt: "2030-07-15T09:58:59Z",
            },
          ],
          limit: 20,
          offset: 0,
          total: 1,
        },
      });
      return;
    }
    if (
      url.pathname === `/api/v1/load-nodes/${nodeId}` &&
      method === "DELETE"
    ) {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      currentNode = null;
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (url.pathname === "/api/v1/load-nodes" && method === "GET") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      let listedNode = currentNode;
      if (currentNode?.status === "initializing") {
        initializationListReads += 1;
        if (initializationListReads >= 2) {
          currentNode = loadNode("idle");
          listedNode = currentNode;
        }
      }
      await route.fulfill({
        json: {
          items: listedNode ? [listedNode] : [],
          limit: 20,
          offset: 0,
          total: listedNode ? 1 : 0,
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { code: "RESOURCE_NOT_FOUND" } });
  });

  await page.goto("/resources/load-nodes/new");
  await expect(
    page.getByRole("heading", { name: "Register Load Node" }),
  ).toBeVisible();

  await page.getByLabel("Host/IP").fill("load-node-smoke.internal");
  await page.getByRole("textbox", { name: "Password" }).fill("smoke-password");
  await page.getByRole("button", { name: "Scan key" }).click();
  await expect(page.getByText("SHA256:testHostKey")).toBeVisible();
  expect(scanPayload).toEqual({
    scope: "workspace",
    host: "load-node-smoke.internal",
    sshPort: 22,
  });
  await page.getByRole("button", { name: "Register Load Node" }).click();

  await expect(page).toHaveURL(/\/resources\/load-nodes$/);
  await expect(
    page.getByRole("table").getByText("load-node-smoke.internal"),
  ).toBeVisible();
  expect(createPayload).toMatchObject({
    host: "load-node-smoke.internal",
    sshHostKey: {
      algorithm: "ssh-ed25519",
      publicKey: "AAAAHostKey",
      fingerprintSha256: "SHA256:testHostKey",
    },
    credential: { authType: "password", password: "smoke-password" },
  });

  await page
    .getByRole("button", { name: /initialize load-node-smoke/i })
    .click();
  await expect(
    page.getByRole("heading", { name: "Initialize Load Node?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Initialize", exact: true }).click();
  await expect(page.getByRole("table").getByText("Initializing")).toBeVisible();
  await expect(page.getByRole("table").getByText("Idle")).toBeVisible();
  expect(initializationListReads).toBeGreaterThanOrEqual(2);
  expect(initializePayload).toEqual({ force: false });

  await page
    .getByRole("button", {
      name: /view initialization logs for load-node-smoke/i,
    })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Initialization log" }),
  ).toBeVisible();
  await expect(page.getByText("[info] setup output sanitized")).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: /archive load-node-smoke/i }).click();
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No Load Nodes yet" }),
  ).toBeVisible();
});
