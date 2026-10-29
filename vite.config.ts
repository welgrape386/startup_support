import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  // 로컬 개발: /api 요청을 FastAPI 백엔드(포트 8000)로 넘긴다. 백엔드를 먼저 켜 둘 것.
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
})
