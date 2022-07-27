import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  base: '/static/',
  build: {
    outDir: 'ietf/static/dist-neue',
    manifest: true,
    rollupOptions: {
      input: {
        main: 'client/main.js'
      }
    }
  },
  cacheDir: '.vite',
  plugins: [
    vue()
  ],
  publicDir: 'ietf/static/public',
  server: {
    host: true
  }
})
