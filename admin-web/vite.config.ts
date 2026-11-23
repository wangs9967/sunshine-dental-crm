import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const proxy = { '/api': process.env.ADMIN_API_PROXY_TARGET || 'http://127.0.0.1:18081' };

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
});
