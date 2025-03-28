<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='state.drawerHeight')
  n-drawer-content.agenda-calendar
    template(#header)
      span Calendar View
      .agenda-calendar-actions
        template(v-if='siteStore.viewport > 990')
          i.bi.bi-globe.me-2
          small.me-2: strong Timezone:
          n-button-group
            n-button(
              :type='agendaStore.isTimezoneMeeting ? `primary` : `default`'
              @click='setTimezone(`meeting`)'
              :text-color='agendaStore.isTimezoneMeeting ? `#FFF` : null'
              ) Meeting
            n-button(
              :type='agendaStore.isTimezoneLocal ? `primary` : `default`'
              @click='setTimezone(`local`)'
              :text-color='agendaStore.isTimezoneLocal ? `#FFF` : null'
              ) Local
            n-button(
              :type='agendaStore.timezone === `UTC` ? `primary` : `default`'
              @click='setTimezone(`UTC`)'
              :text-color='agendaStore.timezone === `UTC` ? `#FFF` : null'
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
          :color='siteStore.theme === `dark` ? `#e35d6a` : `gray`'
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

import FullCalendar from '@fullcalendar/vue3'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import luxonPlugin from '@fullcalendar/luxon3'
import bootstrap5Plugin from '@fullcalendar/bootstrap5'

import AgendaDetailsModal from './AgendaDetailsModal.vue'

import { useAgendaStore } from './store'
import { useSiteStore } from '../shared/store'

// STORES

const agendaStore = useAgendaStore()
const siteStore = useSiteStore()

// STATE

const isShown = ref(false)
const state = reactive({
  drawerHeight: Math.round(window.innerHeight * .8),
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
  initialView: agendaStore.defaultCalendarView === 'day' ? 'timeGridDay' : 'timeGridWeek',
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

// WATCHERS

watch(() => agendaStore.calendarShown, (newValue) => {
  if (newValue) {
    state.drawerHeight = window.innerHeight > 1000 ? 960 : window.innerHeight - 30
    refreshData()
  }
  isShown.value = newValue
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
watch(() => agendaStore.defaultCalendarView, (newValue) => {
  calendarOptions.initialView = newValue === 'day' ? 'timeGridDay' : 'timeGridWeek'
})

// METHODS

function refreshData () {
  let earliestHour = 24
  let latestHour = 0
  let earliestDate = DateTime.fromISO('2200-01-01')
  let latestDate = DateTime.fromISO('1990-01-01')
  let nowDate = DateTime.now()
  let hasCrossDayEvents = false

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
    if (ev.adjustedStart.day !== ev.adjustedEnd.day) {
      hasCrossDayEvents = true
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
  calendarOptions.slotMinTime = hasCrossDayEvents ? '00:00:00' : `${earliestHour.toString().padStart(2, '0')}:00:00`
  calendarOptions.slotMaxTime = hasCrossDayEvents ? '23:59:59' : `${latestHour.toString().padStart(2, '0')}:00:00`
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
@import "../shared/breakpoints";

.agenda-calendar {
  .n-drawer-header {
    padding-top: 10px !important;
    padding-bottom: 10px !important;

    @media screen and (max-width: $bs5-break-sm) {
      padding-left: 10px !important;
      padding-right: 10px !important;
    }

    &__main {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;

      @media screen and (max-width: $bs5-break-sm) {
        justify-content: center;
        flex-wrap: wrap;
        font-size: .9em;
      }
    }
  }

  &-actions {
    @media screen and (max-width: $bs5-break-sm) {
      flex: 0 1 100%;
      margin-top: .75rem;
      display: flex;
      justify-content: center;
    }
  }

  .n-drawer-body-content-wrapper {
    @media screen and (max-width: $bs5-break-sm) {
      padding: 10px !important;
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
      font-size: .7em;
      border: 1px solid #CCC;
      text-transform: uppercase;
      font-weight: 700;
      margin-right: 10px;
    }
  }

  @media screen and (max-width: $bs5-break-sm) {
    .fc-toolbar.fc-header-toolbar {
      flex-wrap: wrap;

      .fc-toolbar-chunk:nth-child(2) {
        display: none;
      }

      .fc-toolbar-title {
        font-size: 1em;
        font-weight: 600;
        padding: 7px 0;
      }
    }
  }

  .fc-v-event {
    background-color: $gray-100;
    border: 1px solid #FFF;
    border-width: 0 1px 1px 0;
    border-radius: 0;
    background-image: linear-gradient(to bottom, $gray-100, $gray-200);
    padding-left: 3px;
    cursor: pointer;
    text-shadow: 1px 1px 0 rgba(255,255,255,.25);
    box-shadow: inset -1px -1px 0 $gray-500;

    &.fc-timegrid-event-short {
      .fc-event-title-container, .fc-event-time {
        display: flex;
        align-items: center;
      }
    }

    .fc-event-main {
      color: #333;

      .fc-event-title-container {
        font-size: .9em;
        font-weight: 500;
        line-height: .9em;
      }
    }
  }

  .event-area-art {
    box-shadow: inset -1px -1px 0 rgba(204, 121, 167);
    background-image: linear-gradient(to top, rgba(204, 121, 167, .3) 50%, rgba(204, 121, 167, .1));

    .fc-event-main {
      color: darken(rgba(204, 121, 167), 30%);
    }
  }
  .event-area-gen {
    box-shadow: inset -1px -1px 0 rgba(29, 78, 17);
    background-image: linear-gradient(to top, rgba(29, 78, 17, .3) 50%, rgba(29, 78, 17, .1));

    .fc-event-main {
      color: darken(rgba(29, 78, 17), 30%);
    }
  }
  .event-area-iab {
    box-shadow: inset -1px -1px 0 rgba(255, 165, 0);
    background-image: linear-gradient(to top, rgba(255, 165, 0, .3) 50%, rgba(255, 165, 0, .1));

    .fc-event-main {
      color: darken(rgba(255, 165, 0), 30%);
    }
  }
  .event-area-int {
    box-shadow: inset -1px -1px 0 rgba(132, 240, 240);
    background-image: linear-gradient(to top, rgba(132, 240, 240, .3) 50%, rgba(132, 240, 240, .1));

    .fc-event-main {
      color: darken(rgba(132, 240, 240), 40%);
    }
  }
  .event-area-irtf {
    box-shadow: inset -1px -1px 0 rgba(154, 119, 230);
    background-image: linear-gradient(to top, rgba(154, 119, 230, .3) 50%, rgba(154, 119, 230, .1));

    .fc-event-main {
      color: darken(rgba(154, 119, 230), 30%);
    }
  }
  .event-area-ops {
    box-shadow: inset -1px -1px 0 rgba(199, 133, 129);
    background-image: linear-gradient(to top, rgba(199, 133, 129, .3) 50%, rgba(199, 133, 129, .1));

    .fc-event-main {
      color: darken(rgba(199, 133, 129), 35%);
    }
  }
  .event-area-rtg {
    box-shadow: inset -1px -1px 0 rgba(222, 219, 124);
    background-image: linear-gradient(to top, rgba(222, 219, 124, .3) 50%, rgba(222, 219, 124, .1));

    .fc-event-main {
      color: darken(rgba(222, 219, 124), 50%);
    }
  }
  .event-area-sec {
    box-shadow: inset -1px -1px 0 rgba(0, 114, 178);
    background-image: linear-gradient(to top, rgba(0, 114, 178, .3) 50%, rgba(0, 114, 178, .1));

    .fc-event-main {
      color: darken(rgba(0, 114, 178), 10%);
    }
  }
  .event-area-tsv {
    box-shadow: inset -1px -1px 0 rgba(117,201,119);
    background-image: linear-gradient(to top, rgba(117,201,119, .3) 50%, rgba(117,201,119, .1));

    .fc-event-main {
      color: darken(rgba(117,201,119), 40%);
    }
  }
}

</style>
