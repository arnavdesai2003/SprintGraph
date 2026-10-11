import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  outputDir: '/artifacts/test-results',
  reporter: [['list'], ['html', { outputFolder: '/artifacts/playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://localhost:3000',
    ...devices['Desktop Chrome'],
    // Traces can capture authentication request bodies. Keep them disabled.
    trace: 'off',
    video: 'off',
    screenshot: 'only-on-failure',
  },
});
