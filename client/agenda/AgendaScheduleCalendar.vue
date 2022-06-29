<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='drawerHeight')
  n-drawer-content.agenda-calendar
    template(#header)
      span Calendar View
      div
        template(v-if='agendaStore.viewport > 990')
          i.bi.bi-globe.me-2
          small.me-2: strong Timezone:
          n-button-group
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
          n-divider(vertical)
        n-button.me-2(
          ghost
          type='success'
          strong
          @click='toggleFilterDrawer'
          )
          i.bi.bi-funnel.me-2
          span Filter Areas + Groups...
          n-badge.ms-2(:value='agendaStore.selectedCatSubs.length', processing)
        n-button(
          ghost
          color='gray'
          strong
          @click='close'
          )
          i.bi.bi-x-square.me-2
          span Close
    .agenda-calendar-content
      .agenda-calendar-hint(v-if='!agendaStore.isMobile')
        template(v-if='state.hoverMessage')
          div
            i.bi.bi-arrow-right-square.me-2
            span {{state.hoverMessage}}
          div(v-if='state.hoverLocationRoom')
            i.bi.bi-geo-alt-fill.me-2
            n-popover(
              v-if='state.hoverLocationName'
              trigger='hover'
              )
              template(#trigger)
                span.badge.me-2 {{state.hoverLocationShort}}
              span {{state.hoverLocationName}}
            span {{state.hoverLocationRoom}}
          div
            i.bi.bi-clock-history.me-2
            span {{state.hoverTime}}
        span(v-else) #[strong Mouse over] a session to display quick info or #[strong click] to view the meeting materials and details.
      full-calendar(
        :options='calendarOptions'
        )
      agenda-details-modal(
        v-model:shown='state.showEventDetails'
        :event='state.eventDetails'
      )
      
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { DateTime } from 'luxon'
import {
  NBadge,
  NButton,
  NButtonGroup,
  NDivider,
  NDrawer,
  NDrawerContent,
  NPopover
} from 'naive-ui'

import '@fullcalendar/core/vdom' // solves problem with Vite
import FullCalendar from '@fullcalendar/vue3'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import luxonPlugin from '@fullcalendar/luxon2'
import bootstrap5Plugin from '@fullcalendar/bootstrap5'

import AgendaDetailsModal from './AgendaDetailsModal.vue'

import { useAgendaStore } from './store'

// STORES

const agendaStore = useAgendaStore()

// STATE

const isShown = ref(false)
const state = reactive({
  hoverMessage: '',
  hoverTime: '',
  hoverLocationRoom: '',
  hoverLocationName: '',
  hoverLocationShort: '',
  showEventDetails: false,
  eventDetails: {
    start: '00:00',
    end: '00:00'
  }
})
const calendarOptions = reactive({
  plugins: [ bootstrap5Plugin, timeGridPlugin, interactionPlugin, luxonPlugin ],
  initialView: 'timeGridWeek',
  themeSystem: 'bootstrap5',
  timeZone: agendaStore.timezone,
  slotEventOverlap: false,
  nowIndicator: true,
  headerToolbar: {
    left: 'timeGridWeek,timeGridDay',
    center: 'title',
    right: 'today prev,next'
  },
  allDaySlot: false,
  validRange: {
    start: null,
    end: null
  },
  expandRows: true,
  height: '100%',
  eventTimeFormat: {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  },
  eventClick: (info) => {
    state.eventDetails = info.event.extendedProps
    state.showEventDetails = true
  },
  eventMouseEnter: (info) => {
    const timeStart = info.event.extendedProps.adjustedStart?.toFormat('T')
    const timeEnd = info.event.extendedProps.adjustedEnd?.toFormat('T')
    const timeDay = info.event.extendedProps.adjustedStart?.toFormat('DDDD')
    state.hoverMessage = info.event.title
    state.hoverTime = `${timeDay} from ${timeStart} to ${timeEnd}`
    state.hoverLocationShort = info.event.extendedProps.location?.short
    state.hoverLocationName = info.event.extendedProps.location?.name
    state.hoverLocationRoom = info.event.extendedProps.room
  }
})
const drawerHeight = Math.round(window.innerHeight * .8)

// WATCHERS

watch(() => agendaStore.calendarShown, (newValue) => {
  isShown.value = newValue
  if (newValue) {
    refreshData()
  }
})
watch(isShown, (newValue) => {
  agendaStore.$patch({ calendarShown: newValue })
})
watch(() => agendaStore.scheduleAdjusted, () => {
  refreshData()
})
watch(() => agendaStore.timezone, (newValue) => {
  calendarOptions.timeZone = newValue
  state.hoverMessage = ''
})

// METHODS

function refreshData () {
  let earliestHour = 24
  let latestHour = 0
  let earliestDate = DateTime.fromISO('2200-01-01')
  let latestDate = DateTime.fromISO('1990-01-01')
  let nowDate = DateTime.now()

  calendarOptions.events = agendaStore.scheduleAdjusted.map(ev => {
    // -> Determine boundaries
    if (ev.adjustedStart.hour < earliestHour) {
      earliestHour = ev.adjustedStart.hour
    }
    if (ev.adjustedEnd.hour > latestHour) {
      latestHour = ev.adjustedEnd.hour
    }
    if (ev.adjustedStart < earliestDate) {
      earliestDate = ev.adjustedStart
    }
    if (ev.adjustedEnd < latestDate) {
      latestDate = ev.adjustedEnd
    }
    // -> Build event object
    return {
      id: ev.id,
      start: ev.adjustedStart.toJSDate(),
      end: ev.adjustedEnd.toJSDate(),
      title: ev.type === 'regular' ? `${ev.groupName} (${ev.acronym})` : ev.name,
      classNames: [`event-area-${ev.groupParent.acronym}`],
      extendedProps: ev
    }
  })

  // -> Display settings
  calendarOptions.slotMinTime = `${earliestHour.toString().padStart(2, '0')}:00:00`
  calendarOptions.slotMaxTime = `${latestHour.toString().padStart(2, '0')}:00:00`
  calendarOptions.validRange.start = earliestDate.minus({ days: 1 }).toISODate()
  calendarOptions.validRange.end = latestDate.plus({ days: 1 }).toISODate()
  // calendarOptions.scrollTime = `${earliestHour.toString().padStart(2, '0')}:00:00`

  // -> Initial date
  if (nowDate >= earliestDate && nowDate <= latestDate) {
    calendarOptions.initialDate = nowDate.toJSDate()
  } else {
    calendarOptions.initialDate = earliestDate.toJSDate()
  }
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

function toggleFilterDrawer () {
  agendaStore.$patch({ filterShown: true })
}

function close () {
  isShown.value = false
  state.hoverMessage = ''
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-calendar {
  .n-drawer-header {
    padding-top: 10px !important;
    padding-bottom: 10px !important;

    &__main {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
    }
  }

  &-content {
    height: 100%;
    padding-bottom: 15px;
  }

  &-hint {
    position: absolute;
    display: block;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: rgba(0,0,0,.7);
    color: #FFF;
    font-size: 12px;
    font-weight: 500;
    padding: 5px 25px;
    z-index: 10;
    display: flex;
    justify-content: space-between;

    > div {
      flex: 1 1 33%;
    }

    > span strong {
      color: $blue-200;
    }

    .badge {
      width: 30px;
      font-size: .7em;
      border: 1px solid #CCC;
      text-transform: uppercase;
      font-weight: 700;
      margin-right: 10px;
    }
  }

  .fc-v-event {
    background-color: #333940;
    border: 1px solid #333940;
    border-left-width: 5px;
    background-image: linear-gradient(to top, #333940, #525a62);
    padding-left: 5px;
    cursor: pointer;
  }

  .event-area-art {
    border-color: rgba(204, 121, 167);
    background-image: linear-gradient(to top, rgba(204, 121, 167, .35), rgba(204, 121, 167, 0));
  }
  .event-area-gen {
    border-color: rgba(29, 78, 17);
    background-image: linear-gradient(to top, rgba(29, 78, 17, .35), rgba(29, 78, 17, 0));
  }
  .event-area-iab {
    border-color: rgba(255, 165, 0);
    background-image: linear-gradient(to top, rgba(255, 165, 0, .35), rgba(255, 165, 0, 0));
  }
  .event-area-int {
    border-color: rgba(132, 240, 240);
    background-image: linear-gradient(to top, rgba(132, 240, 240, .35), rgba(132, 240, 240, 0));
  }
  .event-area-irtf {
    border-color: rgba(154, 119, 230);
    background-image: linear-gradient(to top, rgba(154, 119, 230, .35), rgba(154, 119, 230, 0));
  }
  .event-area-ops {
    border-color: rgba(199, 133, 129);
    background-image: linear-gradient(to top, rgba(199, 133, 129, .35), rgba(199, 133, 129, 0));
  }
  .event-area-rtg {
    border-color: rgba(222, 219, 124);
    background-image: linear-gradient(to top, rgba(222, 219, 124, .35), rgba(222, 219, 124, 0));
  }
  .event-area-sec {
    border-color: rgba(0, 114, 178);
    background-image: linear-gradient(to top, rgba(0, 114, 178, .35), rgba(0, 114, 178, 0));
  }
  .event-area-tsv {
    border-color: rgba(117,201,119);
    background-image: linear-gradient(to top, rgba(117,201,119, .35), rgba(117,201,119, 0));
  }
}

</style>
