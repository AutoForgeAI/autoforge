import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Backend port - can be overridden via VITE_API_PORT env var
const apiPort = process.env.VITE_API_PORT || '8888'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // React core
          'vendor-react': ['react', 'react-dom'],
          // Data fetching
          'vendor-query': ['@tanstack/react-query'],
          // Flow/graph visualization (largest dependency)
          'vendor-flow': ['@xyflow/react', 'dagre'],
          // Terminal emulator
          'vendor-xterm': ['@xterm/xterm', '@xterm/addon-fit', '@xterm/addon-web-links'],
          // UI components
          'vendor-ui': [
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-tooltip',
            'lucide-react',
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      // WebSocket endpoints must be listed BEFORE /api to match first
      '/api/spec/ws': {
        target: `ws://127.0.0.1:${apiPort}`,
        ws: true,
        // Handle connection errors gracefully during restarts
        configure: (proxy) => {
          proxy.on('error', () => {}) // Silently handle - browser will auto-reconnect
        },
      },
      '/api/assistant/ws': {
        target: `ws://127.0.0.1:${apiPort}`,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', () => {})
        },
      },
      '/api/expand/ws': {
        target: `ws://127.0.0.1:${apiPort}`,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', () => {})
        },
      },
      '/api': {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
      '/ws': {
        target: `ws://127.0.0.1:${apiPort}`,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', () => {})
        },
      },
    },
  },
})
