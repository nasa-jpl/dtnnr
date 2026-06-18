import { tanstackRouter } from '@tanstack/router-plugin/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const SERVER_URL = process.env.OPENAPI_SERVER_URL;

export default defineConfig({
  build: { outDir: 'build' },
  plugins: [
    tanstackRouter({ target: 'react', autoCodeSplitting: true }),
    react(),
  ],
  server: {
    proxy: {
      [SERVER_URL]: {
        target: 'http://api:5000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(new RegExp(`^${SERVER_URL}`), ''),
      },
    },
  },
});
