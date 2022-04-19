module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    jquery: true,
    node: true
  },
  extends: [
    'plugin:vue/vue3-essential', // Priority A: Essential (Error Prevention)
    'plugin:vue/vue3-strongly-recommended', // Priority B: Strongly Recommended (Improving Readability)
    'plugin:cypress/recommended',
    'standard'
  ],
  globals: {
    d3: true
  },
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module'
  },
  plugins: [
    'vue'
  ],
  rules: {
  }
}
