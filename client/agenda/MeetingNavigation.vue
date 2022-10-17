<template lang="pug">
ul.nav.nav-tabs.meeting-nav(v-if='agendaStore.isLoaded')
  li.nav-item(v-for='tab of tabs')
    a.nav-link(
      v-if='tab.href'
      :href='`/meeting/` + agendaStore.meeting.number + `/` + tab.href'
      )
      i.bi.me-2.d-none.d-sm-inline(:class='tab.icon')
      span {{tab.title}}
    router-link.nav-link(
      v-else
      active-class='active'
      :to='`/meeting/` + agendaStore.meeting.number + `/` + tab.key'
      )
      i.bi.me-2.d-none.d-sm-inline(:class='tab.icon')
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

<style lang="scss">
@import "../shared/breakpoints";

.meeting-nav {
  @media screen and (max-width: $bs5-break-sm) {
    justify-content: center;
  }
}
</style>
