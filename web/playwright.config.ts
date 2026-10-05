import { defineConfig, devices } from "@playwright/test";

const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "../tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m uvicorn service.main:app --port 8000`,
      cwd: "..",
      url: "http://localhost:8000/healthz",
      env: { GATEWAY_ENGINE: "fake", CORS_ORIGINS: "http://localhost:5173" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173/field",
      env: { VITE_API_BASE: "http://localhost:8000" },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
