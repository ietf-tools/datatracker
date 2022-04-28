<template lang="pug">
.agenda
  h1 {{title}}
  h4
    span {{props.meeting.city}}, {{ meetingDate }}
    h6.float-end(v-if='meetingUpdated') #[span.text-muted Updated:] {{ meetingUpdated }}

  ul.nav.nav-tabs.my-3
    li.nav-item(v-for='tab of state.tabs')
      a.nav-link.agenda-link.filterable(
        :class='{ active: tab.key === state.currentTab }'
        @click.prevent='switchTab(tab.key)'
        :href='tab.key'
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
          small.me-2: strong Timezone:
          n-button-group.me-2
            n-button(
              :type='isTimezoneMeeting ? `primary` : `default`'
              @click='setTimezone(`meeting`)'
              ) Meeting
            n-button(
              :type='isTimezoneLocal ? `primary` : `default`'
              @click='setTimezone(`local`)'
              ) Local
            n-button(
              :type='state.timezone === `UTC` ? `primary` : `default`'
              @click='setTimezone(`UTC`)'
              ) UTC
          n-select.agenda-timezone-ddn(
            v-model:value='state.timezone'
            :options='timezones'
            placeholder='Select Time Zone'
            filterable
            )

      .alert.alert-warning.mt-3(v-if='props.isCurrentMeeting || true') #[strong Note:] IETF agendas are subject to change, up to and during a meeting.
      .agenda-infonote.my-3(v-if='props.meeting.infoNote', v-html='props.meeting.infoNote')

      // -----------------------------------
      // -> Drawers
      // -----------------------------------
      agenda-filter(v-model:shown='state.filterShown', v-model:selection='state.selectedCatSubs', :categories='props.categories')
      agenda-schedule-calendar(v-model:shown='state.calendarShown', :events='scheduleAdjusted')

      // -----------------------------------
      // -> SCHEDULE LIST
      // -----------------------------------
      agenda-schedule-list(
        :events='scheduleAdjusted'
        :picker-mode='state.pickerMode'
        :meeting-number='props.meeting.number'
        :use-codi-md='props.useCodiMd'
        )

    // -----------------------------------
    // -> Anchored Day Quick Access Menu
    // -----------------------------------
    .col-auto.d-print-none
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
                n-badge.me-2(:value='state.selectedCatSubs.length', processing)
                i.bi.bi-funnel.me-2
                span Filter Areas + Groups...
              n-button.mt-2(
                v-if='!state.pickerMode'
                block
                secondary
                type='success'
                size='large'
                strong
                @click='state.pickerMode = true'
                )
                i.bi.bi-ui-checks.me-2
                span Pick Sessions...
              .agenda-quickaccess-btnrow(v-else)
                .agenda-quickaccess-btnrow-title Session Selection
                n-button.me-1(
                  v-if='!state.pickerModeView'
                  type='success'
                  size='large'
                  strong
                  @click='state.pickerModeView = true'
                  )
                  i.bi.bi-check2-square.me-2
                  span Apply
                n-button.me-1(
                  v-else
                  color='#6f42c1'
                  size='large'
                  strong
                  @click='state.pickerModeView = false'
                  )
                  i.bi.bi-pencil-square.me-2
                  span Modify
                n-button.ms-1(
                  secondary
                  color='#666'
                  size='large'
                  strong
                  @click='state.pickerMode = false'
                  )
                  i.bi.bi-x-square.me-2
                  span Discard
              n-divider: small.text-muted Calendar
              n-button.mt-2(
                block
                color='#6c757d'
                size='large'
                strong
                @click='state.calendarShown = true'
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
              n-divider: small.text-muted Jump to...
              ul.nav.nav-pills.flex-column.small
                li.nav-item
                  a.nav-link(href='#now')
                    i.bi.bi-arrow-right-short.me-2
                    span Now
                li.nav-item(v-for='day of meetingDays')
                  a.nav-link(
                    :class='state.dayIntersectId === day.slug ? `active` : ``'
                    :href='`#slot-` + day.slug'
                    @click='scrollToDay(day.slug, $event)'
                    )
                    i.bi.bi-arrow-right-short.me-2
                    span {{day.label}}
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import uniqBy from 'lodash/uniqBy'
import { DateTime } from 'luxon'
import {
  NAffix,
  NBadge,
  NButtonGroup,
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NDataTable,
  NDivider,
  NDrawer,
  NDrawerContent,
  NDropdown,
  NIcon,
  NInput,
  NPopover,
  NSelect,
  NTabPane,
  NTabs,
  useMessage
} from 'naive-ui'
import AgendaFilter from './AgendaFilter.vue'
import AgendaScheduleList from './AgendaScheduleList.vue'
import AgendaScheduleCalendar from './AgendaScheduleCalendar.vue'
import timezones from '../shared/timezones'

// PROPS

const props = defineProps({
  meeting: {
    type: Object,
    default: () => ({})
  },
  categories: {
    type: Array,
    default: () => ([])
  },
  isCurrentMeeting: {
    type: Boolean,
    default: false
  },
  useCodiMd: {
    type: Boolean,
    default: false
  },
  schedule: {
    type: Array,
    default: () => ([])
  }
})

// DATA

const state = reactive({
  dayIntersectId: '',
  visibleDays: [],
  currentTab: 'agenda',
  timezone: DateTime.local().zoneName,
  tabs: [
    { key: 'agenda', title: 'Agenda', icon: 'bi-calendar3' },
    // { key: 'personalize', title: 'Personalize Agenda', icon: 'bi-calendar2-check' },
    { key: 'floorplan', title: 'Floor plan', icon: 'bi-pin-map' },
    { key: 'plaintext', title: 'Plaintext', icon: 'bi-file-text' }
  ],
  searchText: '',
  calendarShown: false,
  downloadIcsShown: false,
  filterShown: false,
  pickerMode: false,
  pickerModeView: false,
  selectedCatSubs: [],
  downloadOptions: [
    {
      label: 'Current Selection...',
      key: 'current',
      icon () {
        return h('i', { class: 'bi bi-calendar2-check' })
      }
    },
    {
      type: 'divider',
      key: 'd1'
    },
    {
      label: 'ART',
      key: 'art'
    },
    {
      label: 'GEN',
      key: 'gen'
    }
  ]
})
const message = useMessage()

// COMPUTED

const isTimezoneLocal = computed(() => {
  return state.timezone === DateTime.local().zoneName
})
const isTimezoneMeeting = computed(() => {
  return state.timezone === props.meeting.timezone
})
const title = computed(() => {
  let title = `IETF ${props.meeting.number} Meeting Agenda`
  if (state.timezone === 'UTC') {
    title = `${title} (UTC)`
  }
  if (state.currentTab === 'personalize') {
    title = `${title} Personalization`
  }
  return title
})
const meetingDate = computed(() => {
  const start = DateTime.fromISO(props.meeting.startDate).setZone(state.timezone)
  const end = DateTime.fromISO(props.meeting.endDate).setZone(state.timezone)
  if (start.month === end.month) {
    return `${start.toFormat('MMMM d')} - ${end.toFormat('d, y')}`
  } else {
    return `${start.toFormat('MMMM d')} - ${end.toFormat('MMMM d, y')}`
  }
})
const scheduleAdjusted = computed(() => {
  return props.schedule.filter(s => {
    // -> Apply filters
    if (state.selectedCatSubs.length > 0 && !s.filterKeywords.some(k => state.selectedCatSubs.includes(k))) {
      return false
    }
    if (s.type === 'lead') { return false }
    return true
  }).map(s => {
    // -> Adjust times to selected timezone
    const eventStartDate = DateTime.fromISO(s.startDateTime, { zone: props.meeting.timezone }).setZone(state.timezone)
    const eventEndDate = eventStartDate.plus({ seconds: s.duration })
    return {
      ...s,
      adjustedStart: eventStartDate,
      adjustedEnd: eventEndDate,
      adjustedStartDate: eventStartDate.toISODate(),
      adjustedStartDateTime: eventStartDate.toISO(),
      adjustedEndDateTime: eventEndDate.toISO()
    }
  })
})
const meetingDays = computed(() => {
  return uniqBy(scheduleAdjusted.value, 'adjustedStartDate').sort().map(s => ({
    slug: s.id.toString(),
    ts: s.adjustedStartDate,
    label: DateTime.fromISO(s.adjustedStartDate).toLocaleString(DateTime.DATE_HUGE)
  }))
})
const meetingUpdated = computed(() => {
  return props.meeting.updated ? DateTime.fromISO(props.meeting.updated).setZone(state.timezone).toFormat(`DD 'at' tt ZZZZ`) : false
})

// METHODS

function switchTab (key) {
  state.currentTab = key
  window.history.pushState({}, '', key)
}
function setTimezone (tz) {
  switch (tz) {
    case 'meeting':
      state.timezone = props.meeting.timezone
      break
    case 'local':
      state.timezone = DateTime.local().zoneName
      break
    default:
      state.timezone = tz
      break
  }
}
function showFilter () {
  state.filterShown = true
}

function downloadIcs (key) {
  message.loading('Generating calendar file... Download will begin shortly.')
  let icsUrl = ''
  if (state.selectedCatSubs.length > 0) {
    icsUrl = `/meeting/${props.meeting.number}/agenda.ics?show=${state.selectedCatSubs.join(',')}`
  } else {
    icsUrl = `/meeting/${props.meeting.number}/agenda.ics`
  }
  if (key === 'subscribe') {
    window.location.assign(`webcal://${window.location.host}${icsUrl}`)
  } else {
    window.location.assign(icsUrl)
  }
}

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

// Handle day indicator / scroll

const visibleDays = []
const observer = new IntersectionObserver((entries) => {
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

  let finalDayId = state.dayIntersectId
  let earliestTs = '9'
  for (const day of visibleDays) {
    if (day.ts < earliestTs) {
      finalDayId = day.id
      earliestTs = day.ts
    }
  }

  state.dayIntersectId = finalDayId.toString()
}, {
  root: null,
  rootMargin: '0px',
  threshold: [0.0, 1.0]
})

onMounted(() => {
  for (const mDay of meetingDays.value) {
    const el = document.getElementById(`agenda-day-${mDay.slug}`)
    el.dataset.dayId = mDay.slug.toString()
    el.dataset.dayTs = mDay.ts
    observer.observe(el)
  }
})

onBeforeUnmount(() => {
  for (const mDay of meetingDays.value) {
    observer.unobserve(document.getElementById(`agenda-day-${mDay.slug}`))
  }
})

function scrollToDay (dayId, ev) {
  ev.preventDefault()
  document.getElementById(`agenda-day-${dayId}`)?.scrollIntoView(true)
}

// CREATED

// -> Handle loading tab directly based on URL
if (window.location.pathname.indexOf('-utc') >= 0) {
  state.timezone = 'UTC'
} else if (window.location.pathname.indexOf('personalize') >= 0) {
  state.currentTab = 'personalize'
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

  &-quickaccess {
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
}
</style>
