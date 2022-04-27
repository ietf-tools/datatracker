<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='650')
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
      span Test
      //- vue-cal.vuecal--blue-theme(
      //-   :disable-views='[`years`, `year`]'
      //-   :time-from='10 * 60'
      //-   :time-to='18 * 60'
      //-   hide-title-bar
      //-   hide-weekends
      //-   selected-date='2021-11-03'
      //-   :events='calendarEvents'
      //-   active-view='week'
      //-   style='height: 850px;'
      //-   )
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  useMessage
} from 'naive-ui'

// import VueCal from 'vue-cal'
// import 'vue-cal/dist/vuecal.css'

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
    display: flex;
    justify-content: stretch;
    align-items: stretch;
  }
}

</style>
