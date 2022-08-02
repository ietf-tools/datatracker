const { defineConfig } = require('cypress')

module.exports = defineConfig({
  chromeWebSecurity: false,
  component: {
    devServer: {
      framework: 'vue',
      bundler: 'vite',
    }
  },
  e2e: {
    baseUrl: 'http://localhost:8000',
    setupNodeEvents(on, config) {
      // implement node event listeners here
    }
  },
  viewportWidth: 1280,
  viewportHeight: 800
})
