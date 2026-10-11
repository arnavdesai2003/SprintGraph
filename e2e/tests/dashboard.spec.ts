import { test, expect, type Page } from '@playwright/test';

async function login(page: Page, role: 'admin' | 'developer') {
  const password = process.env.DEMO_PASSWORD;
  if (!password) throw new Error('DEMO_PASSWORD is required for browser tests');
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill(`${role}@sprintgraph.local`);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible();
  await expect(page.getByText('demo environment', { exact: true })).toBeVisible();
}

test('admin navigates all pages and inspects database-backed evidence', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await login(page, 'admin');
  await expect(page.getByText('Engineering events', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('overview.png'), fullPage: true });

  await page.getByRole('link', { name: 'Pull Requests', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Pull Requests', exact: true })).toBeVisible();
  await page.getByText('Inspect source evidence', { exact: true }).first().click();
  await expect(page.locator('details[open] pre').first()).toContainText('sprintgraph/demo');
  await expect(page.getByText('SG-101', { exact: true }).first()).toBeVisible();

  await page.getByRole('link', { name: 'Sprint Insights', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sprint Insights', exact: true })).toBeVisible();
  await expect(page.getByText('definite · explicit', { exact: true })).toBeVisible();
  await expect(page.getByText('potential · stalled', { exact: true }).first()).toBeVisible();
  await page.getByText('Inspect source evidence', { exact: true }).first().click();
  await expect(page.locator('details[open] pre').first()).toContainText('SG-102');

  await page.getByRole('link', { name: 'Task Priorities', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Task Priorities', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: /SG-102/ })).toBeVisible();
  await expect(page.getByText(/priority: \+50/).first()).toBeVisible();

  await page.getByRole('link', { name: 'Workflow Activity', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Workflow Activity', exact: true })).toBeVisible();
  await expect(page.getByText('succeeded', { exact: true }).first()).toBeVisible();

  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Integration configuration' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Audit trail' })).toBeVisible();
  await expect(page.getByText('developer@sprintgraph.local', { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});

test('PR regeneration reaches persisted success and appears in the browser', async ({ page }) => {
  await login(page, 'admin');
  await page.getByRole('link', { name: 'Pull Requests', exact: true }).click();
  // Use a distinct valid provider ID so an older seeded result cannot satisfy this assertion.
  const number = 100_000 + Math.floor(Date.now() / 1000) % 1_000_000;
  await page.getByRole('spinbutton', { name: 'PR number' }).fill(String(number));
  const submitted = page.waitForResponse(response =>
    /\/api\/projects\/\d+\/run$/.test(response.url()) && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run pull request', exact: true }).click();
  const response = await submitted;
  expect(response.status()).toBe(202);
  const { event_id } = await response.json();
  await expect(page.getByRole('status')).toContainText(`Event #${event_id} queued`);
  await expect(page.getByText(`PR #${number}:`, { exact: false }).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('link', { name: 'Workflow Activity', exact: true }).click();
  const entry = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: `#${event_id} ·` }) });
  await expect(entry.getByText('succeeded', { exact: true })).toBeVisible();
  await entry.locator('summary').first().click();
  await expect(entry.locator('pre')).toContainText(`sprintgraph/demo#${number}`);
});

test('developer is denied admin settings and backend admin APIs', async ({ page, request }) => {
  await login(page, 'developer');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await expect(page.getByText('Settings require the Admin role.', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Change role' })).toHaveCount(0);
  const token = await page.evaluate(() => sessionStorage.getItem('sprintgraph-token'));
  for (const endpoint of ['settings', 'audit']) {
    const response = await request.get(`http://localhost:8000/api/${endpoint}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(403);
  }
});

test('role changes require confirmation and sign-out clears the session', async ({ page }) => {
  await login(page, 'admin');
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  const changes: string[] = [];
  page.on('request', request => {
    if (request.method() === 'PATCH' && request.url().includes('/users/')) changes.push(request.url());
  });
  const confirmation = page.waitForEvent('dialog');
  const clicking = page.getByRole('button', { name: 'Change role', exact: true }).click();
  const dialog = await confirmation;
  expect(dialog.message()).toContain('developer@sprintgraph.local');
  await dialog.dismiss();
  await clicking;
  expect(changes).toEqual([]);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('sprintgraph-token'))).toBeNull();
});
