// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://atlas-crm.alexandratechlab.com';

// Test credentials - using superadmin account
const TEST_USER = {
  email: 'superadmin@atlas.com',
  password: 'Atlas@2024!'
};

// Helper function to login
async function login(page) {
  await page.goto(`${BASE_URL}/users/login/`);
  await page.fill('input[name="email"]', TEST_USER.email);
  await page.fill('input[name="password"]', TEST_USER.password);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE_URL}/dashboard/**`, { timeout: 15000 });
}

test.describe('Finance Module - New UI Pages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('COD Management page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/finance/cod/`);
    await expect(page.locator('h1')).toContainText('COD Management');
    await expect(page.locator('text=Total COD')).toBeVisible();
    await expect(page.locator('text=Pending Collection')).toBeVisible();
    await expect(page.locator('text=Collected')).toBeVisible();
  });

  test('Seller Payouts page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/finance/seller-payouts/`);
    await expect(page.locator('h1')).toContainText('Seller Payouts');
  });

  test('Refunds Management page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/finance/refunds/`);
    await expect(page.locator('h1')).toContainText('Refunds');
  });

  test('Reconciliation page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/finance/reconciliation/`);
    await expect(page.locator('h1')).toContainText('Reconciliation');
  });
});

test.describe('Inventory Module - New UI Pages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('Stock Alerts page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/inventory/alerts/`);
    await expect(page.locator('h1')).toContainText('Stock Alerts');
    await expect(page.locator('text=Critical Alerts')).toBeVisible();
  });

  test('Stock Reservations page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/inventory/reservations/`);
    await expect(page.locator('h1')).toContainText('Stock Reservations');
  });
});

test.describe('Users Module - New UI Pages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('Roles Management page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/users/roles/`);
    await expect(page.locator('h1')).toContainText('Roles Management');
    await expect(page.locator('text=Total Roles')).toBeVisible();
    await expect(page.locator('text=Create Role')).toBeVisible();
  });

  test('User Settings page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/users/settings/`);
    await expect(page.locator('h1')).toContainText('User Settings');
  });

  test('Notification Settings page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/users/settings/notifications/`);
    await expect(page.locator('h1')).toContainText('Notification Settings');
    await expect(page.locator('text=Order Notifications')).toBeVisible();
    await expect(page.locator('text=Inventory Notifications')).toBeVisible();
  });

  test('Two-Factor Authentication page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/users/settings/two-factor/`);
    await expect(page.locator('h1')).toContainText('Two-Factor Authentication');
  });
});

test.describe('Callcenter Module - New UI Pages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('Callbacks Schedule page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/callcenter/callbacks/`);
    await expect(page.locator('h1')).toContainText('Callbacks Schedule');
    await expect(page.locator('text=Total Callbacks')).toBeVisible();
    await expect(page.locator('text=Pending')).toBeVisible();
  });

  test('Agents List page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/callcenter/agents/`);
    await expect(page.locator('h1')).toContainText('Call Center Agents');
    await expect(page.locator('text=Total Agents')).toBeVisible();
    await expect(page.locator('text=Active Agents')).toBeVisible();
  });
});

test.describe('Delivery Module - New UI Pages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('Couriers List page loads correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/delivery/couriers/`);
    await expect(page.locator('h1')).toContainText('Delivery Couriers');
    await expect(page.locator('text=Total Couriers')).toBeVisible();
    await expect(page.locator('text=Active Couriers')).toBeVisible();
  });
});

test.describe('Navigation and Links', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('Dashboard links to new Finance pages work', async ({ page }) => {
    await page.goto(`${BASE_URL}/finance/dashboard/`);

    // Check COD link exists
    const codLink = page.locator('a[href*="/finance/cod/"]');
    if (await codLink.count() > 0) {
      await codLink.first().click();
      await expect(page.locator('h1')).toContainText('COD Management');
    }
  });

  test('Settings navigation works correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/users/settings/`);

    // Navigate to Notifications
    await page.click('a:has-text("Notifications")');
    await expect(page.locator('h1')).toContainText('Notification Settings');

    // Navigate to Security
    await page.click('a:has-text("Security")');
    await expect(page.locator('h1')).toContainText('Two-Factor Authentication');
  });
});
