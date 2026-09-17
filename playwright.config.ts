import { defineConfig, devices } from "@playwright/test";

const apiPort = process.env.SURGEPILOT_E2E_API_PORT ?? "8000";
const webPort = process.env.SURGEPILOT_E2E_WEB_PORT ?? "5173";
const runtimeVersion = process.env.LOAD_NODE_RUNTIME_VERSION ?? "runtime-e2e-v1";
const apiBaseUrl = `http://127.0.0.1:${apiPort}`;
const webBaseUrl = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  workers: 1,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: webBaseUrl,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chrome",
      use: {
        ...devices["Desktop Chrome"],
        channel: "chrome",
      },
    },
  ],
  webServer: [
    {
      command:
        `mkdir -p .tmp && rm -f .tmp/p0_00_e2e.db && db_url="sqlite+pysqlite:///$PWD/.tmp/p0_00_e2e.db" && DATABASE_URL="$db_url" LOAD_NODE_RUNTIME_VERSION="${runtimeVersion}" SSH_CREDENTIAL_ENCRYPTION_KEY="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=" PYTHONPATH=apps/api uv run --all-packages python scripts/setup_e2e_db.py && cd apps/api && DATABASE_URL="$db_url" LOAD_NODE_RUNTIME_VERSION="${runtimeVersion}" SSH_CREDENTIAL_ENCRYPTION_KEY="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=" uv run fastapi dev app/main.py --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiBaseUrl}/api/healthz`,
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command:
        `pnpm --filter @surgepilot/web dev -- --host 127.0.0.1 --port ${webPort}`,
      url: webBaseUrl,
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
