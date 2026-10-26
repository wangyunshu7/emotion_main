import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const python = resolve(
  process.platform === "win32"
    ? "../backend/.venv/Scripts/python.exe"
    : "../backend/.venv/bin/python",
);
export default defineConfig({
  globalSetup: "./e2e/global-setup.ts",
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: { baseURL: "http://127.0.0.1:5174", trace: "retain-on-failure" },
  webServer: [
    {
      command: `"${python}" ../scripts/dev_backend.py --port 8001`,
      url: "http://127.0.0.1:8001/health/ready",
      timeout: 60000,
      reuseExistingServer: false,
      env: {
        AI_ENABLED: "true",
        AI_PROVIDER: "fake",
        ALLOWED_ORIGINS: "http://127.0.0.1:5174",
        APP_BASE_URL: "http://127.0.0.1:5174",
        DATABASE_URL:
          process.env.E2E_DATABASE_URL ||
          "postgresql+psycopg://emotion:emotion@127.0.0.1:55432/emotion_test",
      },
    },
    {
      command: "npm run dev -- --port 5174",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      env: { API_PROXY_TARGET: "http://127.0.0.1:8001" },
    },
  ],
});
