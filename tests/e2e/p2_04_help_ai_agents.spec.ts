import { execFileSync } from "node:child_process";
import { open } from "node:fs/promises";

import { expect, test } from "@playwright/test";


const minioImage = "quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z";
let ownedMinioContainer: string | null = null;

function minioEndpoint() {
  return process.env.MINIO_ENDPOINT ?? "http://127.0.0.1:9000";
}

function ensureMinio() {
  const port = new URL(minioEndpoint()).port || "9000";
  const name = `surgepilot-p2-04-minio-${port}-${process.pid}-${Date.now()}`;
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

test("authenticated user follows AI Agents guidance and downloads the official skill", async ({
  page,
}) => {
  ensureMinio();
  const email = `help-ai-agents-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Help AI Agents User");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  await page.getByRole("link", { name: "Help" }).click();
  await expect(page).toHaveURL(/\/help$/);
  await expect(page.getByRole("heading", { name: "Help" })).toBeVisible();

  const tabs = page.getByRole("tablist", { name: "Help topics" }).getByRole("tab");
  await expect(tabs).toHaveText([
    "Getting Started",
    "AI Agents",
    "Scripting",
    "API Catalog",
    "Troubleshooting",
    "Limits & Activation",
  ]);
  await expect(page.getByRole("tab", { name: "Automation" })).toHaveCount(0);

  await page.getByRole("tab", { name: "AI Agents" }).click();
  await expect(page.getByText("Use a user-owned local agent")).toBeVisible();
  await expect(page.getByText(/explicit Workspace ID/i)).toBeVisible();
  await expect(page.getByText(/operationId allowlist/i)).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download official AI skill" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("surgepilot-public-api-skill.zip");
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const file = await open(downloadPath as string, "r");
  try {
    const signature = Buffer.alloc(4);
    await file.read(signature, 0, signature.length, 0);
    expect([...signature]).toEqual([0x50, 0x4b, 0x03, 0x04]);
  } finally {
    await file.close();
  }

  await page.getByRole("tab", { name: "Limits & Activation" }).click();
  await expect(page.getByText("System bootstrap is active")).toBeVisible();
  await expect(
    page.getByText(/does not automatically ingest user-provided URLs/i),
  ).toBeVisible();
});
