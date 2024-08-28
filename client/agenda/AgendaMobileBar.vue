<template lang="pug">
.agenda-mobile-bar(v-if='siteStore.viewport < 990')
  n-dropdown(
    :options='jumpToDayOptions'
    size='huge'
    :show-arrow='true'
    trigger='click'
    @select='jumpToDay'
    )
    button
      i.bi.bi-arrow-down-circle
  button(@click='agendaStore.$patch({ filterShown: true })')
    i.bi.bi-funnel
    n-badge.ms-2(:value='agendaStore.selectedCatSubs.length', processing)
  button(@click='agendaStore.$patch({ calendarShown: true })')
    i.bi.bi-calendar3
  n-dropdown(
    :options='downloadIcsOptions'
    size='huge'
    :show-arrow='true'
    trigger='click'
    @select='downloadIcs'
    )
    button
      i.bi.bi-download
  button(@click='agendaStore.$patch({ settingsShown: !agendaStore.settingsShown })')
    i.bi.bi-gear
</template>

<script setup>
import { computed, h } from 'vue'
import {
  NBadge,
  NDropdown,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'
import { useSiteStore } from '../shared/store'
import { getUrl } from '../shared/urls'

// MESSAGE PROVIDER

const message = useMessage()

// STORES

const agendaStore = useAgendaStore()
const siteStore = useSiteStore()

// Meeting Days

function optionToLink(opts){
  const { key, label, icon } = opts

  return {
    ...opts,
    type: 'render',
    render: () => h(
      'a',
      {
        class: 'dropdown-link',
        'data-testid': 'mobile-link',
        href: `#${key}`
      },
      [
        h(
          'span',
          icon()
        ),
        h(
          'span',
          label
        )
      ]
    )
  }
}

const jumpToDayOptions = computed(() => {
  const days = []
  if (agendaStore.isMeetingLive) {
    days.push(optionToLink({
      label: 'Jump to Now',
      key: 'now',
      icon: () => h('i', { class: 'bi bi-arrow-down-right-square text-red' })
    }))
  }
  for (const day of agendaStore.meetingDays) {
    days.push(optionToLink({
      label: `Jump to ${day.label}`,
      key: day.slug,
      icon: () => h('i', { class: 'bi bi-arrow-down-right-square' })
    }))
  }
  return days
})

// Download Ics Options

const downloadIcsOptions = [
  {
    label: 'Subscribe... (webcal)',
    key: 'subscribe',
    icon: () => h('i', { class: 'bi bi-calendar-week' })
  },
  {
    label: 'Download... (.ics)',
    key: 'download',
    icon: () => h('i', { class: 'bi bi-arrow-down-square' })
  }
]

// METHODS

function jumpToDay (dayId) {
  if (dayId === 'now') {
    const lastEventId = agendaStore.findCurrentEventId()
    if (lastEventId) {
      document.getElementById(`agenda-rowid-${lastEventId}`)?.scrollIntoView(true)
    } else {
      message.warning('There is no event happening right now.')
    }
  } else {
    document.getElementById(dayId)?.scrollIntoView(true)
  }
}

function downloadIcs (key) {
  message.loading('Generating calendar file... Download will begin shortly.')
  let icsUrl = ''
  if (agendaStore.pickerMode) {
    const sessionKeywords = agendaStore.scheduleAdjusted.map(s => s.sessionKeyword)
    icsUrl = `${getUrl('meetingCalIcs', { meetingNumber: agendaStore.meeting.number })}?show=${sessionKeywords.join(',')}`
  } else if (agendaStore.selectedCatSubs.length > 0) {
    icsUrl = `${getUrl('meetingCalIcs', { meetingNumber: agendaStore.meeting.number })}?show=${agendaStore.selectedCatSubs.join(',')}`
  } else {
    icsUrl = `${getUrl('meetingCalIcs', { meetingNumber: agendaStore.meeting.number })}`
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
    text-align: center;
    flex: 1 1;

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

.dropdown-link {
  display: flex;
  text-decoration:none;
  gap: 0.2rem 0.5rem;
  padding: 0.5em;
  color: var(--bs-body-color);
  
  &:hover,
  &:focus {
    background-color: var(--bs-dark-bg-subtle);
    text-decoration: underline;
  }
}

</style>
