/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api/stream': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
        ws: false,
        timeout: 0,
        buffer: false,  // КРИТИЧНО: отключаем буферизацию для SSE
        configure: (proxy, _options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.url?.includes('/stream')) {
              proxyReq.setHeader('Accept', 'text/event-stream')
              proxyReq.setHeader('Cache-Control', 'no-cache')
              proxyReq.setHeader('Connection', 'keep-alive')
            }
          })
          proxy.on('proxyRes', (proxyRes, req, res) => {
            if (req.url?.includes('/stream')) {
              // КРИТИЧНО: удаляем content-length для chunked encoding
              delete proxyRes.headers['content-length']
              // Устанавливаем правильные заголовки для SSE
              res.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
              res.setHeader('Cache-Control', 'no-cache, no-transform')
              res.setHeader('Connection', 'keep-alive')
              res.setHeader('X-Accel-Buffering', 'no')
              // Отключаем буферизацию ответа
              if (res.flushHeaders) {
                res.flushHeaders()
              }
            }
          })
        }
      },
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
