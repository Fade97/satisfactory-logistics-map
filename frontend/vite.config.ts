import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: { proxy: { '/api': 'http://127.0.0.1:8050' } },
  build: { target: 'es2022', chunkSizeWarningLimit: 800 },
});
