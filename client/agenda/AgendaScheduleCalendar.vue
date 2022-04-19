<template lang="pug">
vue-cal.vuecal--blue-theme(
  :disable-views='[`years`, `year`]'
  :time-from='10 * 60'
  :time-to='18 * 60'
  hide-title-bar
  hide-weekends
  selected-date='2021-11-03'
  :events='calendarEvents'
  active-view='week'
  style='height: 850px;'
  )
</template>

<script>
import { computed, toRefs } from 'vue'

import VueCal from 'vue-cal'
import 'vue-cal/dist/vuecal.css'

export default {
  components: {
    VueCal
  },
  props: {
    events: {
      type: Array,
      required: true
    }
  },
  setup (props) {
    const { events } = toRefs(props)

    const calendarEvents = computed(
      () => events.value.map(ev => ({
        start: ev.adjustedStart.toJSDate(),
        end: ev.adjustedEnd.toJSDate(),
        title: ev.name
      }))
    )

    return {
      calendarEvents
    }
  }
}
</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

</style>
