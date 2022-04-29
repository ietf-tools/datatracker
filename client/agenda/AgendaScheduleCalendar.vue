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
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { DateTime } from 'luxon'
import {
  NButton,
  NButtonGroup,
  NDivider,
  NDrawer,
  NDrawerContent,
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
    console.info(ev)
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
      title: ev.name,
      classNames: [`event-area-${ev.groupParent.acronym}`]
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

  .fc-v-event {
    background: linear-gradient(to top, #333940, #525a62);
    border-color: #333940;
  }

  .event-area-art {
    background: rgba(204, 121, 167);
  }
  .event-area-gen {
    background: rgba(29, 78, 17);
  }
  .event-area-iab {
    background: rgba(255, 165, 0);
  }
  .event-area-int {
    background: rgba(132, 240, 240);
  }
  .event-area-irtf {
    background: rgba(154, 119, 230);
  }
  .event-area-ops {
    background: rgba(199, 133, 129);
  }
  .event-area-rtg {
    background: rgba(222, 219, 124);
  }
  .event-area-sec {
    background: rgba(0, 114, 178);
  }
  .event-area-tsv {
    background: rgba(117,201,119);
  }
}

</style>
