module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    jquery: true,
    node: true,
    'vue/setup-compiler-macros': true
  },
  extends: [
    // 'plugin:vue/vue3-essential', // Priority A: Essential (Error Prevention)
    'plugin:vue/vue3-strongly-recommended' // Priority B: Strongly Recommended (Improving Readability)
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
    'vue/script-setup-uses-vars': 'error',
    'vue/multi-word-component-names': 'off',
    'vue/max-attributes-per-line': 'off',
    'vue/singleline-html-element-content-newline': 'off'
  }
}
