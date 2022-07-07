<template lang="pug">
ul.nav.nav-tabs
  li.nav-item(v-for='tab of tabs')
    a.nav-link(
      v-if='tab.href'
      :href='`/meeting/` + agendaStore.meeting.number + `/` + tab.href'
      )
      i.bi.me-2(:class='tab.icon')
      span {{tab.title}}
    router-link.nav-link(
      v-else
      active-class='active'
      :to='`/meeting/` + agendaStore.meeting.number + `/` + tab.key + `-neue`'
      )
      i.bi.me-2(:class='tab.icon')
      span {{tab.title}}
</template>

<script setup>
import { useAgendaStore } from './store'

// STATE

const tabs = [
  { key: 'agenda', title: 'Agenda', icon: 'bi-calendar3' },
  { key: 'floor-plan', title: 'Floor plan', icon: 'bi-pin-map' },
  { key: 'plaintext', href: 'agenda.txt', title: 'Plaintext', icon: 'bi-file-text' }
]

// STORES

const agendaStore = useAgendaStore()
</script>
