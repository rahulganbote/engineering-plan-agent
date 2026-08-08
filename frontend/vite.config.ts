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
  
  // Configure build bundle parameters
  build: {
    // Raises threshold warning from 500kB to 1000kB to pass large icons cleanly
    chunkSizeWarningLimit: 1000,
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
      // Note: We use 127.0.0.1 instead of localhost to prevent macOS IPv6 (::1) resolution
      // delays when connecting to the IPv4-bound Uvicorn server.
      '/api': 'http://127.0.0.1:8000',
      '/run-pipeline': 'http://127.0.0.1:8000',

      '/status': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/events': 'http://127.0.0.1:8000',
      '/approve': 'http://127.0.0.1:8000',
      '/cancel': 'http://127.0.0.1:8000',
      '/download': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/results': 'http://127.0.0.1:8000',
      '/artifacts': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
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
