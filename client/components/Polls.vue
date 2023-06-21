<template lang="pug">
.polls
  n-data-table(
    v-if='state.items.length > 0'
    :data='state.items'
    :columns='columns'
    striped
    )
  span.text-body-secondary(v-else)
    em No polls available.
</template>
  
<script setup>
import { onMounted, reactive } from 'vue'
import { DateTime } from 'luxon'
import {
  NDataTable
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

const columns = [
  {
    title: 'Question',
    key: 'question'
  },
  {
    title: 'Start Time',
    key: 'start_time',
  },
  {
    title: 'End Time',
    key: 'end_time'
  },
  {
    title: 'Raise Hand',
    key: 'raise_hand'
  },
  {
    title: 'Do Not Raise Hand',
    key: 'do_not_raise_hand'
  }
]

// MOUNTED

onMounted(() => {
  // Get polls from embedded json tag
  const polls = JSON.parse(document.getElementById(`${props.componentId}-data`).textContent || '[]')
  if (polls.length > 0) {
    let idx = 1
    for (const poll of polls) {
      state.items.push({
        id: `poll-${idx}`,
        question: poll.text,
        start_time: DateTime.fromISO(poll.start_time).toFormat('dd LLLL yyyy \'at\' HH:mm:ss a ZZZZ'),
        end_time: DateTime.fromISO(poll.end_time).toFormat('dd LLLL yyyy \'at\' HH:mm:ss a ZZZZ'),
        raise_hand: poll.raise_hand,
        do_not_raise_hand: poll.do_not_raise_hand
      })
      idx++
    }
  }
})
</script>

