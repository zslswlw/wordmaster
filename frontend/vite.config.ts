import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  server: mode === 'development' ? {
    port: 5178,
    host: '127.0.0.1', // 仅本地访问，生产环境不要暴露
    proxy: {
      '/api': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        secure: false
      },
      '/ai-images': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        secure: false
      },
      '/ai-media': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        secure: false
      }
    }
  } : undefined,
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false, // 生产环境不生成 sourcemap
    rollupOptions: {
      output: {
        manualChunks: {
          'element-plus': ['element-plus'],
          'vue-vendor': ['vue', 'vue-router']
        }
      }
    }
  }
}))
