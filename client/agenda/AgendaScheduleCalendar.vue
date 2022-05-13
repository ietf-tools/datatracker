<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='drawerHeight')
  n-drawer-content.agenda-calendar
    template(#header)
      span Calendar View
      div
        i.bi.bi-globe.me-2
        small.me-2: strong Timezone:
        n-button-group
          n-button(
            :type='isTimezoneMeeting ? `primary` : `default`'
            @click='setTimezone(`meeting`)'
            ) Meeting
          n-button(
            :type='isTimezoneLocal ? `primary` : `default`'
            @click='setTimezone(`local`)'
            ) Local
          n-button(
            :type='props.timezone === `UTC` ? `primary` : `default`'
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
        n-button(
          ghost
          color='gray'
          strong
          @click='close'
          )
          i.bi.bi-x-square.me-2
          span Close
    .agenda-calendar-content
      full-calendar(
        :options='calendarOptions'
        )
      n-modal(v-model:show='state.showEventDetails')
        n-card.agenda-calendar-eventdetails(
          :bordered='false'
          segmented
          role='dialog'
          aria-modal='true'
          v-if='state.eventDetails'
          )
          template(#header-extra)
            .detail-header
              i.bi.bi-clock-history
              strong {{state.eventDetails.start}} - {{state.eventDetails.end}}
              n-button.ms-4.detail-close(
                ghost
                color='gray'
                strong
                @click='state.showEventDetails = false'
                )
                i.bi.bi-x
          template(#header)
            .detail-header
              i.bi.bi-calendar-check
              span {{state.eventDetails.day}}
          template(#action)
            .detail-action
              n-button.me-2(
                ghost
                color='gray'
                strong 
                )
                i.bi.bi-collection.me-2
                span Meeting Materials
              n-button.me-2(
                ghost
                color='gray'
                strong 
                )
                i.bi.bi-journal-text.me-2 
                span Notepad
          .detail-content
            .detail-title
              h6
                i.bi.bi-arrow-right-square
                span {{state.eventDetails.title}}
              .detail-location
                i.bi.bi-geo-alt-fill
                n-popover(
                  v-if='state.eventDetails.locationName'
                  trigger='hover'
                  )
                  template(#trigger)
                    span.badge {{state.eventDetails.locationShort}}
                  span {{state.eventDetails.locationName}}
                span {{state.eventDetails.room}}
            .detail-text
              iframe(
                src='/meeting/106/materials/agenda-106-wpack-06'
                )
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { DateTime } from 'luxon'
import {
  NButton,
  NButtonGroup,
  NCard,
  NDivider,
  NDrawer,
  NDrawerContent,
  NModal,
  NPopover,
  useMessage
} from 'naive-ui'

import '@fullcalendar/core/vdom' // solves problem with Vite
import FullCalendar from '@fullcalendar/vue3'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import luxonPlugin from '@fullcalendar/luxon2'
import bootstrap5Plugin from '@fullcalendar/bootstrap5'

// PROPS

const props = defineProps({
  shown: {
    type: Boolean,
    required: true,
    default: false
  },
  events: {
    type: Array,
    required: true
  },
  timezone: {
    type: String,
    required: true
  },
  meetingTimezone: {
    type: String,
    required: true
  }
})

// EMITS

const emit = defineEmits(['update:shown', 'update:timezone', 'toggleFilterDrawer'])

// STATE

const isShown = ref(props.shown)
const state = reactive({
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
  timeZone: props.timezone,
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
  height: 'auto',
  eventTimeFormat: {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  },
  eventClick: (info) => {
    const ev = info.event.extendedProps
    state.eventDetails = {
      start: ev.adjustedStart.toFormat('T'),
      end: ev.adjustedEnd.toFormat('T'),
      day: ev.adjustedStart.toFormat('DDDD'),
      locationShort: ev.location?.short,
      locationName: ev.location?.name,
      room: ev.room,
      title: info.event.title
    }
    state.showEventDetails = true
  }
})
const drawerHeight = Math.round(window.innerHeight * .8)

// COMPUTED

const isTimezoneLocal = computed(() => {
  return props.timezone === DateTime.local().zoneName
})
const isTimezoneMeeting = computed(() => {
  return props.timezone === props.meetingTimezone
})

// WATCHERS

watch(() => props.shown, (newValue) => {
  isShown.value = newValue
  if (newValue) {
    refreshData()
  }
})
watch(isShown, (newValue) => {
  emit('update:shown', newValue)
})
watch(() => props.events, () => {
  refreshData()
})
watch(() => props.timezone, (newValue) => {
  calendarOptions.timeZone = newValue
})

// METHODS

function refreshData () {
  let earliestHour = 24
  let latestHour = 0
  let earliestDate = DateTime.fromISO('2200-01-01')
  let latestDate = DateTime.fromISO('1990-01-01')
  let nowDate = DateTime.now()

  calendarOptions.events = props.events.map(ev => {
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
      emit('update:timezone', props.meetingTimezone)
      break
    case 'local':
      emit('update:timezone', DateTime.local().zoneName)
      break
    default:
      emit('update:timezone', tz)
      break
  }
}

function toggleFilterDrawer () {
  emit('toggleFilterDrawer')
}

function close () {
  emit('update:shown', false)
  isShown.value = false
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
  }

  &-eventdetails {
    width: 90vw;
    max-width: 1000px;

    .bi {
      font-size: 20px;
      color: $indigo;
    }

    .detail-header {
      font-size: 20px;
      display: flex;
      align-items: center;

      > .bi {
        margin-right: 12px;
      }
    }

    .detail-title {
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;

      .bi {
        margin-right: 12px;
      }

      h6 {
        display: flex;
        align-items: center;
      }
    }

    .detail-close .bi {
      font-size: 20px;
      color: inherit;
    }

    .detail-location {
      display: flex;
      align-items: center;
      background-color: rgba($indigo, .05);
      padding: 5px 12px;
      border-radius: 5px;

      .badge {
        width: 30px;
        font-size: .7em;
        background-color: $yellow-200;
        border-bottom: 1px solid $yellow-500;
        border-right: 1px solid $yellow-500;
        color: $yellow-900;
        text-transform: uppercase;
        font-weight: 700;
        margin-right: 10px;
        text-shadow: 1px 1px $yellow-100;
      }
    }

    .detail-text {
      padding: 12px;
      background-color: #333940;
      color: #FFF;
      margin-top: 12px;
      border-radius: 5px;

      > iframe {
        width: 100%;
        min-height: 300px;
        background-color: #333940;
        overflow: auto;
        border: none;
      }
    }

    .detail-action {
      .bi {
        color: inherit;
        font-size: 16px;
      }
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
