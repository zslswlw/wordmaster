import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    // proxy: {
    //   '/api': {
    //     target: 'http://8.137.151.142:8000',
    //     changeOrigin: true,
    //     secure: false
    //   }
    // }
  }
})
