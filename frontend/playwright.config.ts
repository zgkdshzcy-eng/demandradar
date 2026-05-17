import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for DemandRadar.
 *
 * Two run modes:
 * 1. Local — `npm run test:e2e` spins up backend (uvicorn) + frontend (next start)
 *    via webServer; the backend uses an isolated SQLite file so tests are
 *    deterministic and CI-friendly.
 * 2. CI — workflow installs both stacks, then runs the same command.
 *
 * Magic-link emails: SMTP_HOST is intentionally empty so /api/auth/request-link
 * returns the token in `debug_link`; the spec extracts it and exchanges it for
 * a session cookie.
 */
const PORT_FE = Number(process.env.E2E_PORT_FE || 3100);
const PORT_BE = Number(process.env.E2E_PORT_BE || 8100);
const FE_URL = `http://127.0.0.1:${PORT_FE}`;
const BE_URL = `http://127.0.0.1:${PORT_BE}`;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false, // shared backend state between specs
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: FE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      // Backend: isolated SQLite file, no SMTP, deterministic secret.
      command:
        process.platform === "win32"
          ? `set DATABASE_URL=sqlite+pysqlite:///./e2e_test.db&& set APP_SECRET_KEY=e2e-test-secret-key-do-not-use-in-prod&& set PUBLIC_BASE_URL=${FE_URL}&& set SMTP_HOST=&& set STRIPE_SECRET_KEY=&& set LOG_LEVEL=WARNING&& set E2E_ENABLE=1&& python -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT_BE}`
          : `DATABASE_URL=sqlite+pysqlite:///./e2e_test.db APP_SECRET_KEY=e2e-test-secret-key-do-not-use-in-prod PUBLIC_BASE_URL=${FE_URL} SMTP_HOST= STRIPE_SECRET_KEY= LOG_LEVEL=WARNING E2E_ENABLE=1 python -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT_BE}`,
      cwd: "../backend",
      url: `${BE_URL}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      // Frontend: build once then `next start`, proxying /api/* to the backend.
      command:
        process.platform === "win32"
          ? `set INTERNAL_API_URL=${BE_URL}&& set NEXT_PUBLIC_API_URL=${BE_URL}&& set NEXT_PUBLIC_SITE_URL=${FE_URL}&& npx next start -p ${PORT_FE}`
          : `INTERNAL_API_URL=${BE_URL} NEXT_PUBLIC_API_URL=${BE_URL} NEXT_PUBLIC_SITE_URL=${FE_URL} npx next start -p ${PORT_FE}`,
      cwd: ".",
      url: FE_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  ],
});
