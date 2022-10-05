<template lang="pug">
n-theme
  n-message-provider
    .app-error(v-if='siteStore.criticalError')
      i.bi.bi-x-octagon-fill.me-2
      span {{siteStore.criticalError}}
    .app-container(ref='appContainer')
      router-view.meeting
</template>

<script setup>
import { onBeforeUnmount ,onMounted, ref } from 'vue'
import { NMessageProvider } from 'naive-ui'

import { useSiteStore } from './shared/store'

import NTheme from './components/n-theme.vue'

// STORES

const siteStore = useSiteStore()

// STATE

const appContainer = ref(null)

// --------------------------------------------------------------------
// Handle browser resize
// --------------------------------------------------------------------

const resizeObserver = new ResizeObserver(entries => {
  siteStore.$patch({ viewport: Math.round(window.innerWidth) })
  // for (const entry of entries) {
    // const newWidth = entry.contentBoxSize ? entry.contentBoxSize[0].inlineSize : entry.contentRect.width
  // }
})

onMounted(() => {
  resizeObserver.observe(appContainer.value, { box: 'device-pixel-content-box' })
})

onBeforeUnmount(() => {
  resizeObserver.unobserve(appContainer.value)
})
</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.app-error {
  background-color: $red-500;
  border-radius: 5px;
  color: #FFF;
  font-weight: 500;
  padding: 1rem;
  text-align: center;
}
</style>
