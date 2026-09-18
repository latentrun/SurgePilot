import { execFileSync } from "node:child_process";

import { expect, test } from "@playwright/test";

const runId = "01HZX3Y9M0E9W7Z6M5QK9S8P7R";
const artifactId = "01HZX3Y9M0E9W7Z6M5QK9S8P7T";
const bodyBlobArtifactId = "01HZX3Y9M0E9W7Z6M5QK9S8P7B";
const minioImage = "quay.io/minio/minio:RELEASE.2025-04-22T22-12-26Z";
let ownedMinioContainer: string | null = null;

function databaseUrl() {
  return `sqlite+pysqlite:///${process.cwd()}/.tmp/p0_00_e2e.db`;
}

function minioEndpoint() {
  return process.env.MINIO_ENDPOINT ?? "http://127.0.0.1:9000";
}

function minioPort() {
  return new URL(minioEndpoint()).port || "9000";
}

function runPython(code: string) {
  execFileSync("uv", ["run", "--all-packages", "python", "-c", code], {
    cwd: "apps/api",
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl(),
      MINIO_ENDPOINT: minioEndpoint(),
      MINIO_BUCKET: "surgepilot",
      MINIO_ACCESS_KEY: "minioadmin",
      MINIO_SECRET_KEY: "minioadmin",
      SSH_CREDENTIAL_ENCRYPTION_KEY:
        "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
    },
    stdio: "inherit",
  });
}

function ensureMinio() {
  const port = minioPort();
  const name = `surgepilot-p1-08-minio-${port}-${process.pid}-${Date.now()}`;
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
    // If the port is already occupied by a compatible local MinIO, reuse it.
  }
  runPython(`
import os
import time
from urllib.parse import urlparse
from minio import Minio
endpoint = os.environ["MINIO_ENDPOINT"]
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
`);
}

function seedDebugTraceRun(email: string) {
  const tracePayload = [
    {
      schemaVersion: 1,
      sequence: 1,
      label: "Login request api_key=label-secret",
      method: "POST",
      url: "https://user:pass@api.example.test/login?api_key=query-secret&safe=ok",
      requestHeaders: {
        Authorization: "Bearer secret-token",
        "X-Trace": "safe",
      },
      requestBody: {
        contentType: "application/json",
        text: '{"username":"alice","password":"open-sesame"}',
      },
      responseStatus: 401,
      responseHeaders: {
        "Set-Cookie": "session=secret",
        "Content-Type": "application/json",
      },
      responseBody: {
        contentType: "application/json",
        text: '{"error":"unauthorized"}',
      },
      durationMs: 123,
      error: "Unauthorized password=open-sesame token=label-secret",
    },
    {
      schemaVersion: 1,
      sequence: 2,
      label: "Large HTML response",
      method: "GET",
      url: "https://api.example.test/large-html",
      requestHeaders: {},
      requestBody: { contentType: "text/plain", text: "" },
      responseStatus: 200,
      responseHeaders: { "Content-Type": "text/html" },
      responseBody: {
        contentType: "text/html",
        bodyStorage: "sidecar",
        text: "<html>large preview</html>",
        inlinePreview: "<html>large preview</html>",
        bodyTruncated: true,
        sizeBytes: 3145728,
        sha256Prefix: "bbbbbbbbbbbbbbbb",
        downloadRelativePath: "artifacts/debug-http-body-blobs/2-response.bin",
      },
      durationMs: 456,
      error: null,
    },
  ]
    .map((row) => JSON.stringify(row))
    .join("\n");
  runPython(`
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from urllib.parse import urlparse
from minio import Minio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunArtifact, RunSnapshot

engine = create_engine(${JSON.stringify(databaseUrl())}, future=True)
now = datetime.now(UTC)
email = ${JSON.stringify(email)}
run_id = ${JSON.stringify(runId)}
artifact_id = ${JSON.stringify(artifactId)}
body_blob_artifact_id = ${JSON.stringify(bodyBlobArtifactId)}
node_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7N"
scenario_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7S"
trace = (${JSON.stringify(tracePayload)} + "\\n").encode()
body_blob = b"<html>large raw body</html>"
sha = hashlib.sha256(trace).hexdigest()
body_blob_sha = hashlib.sha256(body_blob).hexdigest()
object_key = f"run-artifacts/{DEFAULT_WORKSPACE_ID}/{run_id}/artifacts/debug-http-trace.jsonl"
body_blob_object_key = f"run-artifacts/{DEFAULT_WORKSPACE_ID}/{run_id}/artifacts/debug-http-body-blobs/2-response.bin"

with Session(engine) as session:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        raise SystemExit("user not found")
    if session.get(LoadNode, node_id) is None:
        session.add(LoadNode(
            id=node_id,
            scope="workspace",
            workspace_id=DEFAULT_WORKSPACE_ID,
            host="debug-node.internal",
            ssh_port=22,
            ssh_user="surgepilot",
            runner_home="/opt/surgepilot/runner",
            auth_type="password",
            maintainer=None,
            remark=None,
            status="idle",
            last_status_reason=None,
            runner_version=None,
            bundle_version=None,
            last_initialized_at=now,
            last_force_kill_at=None,
            last_checked_at=now,
            last_heartbeat_at=now,
            current_run_id=None,
            last_init_attempt_id=None,
            created_by=user.id,
            updated_by=user.id,
            archived_by=None,
            created_at=now,
            updated_at=now,
            archived_at=None,
        ))
    session.merge(Run(
        id=run_id,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="debug",
        state="finished",
        source_type="debug_scenario",
        source_id=scenario_id,
        selected_node_id=node_id,
        triggered_by_user_id=user.id,
        accepted_at=now - timedelta(seconds=3),
        started_at=now - timedelta(seconds=2),
        ended_at=now - timedelta(seconds=1),
        last_heartbeat_at=now - timedelta(seconds=1),
        failure_reason="assertion_failed",
        failure_message="Debug request returned unauthorized.",
        forced_convergence=False,
        validity="invalid",
        sla_result="not_evaluated",
        sla_result_reason=None,
        runner_pid=None,
        stop_requested_at=None,
        stop_requested_by_user_id=None,
        last_callback_event_id=None,
        created_at=now - timedelta(seconds=4),
        updated_at=now,
    ))
    session.merge(RunSnapshot(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_id=run_id,
        snapshot_version=1,
        snapshot_hash="c" * 64,
        snapshot_json={
            "schemaVersion": 1,
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": scenario_id,
            "sourceRevision": 1,
            "validityDefault": "invalid",
            "scenario": {
                "id": scenario_id,
                "name": "Debug checkout scenario",
                "scenarioType": "visual",
                "baseUrlExpression": "https://api.example.test",
                "defaultSettings": {},
                "dataSources": [],
                "steps": [],
            },
            "envGroup": {"id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E", "name": "Staging", "variables": {"API_TOKEN": "secret-token"}},
            "dependencyFiles": [],
        },
        created_at=now - timedelta(seconds=4),
    ))
    session.merge(RunArtifact(
        id=artifact_id,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_id=run_id,
        node_id=node_id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        artifact_type="debug_http_trace",
        relative_path="artifacts/debug-http-trace.jsonl",
        display_filename="debug-http-trace.jsonl",
        size_bytes=len(trace),
        sha256=sha,
        content_type="application/jsonl",
        storage_key=object_key,
        status="available",
        terminal_late=False,
        created_at=now - timedelta(seconds=1),
    ))
    session.merge(RunArtifact(
        id=body_blob_artifact_id,
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_id=run_id,
        node_id=node_id,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        artifact_type="debug_http_body_blob",
        relative_path="artifacts/debug-http-body-blobs/2-response.bin",
        display_filename="2-response.bin",
        size_bytes=len(body_blob),
        sha256=body_blob_sha,
        content_type="text/html",
        storage_key=body_blob_object_key,
        status="available",
        terminal_late=False,
        created_at=now - timedelta(seconds=1),
    ))
    session.commit()

endpoint = os.environ["MINIO_ENDPOINT"]
parsed = urlparse(endpoint)
client = Minio(parsed.netloc or parsed.path, access_key="minioadmin", secret_key="minioadmin", secure=parsed.scheme == "https")
from io import BytesIO
client.put_object("surgepilot", object_key, BytesIO(trace), length=len(trace), content_type="application/jsonl")
client.put_object("surgepilot", body_blob_object_key, BytesIO(body_blob), length=len(body_blob), content_type="text/html")
`);
}

test.afterAll(() => {
  if (!ownedMinioContainer) return;
  try {
    execFileSync("docker", ["rm", "-f", ownedMinioContainer], {
      stdio: "ignore",
    });
  } catch {
    // Best-effort cleanup only.
  }
});

test("Debug Run report displays sanitized HTTP trace details from a seeded artifact", async ({
  page,
}) => {
  const email = "trace-e2e@example.com";
  const password = "password123";

  ensureMinio();

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Trace E2E");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/overview$/);

  seedDebugTraceRun(email);

  await page.goto(`/runs/${runId}`);

  await expect(page.getByRole("heading", { name: "HTTP Trace" })).toBeVisible();
  await expect(page.getByText("POST")).toBeVisible();
  await expect(
    page.getByText(
      "https://[REDACTED]@api.example.test/login?api_key=%5BREDACTED%5D&safe=ok",
    ),
  ).toBeVisible();
  await expect(page.getByText("401")).toBeVisible();
  await page
    .getByRole("button", { name: /show trace details/i })
    .first()
    .click();
  await expect(page.getByText("Authorization: [REDACTED]")).toBeVisible();
  await expect(page.getByText("Set-Cookie: [REDACTED]")).toBeVisible();
  await expect(page.getByText('{"error":"unauthorized"}')).toBeVisible();
  await page.getByRole("button", { name: /hide trace details/i }).click();
  await page
    .getByRole("button", { name: /show trace details/i })
    .nth(1)
    .click();
  await expect(page.getByText("<html>large preview</html>")).toBeVisible();
  await expect(
    page.getByText(
      /Large sanitized body stored as an internal sidecar artifact/i,
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /download sanitized body/i }),
  ).toBeVisible();
  await expect(
    page.getByText(
      /secret-token|open-sesame|query-secret|label-secret|user:pass|run-artifacts/i,
    ),
  ).toHaveCount(0);
});
