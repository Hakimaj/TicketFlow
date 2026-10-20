import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
  },
  test: {
    // Playwright specs live in e2e/ and are run by `npm run test:e2e`.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
  build: {
    rollupOptions: {
      output: {
        // Split heavy, rarely-changing dependencies into cacheable chunks so
        // the application code stays well below the 500 kB warning threshold.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('recharts') || id.includes('d3-')) return 'charts'
          if (id.includes('@radix-ui')) return 'radix'
          if (id.includes('lucide-react')) return 'icons'
          if (
            id.includes('react-router') ||
            id.includes('react-dom') ||
            id.includes('node_modules/react/') ||
            id.includes('scheduler')
          ) {
            return 'vendor'
          }
          return undefined
        },
      },
    },
  },
})
