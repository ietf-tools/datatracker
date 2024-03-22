<template lang="pug">
.polls
  n-data-table(
    v-if='state.items.length > 0'
    :data='state.items'
    :columns='state.columns'
    striped
    )
  span.text-danger(v-else-if='state.errMessage')
    em {{ state.errMessage }}
  span.text-body-secondary(v-else)
    em No polls available.
</template>
  
<script setup>
import { onMounted, reactive } from 'vue'
import { DateTime } from 'luxon'
import { cloneDeep, startCase } from 'lodash-es'
import { NDataTable } from 'naive-ui'

// PROPS

const props = defineProps({
  componentId: {
    type: String,
    required: true
  }
})

// STATE

const state = reactive({
  items: [],
  colums: [],
  errMessage: null
})

const defaultColumns = [
  {
    title: 'Question',
    key: 'text'
  },
  {
    title: 'Start Time',
    key: 'start_time',
  },
  {
    title: 'End Time',
    key: 'end_time'
  }
]

// MOUNTED

onMounted(() => {
  // Get polls from embedded json tag
  try {
    const polls = JSON.parse(document.getElementById(`${props.componentId}-data`).textContent || '[]')
    if (polls.length > 0) {
      // Populate columns
      state.columns = cloneDeep(defaultColumns)
      for (const col in polls[0]) {
        if (!['text', 'start_time', 'end_time'].includes(col)) {
          state.columns.push({
            title: startCase(col),
            key: col,
            minWidth: 100,
            titleAlign: 'center',
            align: 'center'
          })
        }
      }

      // Populate rows
      let idx = 1
      for (const poll of polls) {
        state.items.push({
          ...poll,
          id: `poll-${idx}`,
          start_time: DateTime.fromISO(poll.start_time).toFormat('dd LLLL yyyy \'at\' HH:mm:ss a ZZZZ'),
          end_time: DateTime.fromISO(poll.end_time).toFormat('dd LLLL yyyy \'at\' HH:mm:ss a ZZZZ')
        })
        idx++
      }
    }
  } catch (err) {
    console.warn(err)
    state.errMessage = 'Failed to load poll results.'
  }
})
</script>

