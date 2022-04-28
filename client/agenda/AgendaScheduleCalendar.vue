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
  },
  slotMinTime: '06:00:00',
  slotMaxTime: '18:00:00'
  // initialDate: ''
})
const drawerHeight = Math.round(window.innerHeight * .8)

// COMPUTED

const calendarEvents = computed(
  () => props.events.value.map(ev => ({
    start: ev.adjustedStart.toJSDate(),
    end: ev.adjustedEnd.toJSDate(),
    title: ev.name
  }))
)

// WATCHERS

watch(() => props.shown, (newValue) => {
  isShown.value = newValue
})
watch(isShown, (newValue) => {
  emit('update:shown', newValue)
})

// METHODS

const close = () => {
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
