import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',
  // Load .env from the monorepo root instead of frontend/
  envDir: path.resolve(__dirname, '..'),
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/tests/setup.js',
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      // Only measure source files we actually write — not config, dist, or tests
      include: ['src/**/*.{js,jsx,ts,tsx}'],
      exclude: [
        'src/tests/**',
        'src/main.jsx', // entry point — just wires providers, not logic
        'src/Router.jsx', // route table — tested via integration, not unit
        'src/App.jsx',
      ],
      thresholds: {
        lines: 50,
        functions: 60,
        branches: 70,
        statements: 50,
      },
    },
  },
});
