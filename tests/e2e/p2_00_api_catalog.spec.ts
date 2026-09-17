import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

const minioImage = "minio/minio:RELEASE.2025-04-22T22-12-26Z";
let ownedMinioContainer: string | null = null;

function minioEndpoint() {
  return process.env.MINIO_ENDPOINT ?? "http://127.0.0.1:9000";
}

function minioPort() {
  return new URL(minioEndpoint()).port || "9000";
}

function ensureMinio() {
  const port = minioPort();
  const name = `surgepilot-p2-00-minio-${port}-${process.pid}-${Date.now()}`;
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
    execFileSync("docker", ["rm", "-f", ownedMinioContainer], { stdio: "ignore" });
  }
});

test("authenticated user manages API Catalog docs without request sending", async ({ page }) => {
  ensureMinio();
  const email = "api-catalog-e2e@example.com";
  const password = "password123";
  const tempDir = mkdtempSync(join(tmpdir(), "surgepilot-api-catalog-"));
  const specPath = join(tempDir, "orders-openapi.yaml");
  writeFileSync(
    specPath,
    `openapi: 3.1.0
info:
  title: Orders API
  version: 1.0.0
servers:
  - url: https://api.example.invalid
paths:
  /orders:
    get:
      summary: List orders
      responses:
        '200':
          description: OK
`,
    "utf8",
  );

  let outboundTargetRequest = false;
  await page.route("https://api.example.invalid/**", async (route) => {
    outboundTargetRequest = true;
    await route.abort();
  });

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("API Catalog User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  await page.goto("/api-catalog");
  await expect(page.getByRole("heading", { name: "API Catalog" })).toBeVisible();
  await expect(page.getByRole("link", { name: "API Catalog" })).toHaveAttribute("aria-current", "page");

  await page.getByRole("button", { name: "Upload API Spec" }).click();
  const uploadDialog = page.getByRole("dialog", { name: "Upload API Spec" });
  await uploadDialog.getByLabel("API spec file").setInputFiles(specPath);
  await uploadDialog.getByRole("button", { name: "Upload", exact: true }).click();

  await expect(page.getByText("Orders API", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "SHA-256" })).toBeVisible();
  await expect(page.getByRole("link", { name: "View Orders API" })).toBeVisible();
  await page.getByRole("link", { name: "View Orders API" }).click();
  await expect(page.getByLabel("API Reference")).toBeVisible();
  await expect(page.getByText("Documentation only")).toHaveCount(0);
  const main = page.getByRole("main");
  await expect(main.getByText(/No request sending, API client, Agent, MCP/)).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => document.body.classList.contains("light-mode"))).toBe(false);
  await expect(main.getByText(/api-catalog-specs|9000|minio/i)).toHaveCount(0);
  await expect(main.getByText(/Test Request|Try it/i)).toHaveCount(0);
  expect(outboundTargetRequest).toBe(false);

  const operationSection = page.getByRole("region", { name: "List orders" });
  await expect(operationSection).toBeVisible();
  const operationId = await operationSection.getAttribute("id");
  expect(operationId).toBeTruthy();
  const detailUrl = new URL(page.url());
  detailUrl.hash = (operationId ?? "").replace(/^api-1\//, "");

  await page.goto(detailUrl.toString());
  await expect(page.getByLabel("API Reference")).toBeVisible();
  await expect(operationSection).toBeVisible();
  await page.waitForTimeout(100);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);

  await page.getByRole("button", { name: /List orders HTTP Method: GET/ }).click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);

  const bottomScrollY = await page.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
    return window.scrollY;
  });
  expect(bottomScrollY).toBeGreaterThan(0);
  await page.evaluate((hash) => {
    window.history.replaceState({}, "", `${window.location.pathname}${hash}`);
  }, detailUrl.hash);
  await page.waitForTimeout(100);
  expect(await page.evaluate(() => window.scrollY)).toBe(bottomScrollY);

  await page.mouse.wheel(0, -400);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(bottomScrollY);

  await page.goto("/api-catalog");
  await page.getByRole("button", { name: "Delete Orders API" }).click();
  const deleteDialog = page.getByRole("dialog", { name: "Delete Orders API?" });
  await expect(deleteDialog).toBeVisible();
  await deleteDialog.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(page.getByText("Orders API", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "View Orders API" })).toHaveCount(0);
});
