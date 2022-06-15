<template lang="pug">
.agenda-quickaccess
  n-affix(:top='240')
    .card.shadow-sm
      .card-body
        n-button(
          block
          type='success'
          size='large'
          strong
          @click='showFilter'
          )
          n-badge.me-2(:value='agendaStore.selectedCatSubs.length', processing)
          i.bi.bi-funnel.me-2
          span Filter Areas + Groups...
        n-button.mt-2(
          v-if='!agendaStore.pickerMode'
          block
          secondary
          type='success'
          size='large'
          strong
          @click='agendaStore.$patch({ pickerMode: true })'
          )
          i.bi.bi-ui-checks.me-2
          span Pick Sessions...
        .agenda-quickaccess-btnrow(v-else)
          .agenda-quickaccess-btnrow-title Session Selection
          n-button.me-1(
            v-if='!agendaStore.pickerModeView'
            type='success'
            size='large'
            strong
            @click='agendaStore.$patch({ pickerModeView: true })'
            )
            i.bi.bi-check2-square.me-2
            span Apply
          n-button.me-1(
            v-else
            color='#6f42c1'
            size='large'
            strong
            @click='agendaStore.$patch({ pickerModeView: false })'
            )
            i.bi.bi-pencil-square.me-2
            span Modify
          n-button.ms-1(
            secondary
            color='#666'
            size='large'
            strong
            @click='agendaStore.$patch({ pickerMode: false })'
            )
            i.bi.bi-x-square.me-2
            span Discard
        n-divider: small.text-muted Calendar
        n-button.mt-2(
          block
          color='#6c757d'
          size='large'
          strong
          @click='agendaStore.$patch({ calendarShown: true })'
          )
          i.bi.bi-calendar3.me-2
          span Calendar View
        n-dropdown(
          :options='downloadIcsOptions'
          size='large'
          :show-arrow='true'
          trigger='click'
          @select='downloadIcs'
          )
          n-button.mt-2(
            block
            secondary
            color='#6c757d'
            size='large'
            strong
            )
            i.bi.bi-calendar-check.me-2
            span Add to your calendar...
        template(v-if='agendaStore.meetingDays.length > 0')
          n-divider: small.text-muted Jump to...
          ul.nav.nav-pills.flex-column.small
            li.nav-item(v-if='agendaStore.isMeetingLive')
              a.nav-link(
                href='#now'
                @click='scrollToNow'
                )
                i.bi.bi-arrow-right-short.me-2
                span Now
            li.nav-item(v-for='day of agendaStore.meetingDays')
              a.nav-link(
                :class='agendaStore.dayIntersectId === day.slug ? `active` : ``'
                :href='`#slot-` + day.slug'
                @click='scrollToDay(day.slug, $event)'
                )
                i.bi.bi-arrow-right-short.me-2
                span {{day.label}}
</template>

<script setup>
import { h } from 'vue'
import { DateTime } from 'luxon'
import {
  NAffix,
  NBadge,
  NButton,
  NDivider,
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

function showFilter () {
  agendaStore.$patch({ filterShown: true })
}

function scrollToDay (dayId, ev) {
  ev.preventDefault()
  document.getElementById(`agenda-day-${dayId}`)?.scrollIntoView(true)
}

function scrollToNow (ev) {
  ev.preventDefault()

  const current = DateTime.local().setZone(agendaStore.timezone)

  // -> Find last event before current time
  let lastEventId = null
  for(const sh of agendaStore.scheduleAdjusted) {
    if (sh.adjustedStart <= current) {
      lastEventId = sh.id
    }
    if (sh.adjustedEnd > current) {
      break
    }
  }

  if (lastEventId) {
    document.getElementById(`agenda-rowid-${lastEventId}`)?.scrollIntoView(true)
  }
}

</script>

<style lang="scss">
.agenda-quickaccess {
    width: 300px;

    .card {
      width: 300px;
    }

    &-btnrow {
      border: 1px solid #CCC;
      padding: 8px 6px 6px 6px;
      border-radius: 5px;
      display: flex;
      justify-content: stretch;
      position: relative;
      text-align: center;
      margin-top: 12px;

      &-title {
        position: absolute;
        top: -8px;
        font-size: 9px;
        font-weight: 600;
        color: #999;
        left: 50%;
        padding: 0 5px;
        background-color: #FFF;
        transform: translate(-50%, 0);
        text-transform: uppercase;
      }

      button {
        flex: 1;
      }
    }
  }
</style>
