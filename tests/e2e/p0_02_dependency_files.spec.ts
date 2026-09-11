import { execFileSync } from "node:child_process";

import { expect, test } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const minioImage = "minio/minio:RELEASE.2025-04-22T22-12-26Z";
let ownedMinioContainer: string | null = null;

function minioEndpoint() {
  return process.env.MINIO_ENDPOINT ?? "http://127.0.0.1:9000";
}

function minioPort() {
  return new URL(minioEndpoint()).port || "9000";
}

function minioAccessKey() {
  return process.env.MINIO_ACCESS_KEY ?? "minioadmin";
}

function minioSecretKey() {
  return process.env.MINIO_SECRET_KEY ?? "minioadmin";
}

function minioBucket() {
  return process.env.MINIO_BUCKET ?? "surgepilot";
}

function ensureMinio() {
  const port = minioPort();
  const name = `surgepilot-p0-02-minio-${port}-${process.pid}-${Date.now()}`;
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
        `MINIO_ROOT_USER=${minioAccessKey()}`,
        "-e",
        `MINIO_ROOT_PASSWORD=${minioSecretKey()}`,
        minioImage,
        "server",
        "/data",
      ],
      { stdio: "ignore" },
    );
    ownedMinioContainer = name;
  } catch {
    // If the port is already occupied by a compatible local MinIO, reuse it.
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
client = Minio(
    parsed.netloc or parsed.path,
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=parsed.scheme == "https",
)
last_error = None
for _ in range(60):
    try:
        bucket = os.environ["MINIO_BUCKET"]
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
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
        MINIO_BUCKET: minioBucket(),
        MINIO_ACCESS_KEY: minioAccessKey(),
        MINIO_SECRET_KEY: minioSecretKey(),
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

test("authenticated user uploads downloads and deletes Dependency Files", async ({ page }) => {
  ensureMinio();
  const email = "dependency-files@example.com";
  const password = "password123";
  const tempDir = mkdtempSync(join(tmpdir(), "surgepilot-dependency-file-"));
  const textFilePath = join(tempDir, "users.html");
  const binaryFilePath = join(tempDir, "image.png");
  writeFileSync(textFilePath, "<strong>not bold</strong>\n", "utf8");
  writeFileSync(binaryFilePath, Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00]));

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Dependency Files User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await page.goto("/assets/dependency-files");
  await expect(page.getByRole("heading", { name: "Dependency Files", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Upload Dependency File" }).click();
  await page.locator('input[type="file"]').setInputFiles(textFilePath);
  await page.getByRole("button", { name: "Upload" }).click();

  await expect(page.getByText("users.html", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Preview users.html" }).click();
  const previewDialog = page.getByRole("dialog", { name: "Preview users.html" });
  await expect(previewDialog.getByText("<strong>not bold</strong>")).toBeVisible();
  await expect(previewDialog.locator("strong")).toHaveCount(0);
  await expect(previewDialog.getByText("dependency-files/")).toHaveCount(0);
  await expect(previewDialog.getByText("127.0.0.1:9000")).toHaveCount(0);
  await previewDialog.getByRole("button", { name: "Close preview" }).click();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download users.html" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("users.html");

  await page.getByRole("button", { name: "Upload Dependency File" }).click();
  await page.locator('input[type="file"]').setInputFiles(binaryFilePath);
  await page.getByRole("button", { name: "Upload" }).click();
  await expect(page.getByText("image.png", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Preview image.png" }).click();
  const binaryDialog = page.getByRole("dialog", { name: "Preview image.png" });
  await expect(
    binaryDialog.getByText("This file looks binary, so inline preview is disabled."),
  ).toBeVisible();
  await expect(binaryDialog.getByRole("button", { name: "Download image.png" })).toBeVisible();
  await binaryDialog.getByRole("button", { name: "Close preview" }).click();

  await page.getByRole("button", { name: "Delete image.png" }).click();
  await expect(page.getByText("Delete image.png?")).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();

  await page.getByRole("button", { name: "Delete users.html" }).click();
  await expect(page.getByText("Delete users.html?")).toBeVisible();
  await page.getByRole("button", { name: "Delete" }).click();

  await expect(page.getByText("users.html", { exact: true })).toBeHidden();
  await expect(page.getByText("No Dependency Files yet")).toBeVisible();
});
