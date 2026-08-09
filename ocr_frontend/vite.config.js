import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Listen on all network interfaces inside Docker
    port: 3000,
    strictPort: true,
    watch: {
      usePolling: true, // REQUIRED for Windows / WSL2 Docker volume file change detection
    },
    hmr: {
      clientPort: 3000, // Forces the browser to connect the Hot-Reload WebSocket to port 3000
    }
  }
})