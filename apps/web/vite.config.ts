import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const nodeEnv =
  (globalThis as unknown as {
    process?: { env?: Record<string, string | undefined> };
  }).process?.env ?? {};
const devPort = Number(nodeEnv.SURGEPILOT_E2E_WEB_PORT ?? "5173");
const apiPort = nodeEnv.SURGEPILOT_E2E_API_PORT ?? "8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: devPort,
    proxy: {
      "/api/": `http://localhost:${apiPort}`,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
  },
});
