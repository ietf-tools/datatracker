<template lang="pug">
.agenda-mobile-bar(v-if='agendaStore.viewport < 990')
  button(@click='agendaStore.$patch({ filterShown: true })')
    i.bi.bi-filter-square-fill.me-2
    span Filters
    n-badge.ms-2(:value='agendaStore.selectedCatSubs.length', processing)
  div
    button(@click='agendaStore.$patch({ calendarShown: true })')
      i.bi.bi-calendar3.me-2
      span Calendar
    n-dropdown(
      :options='downloadIcsOptions'
      size='huge'
      :show-arrow='true'
      trigger='click'
      @select='downloadIcs'
      )
      button
        i.bi.bi-calendar-check.me-2
        span .ics
</template>

<script setup>
import { h } from 'vue'

import {
  NBadge,
  NDropdown,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'

// MESSAGE PROVIDER

const message = useMessage()

// STORES

const agendaStore = useAgendaStore()

// Download Ics Options

const downloadIcsOptions = [
  {
    label: 'Subscribe... (webcal)',
    key: 'subscribe',
    icon: () => h('i', { class: 'bi bi-calendar-week text-blue' })
  },
  {
    label: 'Download... (.ics)',
    key: 'download',
    icon: () => h('i', { class: 'bi bi-arrow-down-square' })
  }
]

// METHODS

function downloadIcs (key) {
  message.loading('Generating calendar file... Download will begin shortly.')
  let icsUrl = ''
  if (agendaStore.pickerMode) {
    const sessionKeywords = agendaStore.scheduleAdjusted.map(s => s.sessionKeyword)
    icsUrl = `/meeting/${agendaStore.meeting.number}/agenda.ics?show=${sessionKeywords.join(',')}`
  } else if (agendaStore.selectedCatSubs.length > 0) {
    icsUrl = `/meeting/${agendaStore.meeting.number}/agenda.ics?show=${agendaStore.selectedCatSubs.join(',')}`
  } else {
    icsUrl = `/meeting/${agendaStore.meeting.number}/agenda.ics`
  }
  if (key === 'subscribe') {
    window.location.assign(`webcal://${window.location.host}${icsUrl}`)
  } else {
    window.location.assign(icsUrl)
  }
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-mobile-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 99;
  background-color: rgba(0,0,0,.75);
  backdrop-filter: blur(10px);
  display: flex;
  justify-content: space-between;

  button {
    height: 50px;
    border: none;
    background-color: transparent;
    color: #FFF;
    padding: 0 15px;
    transition: all .4s ease;

    & + button {
      margin-left: 1px;
    }

    i.bi {
      font-size: 1.2em;
    }

    &:hover {
      background-color: $blue-400;
    }
    &:active {
      background-color: $blue-700;
    }
  }
}
</style>
