import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 0,      // no timeout — SSE sort streams can run for 2+ minutes
        proxyTimeout: 0, // same for the upstream connection
      },
    },
  },
})
