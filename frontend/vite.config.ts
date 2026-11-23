import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // o Three.js sozinho tem ~600 kB; ele so e baixado ao abrir o Gemeo 3D
  // (rota com import dinamico), entao o aviso de pedaco grande nao se aplica
  build: { chunkSizeWarningLimit: 700 },
  server: {
    // `npm run dev` com a API rodando na maquina host (uvicorn na 8000):
    // o Vite faz o papel do nginx de producao, repassando /api e /ws.
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
