<template lang="pug">
n-theme
  n-message-provider
    agenda(
      :meeting='agendaData.meeting'
      :categories='agendaData.categories'
      :isCurrentMeeting='agendaData.isCurrentMeeting'
      :useCodiMd='agendaData.useCodiMd'
      :schedule='agendaData.schedule'
    )
</template>

<script setup>
import { NMessageProvider } from 'naive-ui'

import NTheme from '../components/n-theme.vue'
import Agenda from './Agenda.vue'

const agendaData = JSON.parse(document.getElementById('agenda-data').textContent)

</script>
