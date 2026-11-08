import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.js",
  timeout: 45000,
  workers: 2,
  use: {
    baseURL: process.env.PORTAL_TEST_URL || "http://127.0.0.1:4320",
    channel: "chrome",
    viewport: { width: 1440, height: 1000 },
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "../../plan/portal-browser-results.json" }],
  ],
});
