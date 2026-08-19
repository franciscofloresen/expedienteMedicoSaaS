import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Separate from vite.config.ts on purpose: importing defineConfig from
// 'vitest/config' brings vitest's rollup-based vite types, which clash with the
// app's rolldown-vite (Vite 8). Keeping it here — and out of the tsconfig
// includes — lets `tsc -b` typecheck the app cleanly while vitest still runs.
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Vitest owns src/**; Playwright owns e2e/** (its .spec.ts files import
    // @playwright/test and must not be collected by Vitest).
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'text-summary'],
      // Focus coverage on business logic, not scaffolding, config, or pure-markup
      // pages — "no premiar cobertura de modelos vacíos" (Fase 11).
      include: ['src/hooks/**', 'src/contexts/**', 'src/services/**', 'src/utils/**'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/types.ts'],
    },
  },
})
