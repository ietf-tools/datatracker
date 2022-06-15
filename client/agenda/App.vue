<template lang="pug">
n-theme
  n-message-provider
    agenda
</template>

<script setup>
import { onMounted } from 'vue'
import { NMessageProvider } from 'naive-ui'

import { useAgendaStore } from './store'

import NTheme from '../components/n-theme.vue'
import Agenda from './Agenda.vue'

// STORES

const agendaStore = useAgendaStore()

// INIT

agendaStore.fetch()

// MOUNTED

onMounted(() => {
  // -> Hide loading screen
  const loadingRef = document.querySelector('#app-agenda-loading')
  if (loadingRef) {
    loadingRef.remove()
  }
})

</script>
