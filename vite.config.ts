import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  // Phase 3에서 다시 켠다: 로컬에서 `vercel dev`(포트 3000)를 띄우면 /api 요청을 그쪽으로 넘긴다.
  // 지금은 서버가 없어 프록시가 ECONNREFUSED → 500 을 돌려주므로 꺼 둔다.
  // server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
})
