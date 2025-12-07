// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = 'https://atlas-crm.alexandratechlab.com';

test('Debug login flow', async ({ page }) => {
  // Navigate to login
  await page.goto(`${BASE_URL}/users/login/`);

  // Take screenshot before login
  await page.screenshot({ path: 'tests/screenshots/before_login.png' });

  // Fill form
  await page.fill('input[name="email"]', 'superadmin@atlas.com');
  await page.fill('input[name="password"]', 'Atlas@2024!');

  // Take screenshot after filling
  await page.screenshot({ path: 'tests/screenshots/after_fill.png' });

  // Click submit
  await page.click('button[type="submit"]');

  // Wait a bit for response
  await page.waitForTimeout(3000);

  // Take screenshot after submit
  await page.screenshot({ path: 'tests/screenshots/after_submit.png' });

  // Log the current URL and page title
  console.log('Current URL:', page.url());
  console.log('Page title:', await page.title());

  // Check if there are any error messages
  const errorMessages = await page.locator('.bg-red-100, .text-red-500, .alert-danger, .error').allTextContents();
  console.log('Error messages:', errorMessages);

  // Check messages area
  const messages = await page.locator('#messages, .messages').allTextContents();
  console.log('Messages:', messages);
});
