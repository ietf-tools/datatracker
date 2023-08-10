<template lang='pug'>
n-config-provider(
  :theme='currentTheme'
  :theme-overrides='state.themeOverrides'
  )
  slot
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { darkTheme, NConfigProvider } from 'naive-ui'

import { useSiteStore } from '../shared/store'

// STORES

const siteStore = useSiteStore()

// DATA

const state = reactive({
  themeOverrides: {
    common: {
      primaryColor: '#0d6efd',
      primaryColorHover: '#0d6efd'
    }
  }
})

// COMPUTED

const currentTheme = computed(() => {
  return siteStore.theme === 'dark' ? darkTheme : null
})

// APPLY BODY THEME CLASS

watch(() => siteStore.theme, (newValue) => {
  if (newValue === 'dark') {
    document.body.classList.add('theme-dark')
  } else {
    document.body.classList.remove('theme-dark')
  }
}, { immediate: true })
</script>
