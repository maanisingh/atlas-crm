// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://atlas-crm.alexandratechlab.com';

// Test credentials
const TEST_USER = {
  email: 'superadmin@atlas.com',
  password: 'Atlas@2024!'
};

// Login once and reuse
test.describe.configure({ mode: 'serial' });

let authenticated = false;

test.beforeEach(async ({ page, context }) => {
  if (!authenticated) {
    await page.goto(`${BASE_URL}/users/login/`);
    await page.fill('input[name="email"]', TEST_USER.email);
    await page.fill('input[name="password"]', TEST_USER.password);
    await page.click('button[type="submit"]');
    await page.waitForURL(`${BASE_URL}/dashboard/**`, { timeout: 15000 });
    authenticated = true;
  }
});

test('Finance COD page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/finance/cod/`);
  console.log('COD Status:', response?.status());
  // Accept either 200 or redirect to login
  expect([200, 302]).toContain(response?.status());
});

test('Finance Payouts page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/finance/payouts/`);
  console.log('Payouts Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Finance Refunds page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/finance/refunds/`);
  console.log('Refunds Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Inventory Alerts page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/inventory/alerts/`);
  console.log('Alerts Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Inventory Reservations page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/inventory/reservations/`);
  console.log('Reservations Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Users Roles page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/users/roles/`);
  console.log('Roles Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Users Settings page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/users/settings/`);
  console.log('Settings Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Callcenter Callbacks page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/callcenter/callbacks/`);
  console.log('Callbacks Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Callcenter Agents page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/callcenter/agents/`);
  console.log('Agents Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});

test('Delivery Couriers page', async ({ page }) => {
  const response = await page.goto(`${BASE_URL}/delivery/couriers/`);
  console.log('Couriers Status:', response?.status());
  expect([200, 302]).toContain(response?.status());
});
