import { defineConfig } from "@playwright/test";

export default defineConfig({
  webServer:
    process.env.SIPI_START_TEST_SERVER === "1"
      ? {
          command: "npm run start -- --hostname 127.0.0.1",
          url: "http://127.0.0.1:3000/login",
          reuseExistingServer: !process.env.CI,
          timeout: 120000,
        }
      : undefined,
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  maxFailures: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  reporter: "list",
});
