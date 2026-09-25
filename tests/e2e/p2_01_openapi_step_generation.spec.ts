import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

const minioImage =
  "mexiaow/minio@" +
  "sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e";
let ownedMinioContainer: string | null = null;

function minioEndpoint() {
  return process.env.MINIO_ENDPOINT ?? "http://127.0.0.1:9000";
}

function minioPort() {
  return new URL(minioEndpoint()).port || "9000";
}

function ensureMinio() {
  const port = minioPort();
  const name = `surgepilot-p2-01-minio-${port}-${process.pid}-${Date.now()}`;
  try {
    execFileSync(
      "docker",
      [
        "run",
        "-d",
        "--name",
        name,
        "-p",
        `${port}:9000`,
        "-e",
        "MINIO_ROOT_USER=minioadmin",
        "-e",
        "MINIO_ROOT_PASSWORD=minioadmin",
        minioImage,
        "server",
        "/data",
      ],
      { stdio: "ignore" },
    );
    ownedMinioContainer = name;
  } catch {
    // Reuse a compatible local MinIO when the port is already occupied.
  }
  execFileSync(
    "uv",
    [
      "run",
      "--all-packages",
      "python",
      "-c",
      `
import os
import time
from urllib.parse import urlparse
from minio import Minio
endpoint = os.environ.get("MINIO_ENDPOINT", "http://127.0.0.1:9000")
parsed = urlparse(endpoint)
client = Minio(parsed.netloc or parsed.path, access_key="minioadmin", secret_key="minioadmin", secure=parsed.scheme == "https")
last_error = None
for _ in range(60):
    try:
        if not client.bucket_exists("surgepilot"):
            client.make_bucket("surgepilot")
        break
    except Exception as exc:
        last_error = exc
        time.sleep(0.5)
else:
    raise SystemExit(f"MinIO unavailable: {last_error}")
`,
    ],
    {
      cwd: "apps/api",
      env: {
        ...process.env,
        MINIO_ENDPOINT: minioEndpoint(),
        MINIO_BUCKET: "surgepilot",
        MINIO_ACCESS_KEY: "minioadmin",
        MINIO_SECRET_KEY: "minioadmin",
      },
      stdio: "inherit",
    },
  );
}

test.afterAll(() => {
  if (ownedMinioContainer) {
    execFileSync("docker", ["rm", "-f", ownedMinioContainer], {
      stdio: "ignore",
    });
  }
});

test("authenticated user generates Scenario Step drafts from OpenAPI operations", async ({
  page,
}) => {
  ensureMinio();
  const email = "openapi-step-generation-e2e@example.com";
  const password = "password123";
  const tempDir = mkdtempSync(join(tmpdir(), "surgepilot-openapi-step-"));
  const specPath = join(tempDir, "orders-openapi.yaml");
  writeFileSync(
    specPath,
    `openapi: 3.1.0
info:
  title: Orders API
  version: 1.0.0
paths:
  /orders/{orderId}:
    get:
      operationId: getOrder
      summary: Get one order
      parameters:
        - name: orderId
          in: path
          required: true
          schema:
            type: string
        - name: include
          in: query
          required: false
          schema:
            type: string
            default: items
      responses:
        '200':
          description: OK
  /orders:
    post:
      operationId: createOrder
      summary: Create order
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [sku]
              properties:
                sku:
                  type: string
                  example: SKU-1
      responses:
        '201':
          description: Created
`,
    "utf8",
  );

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("OpenAPI Step User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  await page.goto("/api-catalog");
  await page.getByRole("button", { name: "Upload API Spec" }).click();
  const uploadDialog = page.getByRole("dialog", { name: "Upload API Spec" });
  await uploadDialog.getByLabel("API spec file").setInputFiles(specPath);
  await uploadDialog
    .getByRole("button", { name: "Upload", exact: true })
    .click();
  await expect(
    page.getByText("Orders API", { exact: true }).first(),
  ).toBeVisible();

  await page.goto("/scenarios");
  await page.getByRole("button", { name: "Create Scenario" }).first().click();
  await page.getByLabel("Scenario name").fill("OpenAPI generation smoke");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "OpenAPI generation smoke" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "From OpenAPI" }).click();
  const importDialog = page.getByRole("dialog", {
    name: "Generate from OpenAPI",
  });
  await importDialog.getByLabel("API Catalog spec").selectOption({ index: 1 });
  await importDialog
    .locator("label")
    .filter({ hasText: "Get one order" })
    .locator('input[type="checkbox"]')
    .check();
  await importDialog
    .locator("label")
    .filter({ hasText: "Create order" })
    .locator('input[type="checkbox"]')
    .check();
  await importDialog
    .getByRole("button", { name: "Preview Step drafts" })
    .click();

  await expect(importDialog.getByText("2. POST /orders")).toBeVisible();
  await expect(
    importDialog.getByText(/GET \/orders\/\$\{orderId\}/),
  ).toBeVisible();
  await expect(
    importDialog.getByText("Fill orderId before running this Step."),
  ).toBeVisible();
  await importDialog
    .getByRole("button", { name: "Insert Step drafts" })
    .click();

  await expect(page.getByText("Unsaved changes")).toBeVisible();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  await expect(page.getByText("Create order").first()).toBeVisible();
  await expect(page.getByText("/orders/${orderId}").first()).toBeVisible();
});
