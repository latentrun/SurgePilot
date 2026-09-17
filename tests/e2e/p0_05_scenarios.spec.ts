import { execFileSync } from "node:child_process";

import { expect, test } from "@playwright/test";

const runtimeVersion = process.env.LOAD_NODE_RUNTIME_VERSION ?? "runtime-e2e-v1";

function seedIdleLoadNode(email: string) {
  const databaseUrl = `sqlite+pysqlite:///${process.cwd()}/.tmp/p0_00_e2e.db`;
  const code = `
from datetime import UTC, datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNode
from app.models.dependency_files import DependencyFile

engine = create_engine(${JSON.stringify(databaseUrl)}, future=True)
with Session(engine) as session:
    user = session.scalar(select(User).where(User.email == ${JSON.stringify(email)}))
    if user is None:
        raise SystemExit("user not found")
    configured_runtime_version = get_settings().load_node_runtime_version
    if not configured_runtime_version:
        raise SystemExit("LOAD_NODE_RUNTIME_VERSION is required")
    now = datetime.now(UTC)
    script_file = session.get(DependencyFile, "01J0000000000000000000000S")
    if script_file is None:
        session.add(DependencyFile(
            id="01J0000000000000000000000S",
            workspace_id=DEFAULT_WORKSPACE_ID,
            filename="setup.groovy",
            content_type="text/x-groovy",
            size_bytes=42,
            sha256="1" * 64,
            storage_bucket="surgepilot",
            storage_object_key="dependency-files/e2e/setup.groovy",
            status="available",
            created_by=user.id,
            created_at=now,
            deleted_at=None,
            deleted_by=None,
        ))
    existing = session.get(LoadNode, "01J0000000000000000000000N")
    if existing is None:
        session.add(LoadNode(
            id="01J0000000000000000000000N",
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
            runtime_version=configured_runtime_version,
            last_initialized_at=now,
            last_force_kill_at=None,
            last_checked_at=now,
            last_heartbeat_at=None,
            current_run_id=None,
            last_init_attempt_id=None,
            created_by=user.id,
            updated_by=user.id,
            archived_by=None,
            created_at=now,
            updated_at=now,
            archived_at=None,
        ))
    session.commit()
`;
  execFileSync("uv", ["run", "--all-packages", "python", "-c", code], {
    cwd: "apps/api",
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl,
      LOAD_NODE_RUNTIME_VERSION: runtimeVersion,
      SSH_CREDENTIAL_ENCRYPTION_KEY:
        "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
    },
    stdio: "inherit",
  });
}

test("authenticated user saves a Scenario before starting a Debug Run", async ({
  page,
}) => {
  const email = "scenarios@example.com";
  const password = "password123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Display name").fill("Scenario User");
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /create/i }).click();

  await expect(page).toHaveURL(/\/overview$/, { timeout: 15_000 });
  seedIdleLoadNode(email);

  await page.goto("/scenarios");
  await expect(page.getByRole("heading", { name: "Scenarios", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Create Scenario" }).first().click();
  await page.getByLabel("Scenario name").fill("Checkout smoke");
  await page.getByLabel("Base URL expression").fill("https://example.test");
  await page.getByRole("button", { name: "Create", exact: true }).click();

  await expect(
    page.getByRole("heading", { name: "Checkout smoke" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add Step" }).first().click();
  await page.getByRole("textbox", { name: "Path", exact: true }).fill("/health");
  await page.getByRole("tab", { name: /Scripts/ }).click();
  await page.getByRole("button", { name: "Add Groovy before script" }).click();
  await expect(page.getByLabel("Script 1 Groovy file")).toBeVisible();
  await expect(page.getByLabel("Script 1 text")).toHaveCount(0);
  await page.getByLabel("Script 1 Groovy file").selectOption("01J0000000000000000000000S");
  await expect(page.getByText("Unsaved changes")).toBeVisible();

  await page.getByRole("button", { name: "Debug" }).click();
  await expect(page.getByRole("heading", { name: "Debug Run" })).toBeVisible();
  await expect(page.getByText("1 virtual user · 1 iteration")).toBeVisible();
  await page.getByLabel("Load Node").selectOption("01J0000000000000000000000N");
  await page.getByRole("button", { name: "Start Debug Run" }).click();

  await expect(page).toHaveURL(/\/runs\/[0-9A-HJKMNP-TV-Z]{26}$/);
  await expect(
    page.getByRole("heading", { name: "Run Report", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Verdict Summary" }),
  ).toBeVisible();
  await expect(page.getByText("Initializing", { exact: true }).first()).toBeVisible();
});
