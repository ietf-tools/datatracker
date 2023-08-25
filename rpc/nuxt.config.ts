// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  app: {
    baseURL: '/rpc/'
  },
  colorMode: {
    preference: 'light',
    classSuffix: '',
    fallback: 'light'
  },
  devtools: {
    enabled: true
  },
  headlessui: {
    prefix: 'Headless'
  },
  modules: [
    '@nuxt/devtools',
    '@nuxtjs/color-mode',
    // '@nuxtjs/eslint-module',
    '@nuxtjs/tailwindcss',
    '@nuxtjs/robots',
    '@pinia/nuxt',
    'nuxt-headlessui',
    'nuxt-icon',
    'nuxt-svgo'
  ],
  robots: {
    rules: [
      { UserAgent: '*' },
      { Disallow: '/' }
    ]
  },
  tailwindcss: {
    viewer: false
  }
})
