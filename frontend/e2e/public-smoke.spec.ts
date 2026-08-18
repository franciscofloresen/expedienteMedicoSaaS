import { test, expect } from '@playwright/test';

// Runs with no backend and no real auth: asserts the app boots and serves its
// public marketing shell. This is the CI-safe E2E floor; the auth-gated clinical
// flows live in clinical-flows.spec.ts (see e2e/README.md).
test.describe('public smoke', () => {
  test('landing page boots and renders the marketing shell', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/CloudMedRecord/);
    await expect(page.getByText(/Expediente clínico legal-first/i)).toBeVisible();
    await expect(page.getByText('CloudMedRecord').first()).toBeVisible();
  });

  test('the SPA mounts (root is not empty)', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#root')).not.toBeEmpty();
  });

  test('privacy page is reachable as a public route', async ({ page }) => {
    await page.goto('/privacidad');
    await expect(page.locator('#root')).not.toBeEmpty();
  });
});
