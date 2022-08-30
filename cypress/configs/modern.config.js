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
    baseUrl: 'http://localhost:3000',
    setupNodeEvents(on, config) {
      // implement node event listeners here
    }
  },
  numTestsKeptInMemory: 10,
  viewportWidth: 1280,
  viewportHeight: 800
})
