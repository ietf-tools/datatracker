<template lang="pug">
n-theme
  n-message-provider
    .app-error(v-if='siteStore.criticalError')
      i.bi.bi-x-octagon-fill.me-2
      span {{siteStore.criticalError}}
    .app-error-link(v-if='siteStore.criticalError && siteStore.criticalErrorLink')
      a(:href='siteStore.criticalErrorLink') {{siteStore.criticalErrorLinkText}} #[i.bi.bi-arrow-right-square-fill.ms-2]
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
// Set user theme
// --------------------------------------------------------------------

function updateTheme() {
  const desiredTheme = window.localStorage?.getItem('theme')
  if (desiredTheme === 'dark') {
    siteStore.theme = 'dark'
  } else if (desiredTheme === 'light') {
    siteStore.theme = 'light'
  } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    siteStore.theme = 'dark'
  } else {
    siteStore.theme = 'light'
  }
}

updateTheme()

// this change event fires for either light or dark changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateTheme)

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
  resizeObserver.observe(appContainer.value)
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

.app-error-link {
  background-color: lighten($red-100, 5%);
  border-radius: 0 0 5px 5px;
  color: #FFF;
  font-weight: 500;
  font-size: .9em;
  padding: .7rem 1rem;
  text-align: center;

  a {
    color: $red-700;
    text-decoration: none;

    &:hover, &:focus {
      text-decoration: underline;
    }
  }
}
</style>
