<template lang="pug">
.agenda
  h1 {{title}}
  h4
    span {{agendaStore.meeting.city}}, {{ meetingDate }}
    h6.float-end.d-none.d-lg-inline(v-if='meetingUpdated') #[span.text-muted Updated:] {{ meetingUpdated }}

  ul.nav.nav-tabs.my-3
    li.nav-item(v-for='tab of state.tabs')
      a.nav-link.agenda-link.filterable(
        :class='{ active: tab.key === state.currentTab }'
        :href='tab.href'
        )
        i.bi.me-2(:class='tab.icon')
        span {{tab.title}}

  .row
    .col

      // ----------------------------
      // -> Subtitle + Timezone Bar
      // ----------------------------
      .row
        .col
          h2 {{ state.currentTab === 'personalize' ? 'Session Selection' : 'Schedule'}}
        .col-auto.d-flex.align-items-center
          i.bi.bi-globe.me-2
          small.me-2.d-none.d-md-inline: strong Timezone:
          n-button-group.me-2
            n-button(
              :type='agendaStore.isTimezoneMeeting ? `primary` : `default`'
              @click='setTimezone(`meeting`)'
              ) Meeting
            n-button(
              :type='agendaStore.isTimezoneLocal ? `primary` : `default`'
              @click='setTimezone(`local`)'
              ) Local
            n-button(
              :type='agendaStore.timezone === `UTC` ? `primary` : `default`'
              @click='setTimezone(`UTC`)'
              ) UTC
          n-select.agenda-timezone-ddn(
            v-if='!agendaStore.mobileMode'
            v-model:value='agendaStore.timezone'
            :options='timezones'
            placeholder='Select Time Zone'
            filterable
            )

      .alert.alert-warning.mt-3(v-if='agendaStore.isCurrentMeeting') #[strong Note:] IETF agendas are subject to change, up to and during a meeting.
      .agenda-infonote.my-3(v-if='agendaStore.meeting.infoNote', v-html='agendaStore.meeting.infoNote')

      .agenda-search.mb-3(v-if='agendaStore.searchVisible')
        n-input-group
          n-input(
            v-model:value='state.searchText'
            ref='searchIpt'
            type='text'
            placeholder='Search...'
            @keyup.esc='closeSearch'
            )
            template(#prefix)
              i.bi.bi-search.me-1
          n-button(
            type='primary'
            ghost
            @click='state.searchText = ``'
            )
            i.bi.bi-x-lg

      // -----------------------------------
      // -> Drawers
      // -----------------------------------
      agenda-filter
      agenda-schedule-calendar

      // -----------------------------------
      // -> SCHEDULE LIST
      // -----------------------------------
      agenda-schedule-list(ref='schdList')

    // -----------------------------------
    // -> Anchored Day Quick Access Menu
    // -----------------------------------
    .col-auto.d-print-none(v-if='!agendaStore.mobileMode')
      agenda-quick-access
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { DateTime } from 'luxon'
import debounce from 'lodash/debounce'

import {
  NButtonGroup,
  NButton,
  NInputGroup,
  NInput,
  NSelect,
  useMessage
} from 'naive-ui'
import AgendaFilter from './AgendaFilter.vue'
import AgendaScheduleList from './AgendaScheduleList.vue'
import AgendaScheduleCalendar from './AgendaScheduleCalendar.vue'
import AgendaQuickAccess from './AgendaQuickAccess.vue'

import timezones from '../shared/timezones'

import { useAgendaStore } from './store'

// MESSAGE PROVIDER

const message = useMessage()

// STORES

const agendaStore = useAgendaStore()

// DATA

const state = reactive({
  searchText: '',
  currentTab: 'agenda',
  tabs: [
    { key: 'agenda', title: 'Agenda', icon: 'bi-calendar3' },
    { key: 'floorplan', href: 'floor-plan', title: 'Floor plan', icon: 'bi-pin-map' },
    { key: 'plaintext', href: 'agenda.txt', title: 'Plaintext', icon: 'bi-file-text' }
  ]
})

// REFS

const schdList = ref(null)
const searchIpt = ref(null)

// WATCHERS

watch(() => agendaStore.searchVisible, (newValue) => {
  state.searchText = agendaStore.searchText
  if (newValue) {
    nextTick(() => {
      searchIpt.value?.focus()
    })
  }
})

watch(() => state.searchText, debounce((newValue) => {
  agendaStore.$patch({
    searchText: newValue.toLowerCase()
  })
}, 500))

// COMPUTED

const title = computed(() => {
  let title = `IETF ${agendaStore.meeting.number} Meeting Agenda`
  if (agendaStore.timezone === 'UTC') {
    title = `${title} (UTC)`
  }
  if (agendaStore.currentTab === 'personalize') {
    title = `${title} Personalization`
  }
  return title
})
const meetingDate = computed(() => {
  const start = DateTime.fromISO(agendaStore.meeting.startDate).setZone(agendaStore.timezone)
  const end = DateTime.fromISO(agendaStore.meeting.endDate).setZone(agendaStore.timezone)
  if (start.month === end.month) {
    return `${start.toFormat('MMMM d')} - ${end.toFormat('d, y')}`
  } else {
    return `${start.toFormat('MMMM d')} - ${end.toFormat('MMMM d, y')}`
  }
})
const meetingUpdated = computed(() => {
  return agendaStore.meeting.updated ? DateTime.fromISO(agendaStore.meeting.updated).setZone(agendaStore.timezone).toFormat(`DD 'at' tt ZZZZ`) : false
})

// METHODS

function switchTab (key) {
  state.currentTab = key
  window.history.pushState({}, '', key)
}

function setTimezone (tz) {
  switch (tz) {
    case 'meeting':
      agendaStore.$patch({ timezone: agendaStore.meeting.timezone })
      break
    case 'local':
      agendaStore.$patch({ timezone: DateTime.local().zoneName })
      break
    default:
      agendaStore.$patch({ timezone: tz })
      break
  }
}

function closeSearch () {
  agendaStore.$patch({
    searchText: '',
    searchVisible: false
  })
}

// Handle browser resize

const resizeObserver = new ResizeObserver(entries => {
  agendaStore.$patch({ mobileMode: window.innerWidth < 1400 })
  // for (const entry of entries) {
    // const newWidth = entry.contentBoxSize ? entry.contentBoxSize[0].inlineSize : entry.contentRect.width
  // }
})

onMounted(() => {
  resizeObserver.observe(schdList.value.$el)
})

onBeforeUnmount(() => {
  resizeObserver.unobserve(schdList.value.$el)
})

// Handle day indicator / scroll

const visibleDays = []
const scrollObserver = new IntersectionObserver(entries => {
  for (const entry of entries) {
    if (entry.isIntersecting) {
      if (!visibleDays.some(e => e.id === entry.target.dataset.dayId)) {
        visibleDays.push({
          id: entry.target.dataset.dayId,
          ts: entry.target.dataset.dayTs
        })
      }
    } else {
      const idxToRemove = visibleDays.findIndex(e => e.id === entry.target.dataset.dayId)
      if (idxToRemove >= 0) {
        visibleDays.splice(idxToRemove, 1)
      }
    }
  }

  let finalDayId = agendaStore.dayIntersectId
  let earliestTs = '9'
  for (const day of visibleDays) {
    if (day.ts < earliestTs) {
      finalDayId = day.id
      earliestTs = day.ts
    }
  }

  agendaStore.$patch({ dayIntersectId: finalDayId.toString() })
}, {
  root: null,
  rootMargin: '0px',
  threshold: [0.0, 1.0]
})

onMounted(() => {
  for (const mDay of agendaStore.meetingDays) {
    const el = document.getElementById(`agenda-day-${mDay.slug}`)
    el.dataset.dayId = mDay.slug.toString()
    el.dataset.dayTs = mDay.ts
    scrollObserver.observe(el)
  }
})

onBeforeUnmount(() => {
  for (const mDay of agendaStore.meetingDays) {
    scrollObserver.unobserve(document.getElementById(`agenda-day-${mDay.slug}`))
  }
})

// CREATED

// -> Handle loading tab directly based on URL
if (window.location.pathname.indexOf('-utc') >= 0) {
  agendaStore.$patch({ timezone: 'UTC' })
} else if (window.location.pathname.indexOf('personalize') >= 0) {
  // state.currentTab = 'personalize'
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda {
  &-timezone-ddn {
    min-width: 350px;
  }

  &-infonote {
    border: 1px solid $blue-400;
    border-radius: .25rem;
    background: linear-gradient(to top, lighten($blue-100, 2%), lighten($blue-100, 5%));
    box-shadow: inset 0 0 0 1px #FFF;
    padding: 1rem;
    font-size: .9rem;
    color: $blue-700;
  }

  &-search {
    
  }
}
</style>
