import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The Mini App is a single-page client app. It is served statically by Vercel
// from `dist/`; all dynamic work goes through the Python function at /api/app.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    target: 'es2020',
  },
})
