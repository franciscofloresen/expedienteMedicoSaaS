import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// Vitest config lives in vitest.config.ts so this file stays typed against
// rolldown-vite (Vite 8) without pulling in vitest's rollup-based vite types.
export default defineConfig({
  plugins: [react()],
})
