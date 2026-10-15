import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Vite 配置：
// - dev 用代理把 /api 转发到 Mock 后端（避免 CORS，即便 mock 已带 CORS 也更省事）
// - baseURL 通过 .env 的 VITE_API_BASE 控制：开发走 /api（proxy），生产留空走同源
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const mockTarget = env.VITE_MOCK_TARGET || 'http://127.0.0.1:8800'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': {
          target: mockTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
    },
  }
})
