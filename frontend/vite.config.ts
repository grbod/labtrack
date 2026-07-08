/// <reference types="vitest/config" />
import path from "path"
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from "@tailwindcss/vite"
import { execSync } from 'child_process'

// Get git commit hash
const gitHash = execSync('git rev-parse --short HEAD').toString().trim()

// Backend origin the dev server proxies to; override to run parallel stacks
// (e.g. a worktree backend on another port): API_TARGET=http://localhost:8010
const apiTarget = process.env.API_TARGET || 'http://localhost:8009'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  define: {
    '__GIT_HASH__': JSON.stringify(gitHash),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/uploads': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
  },
})
