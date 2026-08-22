# End-to-end tests (Playwright)

Three tiers, by dependency:

## 1. Public smoke — `public-smoke.spec.ts`
Runs with **no backend and no real auth**. Asserts the SPA boots and serves its
public marketing/legal shell. This is the CI-safe E2E floor.

```bash
npm run e2e:install   # one-time: download the Chromium binary
npm run e2e           # starts the dev server and runs the smoke
npm run e2e:ui        # interactive runner
```

Locally the dev server reads the real Clerk **dev** key from `.env.local`
(gitignored), so the app mounts fully. In CI, `playwright.config.ts` injects a
format-valid placeholder key so the public shell still renders.

## 2. Responsive layout contract — `responsive.spec.ts`
Runs with **no backend and no real auth**, at 768×1024 (iPad vertical), 390×844
(iPhone) and 1440×900 (desktop regression guard).

Asserts the layout rules the daily flow depends on: the page never scrolls
sideways, the expediente's seven-tab bar absorbs its own overflow, form fields
render at ≥16px so iOS Safari does not zoom the page on focus, touch targets are
≥44px, the note editor reserves room for the virtual keyboard — and that none of
this leaks up into the desktop layout.

The clinical widgets live behind auth, so the spec mounts them from the app's own
stylesheet and measures the computed result. That covers the CSS contract, which
is what actually broke on tablets. The auth-gated walk of the real signing flow
sits at the bottom of the same file as `test.fixme`, ready for the wiring below.

## 3. Auth-gated clinical flows — `clinical-flows.spec.ts` (`test.fixme`)
The roadmap's critical flows: onboarding → paciente → cita → encuentro →
historia → evolución → CIE-10 → receta → consentimiento → firma → impresión →
verificación → addendum → exportación.

They are **defined but skipped** (`test.fixme`) because they need a Clerk **test**
instance plus a running backend — an external setup step (same class as the Fase 9
Clerk gate). To turn them on:

1. Create a Clerk test instance with a seeded user + tenant.
2. Provide CI secrets: `VITE_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
   and test-user credentials (or a testing token).
3. `npm i -D @clerk/testing`, implement `auth.setup.ts` (storageState via
   `setupClerkTestingToken`), add a `setup` project + `storageState` to
   `playwright.config.ts`, and remove `.fixme` from the flow specs.
4. Point `VITE_API_URL` at a running backend (local or ephemeral preprod).

The stub in `auth.setup.ts` documents the exact wiring in one place. Keeping the
flows as visible skeletons means the required coverage shows up as pending in the
report instead of being silently absent.
