import { defineConfig } from 'vite'

// ponytail: sin @vitejs/plugin-react. Vite transpila .jsx con esbuild y runtime
// automatico de serie; el plugin solo aporta Fast Refresh en dev. Si alguien
// pasa el dia en `npm run dev`, que lo agregue.
export default defineConfig({
  base: './',
  esbuild: { jsx: 'automatic' },   // sin esto esbuild emite React.createElement clasico
  build: { outDir: 'dist', emptyOutDir: true },
})
