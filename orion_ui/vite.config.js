import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Expose to network (0.0.0.0)
    port: 5173, // Standard Vite port (avoid 3000 conflict)
    strictPort: true,
  },
})
