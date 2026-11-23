import { defineConfig } from '@playwright/test';

const port = Number(process.env.E2E_PORT || 4318);

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  workers: 2,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: `npm run preview -- --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  },
});
