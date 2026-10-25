import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { readFileSync } from 'fs'

/** [chunk, module path pattern]: first match wins. */
const VENDOR_CHUNKS: [string, RegExp][] = [
  ['charts', /\/node_modules\/(recharts|d3-[^/]+|victory-vendor|@reduxjs|redux|react-redux|immer|reselect|decimal\.js-light|eventemitter3|internmap|es-toolkit)\//],
  ['tanstack-query', /\/node_modules\/@tanstack\/(query-core|react-query)\//],
  ['tanstack-grid', /\/node_modules\/@tanstack\//], // table + virtual: the data grids only
  ['dates', /\/node_modules\/(date-fns|react-day-picker|@date-fns)\//],
  // Shared with the app shell: kept out of 'charts' (Rollup would otherwise move them into it)
  ['ui', /\/node_modules\/(radix-ui|@radix-ui|@floating-ui|clsx|tailwind-merge|class-variance-authority)\//],
  ['react', /\/node_modules\/(react|react-dom|scheduler|react-router|react-router-dom|cookie|set-cookie-parser|use-sync-external-store)\//],
];

const rootPkg = JSON.parse(readFileSync(path.resolve(__dirname, '../package.json'), 'utf-8'))

export default defineConfig({
  // Absolute base everywhere: the packaged app is served over HTTP from the backend root, and
  // relative asset paths break on nested routes (/extras/stats/vpip reloads to a blank page)
  base: '/',
  define: {
    __APP_VERSION__: JSON.stringify(rootPkg.version),
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Vendor groups as their own chunks (08/F11): the screens are lazy routes (App.tsx), and
        // the charting stack only loads with the first screen that draws a chart
        manualChunks(id) {
          if (!id.includes('/node_modules/')) return undefined;
          return VENDOR_CHUNKS.find(([, pattern]) => pattern.test(id))?.[0];
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:4243',
    },
  },
})
