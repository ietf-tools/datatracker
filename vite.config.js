import { defineConfig } from 'vite'
import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const viteConfig = {
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
      host: true,
      port: 3000,
      strictPort: true
    },
    preview: {
      host: true,
      port: 3000,
      strictPort: true
    }
  }
  if (mode === 'test') {
    viteConfig.base = '/'
    viteConfig.root = resolve(__dirname, 'client')
    viteConfig.build.outDir = 'dist'
    viteConfig.build.rollupOptions.input.main = resolve(__dirname, 'client/index.html')
  }
  return viteConfig
})
