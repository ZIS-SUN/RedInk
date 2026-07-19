import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 生产构建时移除 console/debugger（开发环境保留，便于调试）
  esbuild: command === 'build'
    ? { drop: ['console', 'debugger'] as ('console' | 'debugger')[] }
    : undefined,
  build: {
    rollupOptions: {
      output: {
        // 把第三方库单独拆包，避免与业务代码一起失效缓存
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia', 'axios']
        }
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:12398',
        changeOrigin: true
      }
    }
  }
}))
