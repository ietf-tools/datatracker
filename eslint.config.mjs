import globals from 'globals'
import js from '@eslint/js'
import neostandard from 'neostandard'
import pluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import { FlatCompat } from '@eslint/eslintrc'

const compat = new FlatCompat()

export default [
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  ...neostandard(),
  ...compat.extends(
    'plugin:vue-pug/vue3-recommended'
  ),
  {
    ignores: [
      '/node_modules'
    ],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parser: vueParser,
      globals: {
        ...globals.browser,
        ...globals.jquery,
        d3: 'readonly'
      }
    },
    rules: {
      'vue/script-setup-uses-vars': 'error',
      'vue/multi-word-component-names': 'off'
    }
  }
]
