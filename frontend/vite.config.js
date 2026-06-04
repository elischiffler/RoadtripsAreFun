import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/',
  // Load .env from the monorepo root instead of frontend/
  envDir: path.resolve(__dirname, '..'),
});
