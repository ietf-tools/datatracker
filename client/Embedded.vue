<template lang="pug">
n-theme
  n-notification-provider
    n-message-provider
      component(:is='currentComponent', :component-id='props.componentId')
</template>

<script setup>
import { defineAsyncComponent, markRaw, onMounted, ref } from 'vue'
import { NMessageProvider, NNotificationProvider } from 'naive-ui'

import NTheme from './components/n-theme.vue'

// COMPONENTS

const availableComponents = {
  ChatLog: defineAsyncComponent(() => import('./components/ChatLog.vue')),
  Polls: defineAsyncComponent(() => import('./components/Polls.vue')),
  Status: defineAsyncComponent(() => import('./components/Status.vue'))
}

// PROPS

const props = defineProps({
  componentName: {
    type: String,
    default: null
  },
  componentId: {
    type: String,
    default: null
  }
})

// STATE

const currentComponent = ref(null)

// MOUNTED

onMounted(() => {
  currentComponent.value = markRaw(availableComponents[props.componentName] || null)
})
</script>
