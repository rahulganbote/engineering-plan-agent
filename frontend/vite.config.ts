import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Move Vite's pre-bundling cache OUT of node_modules/.vite/ - OneDrive holds
  // a sync-lock on files inside synced folders and Vite's unlink-then-rewrite
  // pattern fails with EPERM. ~/.cache/em-copilot-vite is outside OneDrive,
  // so Vite has uncontested write access. (No effect on CI or Cloud Build -
  // they each get a fresh container with no .cache to worry about.)
  cacheDir: process.env.HOME ? `${process.env.HOME}/.cache/em-copilot-vite` : 'node_modules/.vite',

  server: {
    port: 5173,
    host: true,
    allowedHosts: ['dev.localtest.me', '.ngrok.io', '.ngrok-free.app'],
    proxy: {
      // During dev, proxy /api, /run-pipeline, /status, /approve, /download, /auth
      // to FastAPI so the React app can call them without CORS headaches.
      '/api': 'http://localhost:8000',
      '/run-pipeline': 'http://localhost:8000',

      '/status': { target: 'http://localhost:8000', changeOrigin: true },
      '/events': 'http://localhost:8000',
      '/approve': 'http://localhost:8000',
      '/download': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/results': 'http://localhost:8000',
      '/artifacts': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
    // Vitest covers unit + component tests in src/. Playwright (Sprint 5) owns
    // the e2e/ folder. Without these, Vitest would try to collect the Playwright
    // spec and fail to resolve @playwright/test.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'e2e', '.cache'],
  },
})
