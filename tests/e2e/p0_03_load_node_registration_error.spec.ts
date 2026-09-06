import { expect, test } from "@playwright/test";

const authSession = {
  user: {
    id: "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
    email: "admin@example.com",
    displayName: "Admin User",
    role: "admin",
    status: "active",
  },
  defaultWorkspace: {
    id: "01HZW000000000000000000000",
    name: "Default Workspace",
  },
  csrfToken: "csrf-token",
};

const workspaceId = authSession.defaultWorkspace.id;

test("shows actionable guidance when Load Node credential encryption is unavailable", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

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
      await route.fulfill({
        json: {
          host: "load-node-error.internal",
          sshPort: 22,
          algorithm: "ssh-ed25519",
          publicKey: "AAAAHostKey",
          fingerprintSha256: "SHA256:testHostKey",
          knownHostsLine: "load-node-error.internal ssh-ed25519 AAAAHostKey",
          scannedAt: "2030-07-15T00:00:00Z",
        },
      });
      return;
    }
    if (url.pathname === "/api/v1/load-nodes" && request.method() === "POST") {
      expect(request.headers()["x-workspace-id"]).toBe(workspaceId);
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
      await route.fulfill({
        status: 500,
        json: {
          code: "CREDENTIAL_DECRYPT_FAILED",
          message: "Credential encryption is not configured.",
          requestId: "req-load-node-encryption",
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

  await page.getByLabel("Host/IP").fill("load-node-error.internal");
  await page.getByRole("textbox", { name: "Password" }).fill("ssh-password");
  await page.getByRole("button", { name: "Scan key" }).click();
  await expect(page.getByText("SHA256:testHostKey")).toBeVisible();
  await page.getByRole("button", { name: "Register Load Node" }).click();

  await expect(
    page.getByText(
      "Load Node credential encryption is unavailable. Ask an administrator to verify SSH_CREDENTIAL_ENCRYPTION_KEY and the stored credential data, then restart SurgePilot.",
    ),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/resources\/load-nodes\/new$/);
});
