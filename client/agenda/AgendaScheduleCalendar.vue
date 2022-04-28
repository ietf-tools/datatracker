<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='drawerHeight')
  n-drawer-content.agenda-calendar
    template(#header)
      span Calendar View
      div
        n-button(
          ghost
          color='gray'
          strong
          @click='close'
          )
          i.bi.bi-x-square.me-2
          span Close
    .agenda-calendar-content
      full-calendar(:options='calendarOptions')
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { DateTime } from 'luxon'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  useMessage
} from 'naive-ui'

import '@fullcalendar/core/vdom' // solves problem with Vite
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
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
  }
})

// EMITS

const emit = defineEmits(['update:shown'])

// STATE

const isShown = ref(props.shown)
const calendarOptions = reactive({
  plugins: [ bootstrap5Plugin, dayGridPlugin, timeGridPlugin, interactionPlugin ],
  initialView: 'timeGridWeek',
  themeSystem: 'bootstrap5',
  slotEventOverlap: false,
  nowIndicator: true,
  headerToolbar: {
    left: 'timeGridWeek,timeGridDay',
    center: 'title',
    right: 'today prev,next'
  }
  // slotMinTime: '03:00:00',
  // slotMaxTime: '18:00:00'
  // initialDate: ''
})
const drawerHeight = Math.round(window.innerHeight * .8)

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
      title: ev.name
    }
  })

  // -> Display settings
  calendarOptions.slotMinTime = `${earliestHour.toString().padStart(2, '0')}:00:00`
  calendarOptions.slotMaxTime = `${latestHour.toString().padStart(2, '0')}:00:00`
  console.info(calendarOptions)
  // calendarOptions.scrollTime = `${earliestHour.toString().padStart(2, '0')}:00:00`

  // -> Initial date
  if (nowDate >= earliestDate && nowDate <= latestDate) {
    calendarOptions.initialDate = nowDate.toJSDate()
  } else {
    calendarOptions.initialDate = earliestDate.toJSDate()
  }
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
  }
}

</style>
