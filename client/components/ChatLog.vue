<template lang="pug">
.chatlog
  n-timeline(
    v-if='state.items.length > 0'
    :icon-size='18'
    size='large'
    )
    n-timeline-item(
      v-for='item of state.items'
      :key='item.id'
      type='default'
      :color='item.color'
      :title='item.author'
      :time='item.time'
      )
      template(#default)
        div(v-html='item.text')
  span.text-muted(v-else)
    em No chat log available.
</template>
  
<script setup>
import { onMounted, reactive } from 'vue'
import { DateTime } from 'luxon'
import {
  NTimeline,
  NTimelineItem
} from 'naive-ui'

// PROPS

const props = defineProps({
  componentId: {
    type: String,
    required: true
  }
})

// STATE

const state = reactive({
  items: []
})

// bs5 colors
const colors = [
  '#0d6efd',
  '#dc3545',
  '#20c997',
  '#6f42c1',
  '#fd7e14',
  '#198754',
  '#0dcaf0',
  '#d63384',
  '#ffc107',
  '#6610f2',
  '#adb5bd'
]

// MOUNTED

onMounted(() => {
  const authorColors = {}
  // Get chat log data from embedded json tag
  const chatLog = JSON.parse(document.getElementById(`${props.componentId}-data`).textContent || '[]')
  if (chatLog.length > 0) {
    let idx = 1
    let colorIdx = 0
    for (const logItem of chatLog) {
      // -> Get unique color per author
      if (!authorColors[logItem.author]) {
        authorColors[logItem.author] = colors[colorIdx]
        colorIdx++
        if (colorIdx >= colors.length) {
          colorIdx = 0
        }
      }
      // -> Generate log item
      state.items.push({
        id: `logitem-${idx}`,
        color: authorColors[logItem.author],
        author: logItem.author,
        text: logItem.text,
        time: DateTime.fromISO(logItem.time).toFormat('dd LLLL yyyy \'at\' HH:mm:ss a ZZZZ')
      })
      idx++
    }
  }
})
</script>

<style lang="scss">
.chatlog {
  .n-timeline-item-content__content > div > p {
    margin-bottom: 0;
  }
}
</style>
