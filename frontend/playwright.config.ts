import { defineConfig, devices } from '@playwright/test';

// E2E config (Fase 11). The public smoke runs with no backend and no real auth.
// The auth-gated clinical flows need a Clerk TEST instance — see e2e/README.md.
const PORT = Number(process.env.E2E_PORT ?? 5173);
const baseURL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    // Locally, Vite reads the real dev publishable key from .env.local (gitignored),
    // so the app mounts fully. In CI there is no .env.local, so provide a format-valid
    // placeholder (or a real CI value) — enough for ClerkProvider to construct and the
    // public marketing shell to render; the fake domain means only public/static
    // content is asserted until a Clerk test instance is wired (see e2e/README.md).
    env: process.env.CI
      ? {
          VITE_CLERK_PUBLISHABLE_KEY:
            process.env.VITE_CLERK_PUBLISHABLE_KEY ?? 'pk_test_Y2xlcmsuZXhhbXBsZS5jb20k',
          VITE_API_URL: process.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1',
        }
      : {},
  },
});
