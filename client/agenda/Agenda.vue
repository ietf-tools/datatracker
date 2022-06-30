<template lang="pug">
.agenda(
  :class='{ "bolder-text": agendaStore.bolderText }'
  )
  h1
    span #[strong IETF {{agendaStore.meeting.number}}] Meeting Agenda {{titleExtra}}
    .agenda-h1-badges
      span.agenda-warning(v-if='agendaStore.meeting.warningNote') {{agendaStore.meeting.warningNote}}
      span.agenda-beta BETA
  h4
    span {{agendaStore.meeting.city}}, {{ meetingDate }}
    h6.float-end.d-none.d-lg-inline(v-if='meetingUpdated') #[span.text-muted Updated:] {{ meetingUpdated }}

  .agenda-topnav.my-3
    ul.nav.nav-tabs
      li.nav-item(v-for='tab of state.tabs')
        a.nav-link.agenda-link.filterable(
          :class='{ active: tab.key === state.currentTab }'
          :href='tab.href ? `/meeting/` + agendaStore.meeting.number + `/` + tab.href : null'
          )
          i.bi.me-2(:class='tab.icon')
          span {{tab.title}}
    n-button(
      quaternary
      @click='toggleSettings'
      )
      template(#icon)
        i.bi.bi-gear
      span Settings

  .row
    .col

      // ----------------------------
      // -> Subtitle + Timezone Bar
      // ----------------------------
      .row
        .col.d-flex.align-items-center
          h2 {{ agendaStore.pickerMode ? 'Session Selection' : 'Schedule'}}

          n-popover(v-if='!agendaStore.infoNoteShown')
            template(#trigger)
              n-button.ms-2(text, @click='toggleInfoNote')
                i.bi.bi-info-circle.text-muted
            span Show Info Note
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
            v-if='agendaStore.viewport > 1250'
            v-model:value='agendaStore.timezone'
            :options='timezones'
            placeholder='Select Time Zone'
            filterable
            )

      .alert.alert-warning.mt-3(v-if='agendaStore.isCurrentMeeting') #[strong Note:] IETF agendas are subject to change, up to and during a meeting.
      .agenda-infonote.mt-3(v-if='agendaStore.meeting.infoNote && agendaStore.infoNoteShown')
        n-popover
          template(#trigger)
            n-button(
              text
              aria-label='Close Info Note'
              @click='toggleInfoNote'
              )
              i.bi.bi-x-square
          span Hide Info Note
        div(v-html='agendaStore.meeting.infoNote')

      // -----------------------------------
      // -> Search Bar
      // -----------------------------------

      .agenda-search.mt-3(v-if='agendaStore.searchVisible')
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
          n-popover
            template(#trigger)
              n-button(
                type='primary'
                ghost
                @click='state.searchText = ``'
                aria-label='Clear Search'
                )
                i.bi.bi-x-lg
            span Clear Search
          

      // -----------------------------------
      // -> Drawers
      // -----------------------------------
      agenda-filter
      agenda-schedule-calendar
      agenda-settings

      // -----------------------------------
      // -> Schedule List
      // -----------------------------------
      agenda-schedule-list.mt-3(ref='schdList')

    // -----------------------------------
    // -> Anchored Day Quick Access Menu
    // -----------------------------------
    .col-auto.d-print-none(v-if='agendaStore.viewport >= 990')
      agenda-quick-access

  agenda-mobile-bar
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
  NPopover,
  NSelect,
  useMessage
} from 'naive-ui'
import AgendaFilter from './AgendaFilter.vue'
import AgendaScheduleList from './AgendaScheduleList.vue'
import AgendaScheduleCalendar from './AgendaScheduleCalendar.vue'
import AgendaQuickAccess from './AgendaQuickAccess.vue'
import AgendaSettings from './AgendaSettings.vue'
import AgendaMobileBar from './AgendaMobileBar.vue'

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
    { key: 'agenda', title: 'Agenda (New)', icon: 'bi-calendar3' },
    { key: 'agenda-legacy', href: 'agenda', title: 'Agenda', icon: 'bi-calendar2-week' },
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

const titleExtra = computed(() => {
  let title = ''
  if (agendaStore.timezone === 'UTC') {
    title = `${title} (UTC)`
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

function toggleInfoNote () {
  agendaStore.$patch({ infoNoteShown: !agendaStore.infoNoteShown })
  agendaStore.persistMeetingPreferences()
}

function toggleSettings () {
  agendaStore.$patch({
    settingsShown: !agendaStore.settingsShown
  })
}

// Handle browser resize

const resizeObserver = new ResizeObserver(entries => {
  agendaStore.$patch({ viewport: Math.round(window.innerWidth) })
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
  min-height: 500px;
  font-weight: 460;

  &.bolder-text {
    font-weight: 520;
  }

  > h1 {
    font-weight: 500;
    color: $gray-700;
    display: flex;
    justify-content: space-between;
    align-items: center;

    strong {
      font-weight: 700;
      background: linear-gradient(220deg, $blue-500 20%, $purple-500 70%);
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      box-decoration-break: clone;
    }
  }

  &-topnav {
    position: relative;

    > button {
      position: absolute;
      top: 5px;
      right: 0;

      .bi {
        transition: transform 1s ease;
      }

      &:hover {
        .bi {
          transform: rotate(180deg);
        }
      }
    }
  }

  &-timezone-ddn {
    min-width: 350px;
  }

  &-infonote {
    border: 1px solid $blue-400;
    border-radius: .25rem;
    background: linear-gradient(to top, lighten($blue-100, 2%), lighten($blue-100, 5%));
    box-shadow: inset 0 0 0 1px #FFF;
    padding: 16px 50px 16px 16px;
    font-size: .9rem;
    color: $blue-700;
    position: relative;

    > button {
      position: absolute;
      top: 15px;
      right: 15px;
      font-size: 1.2em;
      color: $blue-400;
    }
  }

  &-h1-badges {
    display: flex;
    justify-content: end;
    align-items: center;

    > span {
      font-size: 13px;
      font-weight: 700;
      background-color: $pink-500;
      box-shadow: 0 0 5px 0 rgba($pink-500, .5);
      color: #FFF;
      padding: 5px 8px;
      border-radius: 6px;

      & + span {
        margin-left: 10px;
      }
    }
  }

  &-warning {
    background-color: $red-500 !important;
    box-shadow: 0 0 5px 0 rgba($red-500, .5) !important;
    color: #FFF;
    animation: warningBorderFlash 1s ease infinite;
  }
}

.n-dropdown-option {
  .text-red {
    color: $red-500;
  }
  .text-brown {
    color: $orange-700;
  }
  .text-blue {
    color: $blue-600;
  }
  .text-green {
    color: $green-500;
  }
  .text-purple {
    color: $purple-500;
  }
}

@keyframes spin {
  from { transform:rotate(0deg); }
  to { transform:rotate(360deg); }
}

@keyframes warningBorderFlash {
  10% { color: #FFF; }
  50% { color: $red-300; }
  90% { color: #FFF; }
}
</style>
