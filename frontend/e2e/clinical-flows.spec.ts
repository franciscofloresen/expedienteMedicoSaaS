import { test, expect } from '@playwright/test';

/**
 * Auth-gated clinical E2E (Fase 11 acceptance: "los E2E críticos bloquean deploy").
 *
 * These are the flows the roadmap requires: onboarding → paciente → cita →
 * encuentro → historia → evolución → CIE-10 → receta → consentimiento → firma →
 * impresión → verificación → addendum → exportación.
 *
 * They are `test.fixme` — defined but not run — because they need a Clerk TEST
 * instance (testing tokens + a seeded user/tenant) and a running backend. See
 * e2e/README.md. Wiring auth.setup.ts (storageState) turns these on: remove the
 * `.fixme` and implement each body against the app's real selectors.
 *
 * Kept as skeletons (not deleted) so the required coverage is explicit and the
 * gaps are visible in the test report rather than forgotten.
 */
test.describe('clinical flows (require Clerk test auth + backend)', () => {
  test.fixme('onboarding: a new doctor completes tenant onboarding', async ({ page }) => {
    await page.goto('/onboarding');
    await expect(page).toHaveURL(/\/app/);
  });

  test.fixme('paciente: create a patient and open its record', async () => {});
  test.fixme('cita: schedule an appointment for the patient', async () => {});
  test.fixme('encuentro: open a first-time encounter (primera vez)', async () => {});
  test.fixme('historia + evolución: capture history and an evolution note', async () => {});
  test.fixme('CIE-10: attach structured diagnoses with a principal', async () => {});
  test.fixme('receta: issue a prescription snapshot', async () => {});
  test.fixme('consentimiento: create and patient-sign a consent', async () => {});
  test.fixme('firma: sign the note (KMS) and confirm it becomes immutable', async () => {});
  test.fixme('impresión: print produces the legal document without new S3 objects', async () => {});
  test.fixme('verificación: the public verify page validates the signed document', async () => {});
  test.fixme('addendum: add a signed amendment referencing the original', async () => {});
  test.fixme('exportación: export the record and verify integrity', async () => {});

  // Degraded mode (Fase 10) is unit-tested; an auth-gated E2E would assert the
  // sign button is disabled when /health/ready reports 503.
  test.fixme('degraded mode: signing is blocked when readiness is 503', async () => {});
});
