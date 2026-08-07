import { defineConfig } from 'vite'
import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'
import servePreviewAssets from './dev/vite-plugins/serve-preview-assets.js'
import precompileLodashTemplates from './dev/vite-plugins/precompile-lodash-templates.js'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const viteConfig = {
    base: '/static/',
    build: {
      outDir: 'ietf/static/dist-neue',
      manifest: true,
      rollupOptions: {
        input: {
          main: 'client/main.js',
          embedded: 'client/embedded.js'
        }
      },
      sourcemap: true
    },
    cacheDir: '.vite',
    plugins: [
      vue(),
      precompileLodashTemplates({
        include: ['**/shared/urls.js']
      })
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
    },
    css: {
      preprocessorOptions: {
        scss: {
          quietDeps: true,
          silenceDeprecations: [
            'import',
            'if-function',
            'global-builtin',
            'color-functions',
            'legacy-js-api'
          ]
        }
      }
    }
  }
  if (mode === 'test') {
    viteConfig.base = '/'
    viteConfig.root = resolve(import.meta.dirname, 'client')
    viteConfig.build.outDir = 'dist'
    viteConfig.build.rollupOptions.input.main = resolve(import.meta.dirname, 'client/index.html')
    viteConfig.plugins.push(servePreviewAssets())
  }
  return viteConfig
})
