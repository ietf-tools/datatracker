<template lang="pug">
n-theme
  n-message-provider
    agenda
</template>

<script setup>
import { NMessageProvider } from 'naive-ui'

import { useAgendaStore } from './store'

import NTheme from '../components/n-theme.vue'
import Agenda from './Agenda.vue'

// STORES

const agendaStore = useAgendaStore()

// INIT

agendaStore.fetch()

</script>
