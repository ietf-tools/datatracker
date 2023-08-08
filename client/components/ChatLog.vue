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
  span.text-body-secondary(v-else)
    em No chat log available.
</template>
  
<script setup>
import { onMounted, reactive } from 'vue'
import { DateTime } from 'luxon'
import { emojify } from '@twuni/emojify'
import uniq from 'lodash-es/uniq'
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
    const authorNames = uniq(chatLog.map(l => l.author))

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

      // -> Format text
      let txt = emojify(logItem.text)
      if (txt.indexOf('@') >= 0) {
        for (const authorName of authorNames) {
          txt = txt.replaceAll(`@${authorName}`, `<span class="user-mention">${authorName}</span>`)
        }
      }
      txt = txt.replaceAll('href="/user_uploads/', 'href="https://zulip.ietf.org/user_uploads/')

      // -> Generate log item
      state.items.push({
        id: `logitem-${idx}`,
        color: authorColors[logItem.author],
        author: logItem.author,
        text: txt,
        time: DateTime.fromISO(logItem.time).toFormat('dd LLLL yyyy \'at\' HH:mm:ss a ZZZZ')
      })
      idx++
    }
  }
})
</script>

<style lang="scss">
@import '../shared/colors.scss';

.chatlog {
  .n-timeline-item-content__content {
    > div > p:last-child {
      margin-bottom: 0;
    }

    blockquote {
      background-color: $gray-100;
      border-radius: 5px;
      padding: 8px;
      margin-top: -8px;

      > p:last-child {
        margin-bottom: 0;
      }
    }

    .message_inline_image {
      display: none;
    }

    // Manual user mention
    .user-mention {
      display: inline-block;
      padding: 1px 5px;
      background-color: rgba($purple, .05);
      color: $purple;
      font-weight: 500;
      border-radius: 4px;

      > .user-mention {
        padding: 0;

        &::before {
          display: none;
        }
      }

      &::before {
        content: '@';
      }
    }

    // User reply mention
    .user-mention + a {
      text-decoration: none;
      color: $purple;
      font-style: italic;
      cursor: default;
    }
  }
}
</style>
