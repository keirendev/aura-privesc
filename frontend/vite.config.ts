import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8888',
    },
  },
  build: {
    outDir: '../src/aura_privesc/web/static',
    emptyOutDir: true,
  },
})
