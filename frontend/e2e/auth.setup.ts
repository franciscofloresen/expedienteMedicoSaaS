import { test as setup } from '@playwright/test';

/**
 * Clerk auth bootstrap for the auth-gated clinical flows (Fase 11).
 *
 * This file is intentionally NOT wired into playwright.config.ts yet — it needs
 * a Clerk TEST instance, which is an external setup step (like the Fase 9 Clerk
 * gate). To turn on the auth-gated E2E:
 *
 *  1. Create a Clerk development/test instance and a seeded user + tenant.
 *  2. Provide these to CI as secrets / env:
 *       VITE_CLERK_PUBLISHABLE_KEY  (test instance)
 *       CLERK_SECRET_KEY            (test instance, for @clerk/testing)
 *       E2E_USER_EMAIL / E2E_USER_PASSWORD  (or a Clerk testing token)
 *  3. `npm i -D @clerk/testing`, then implement the body below using
 *     `clerkSetup()` + `setupClerkTestingToken(page)` to bypass the UI/MFA, sign
 *     in the seeded user, and persist storageState.
 *  4. Add a `setup` project to playwright.config.ts that runs this file and set
 *     `storageState: 'e2e/.auth/user.json'` on the chromium project, then remove
 *     `.fixme` from clinical-flows.spec.ts.
 *
 * Keeping the stub here documents the exact remaining wiring in one place.
 */
setup.skip('authenticate (stub — needs a Clerk test instance)', async () => {
  // const { clerkSetup } = await import('@clerk/testing/playwright');
  // await clerkSetup();
  // ...sign in the seeded user, then: await page.context().storageState({ path: authFile });
});
