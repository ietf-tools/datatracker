<template lang="pug">
n-modal(v-model:show='modalShown')
  n-card.agenda-share(
    :bordered='false'
    segmented
    role='dialog'
    aria-modal='true'
    )
    template(#header-extra)
      .agenda-share-header
        n-button.ms-4.agenda-share-close(
          ghost
          color='gray'
          strong
          @click='modalShown = false'
          )
          i.bi.bi-x
    template(#header)
      .agenda-share-header
        i.bi.bi-share
        span Share this view
    .agenda-share-content
      .text-body-secondary.pb-2 Use the following URL for sharing the current view #[em (including any active filters)] with other users:
      n-input-group
        n-input(
          ref='filteredUrlIpt'
          size='large'
          readonly 
          v-model:value='state.filteredUrl'
          )
        n-button(
          type='primary'
          primary
          strong
          size='large'
          @click='copyFilteredUrl'
          )
          template(#icon)
            i.bi.bi-clipboard-check.me-1
          span Copy
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { find } from 'lodash-es'
import {
  NButton,
  NCard,
  NModal,
  NInputGroup,
  NInput,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'

// PROPS

const props = defineProps({
  shown: {
    type: Boolean,
    required: true,
    default: false
  }
})

// MESSAGE PROVIDER

const message = useMessage()

// STORES

const agendaStore = useAgendaStore()

// EMIT

const emit = defineEmits(['update:shown'])

// STATE

const state = reactive({
  isLoading: false,
  filteredUrl: window.location.href
})
const filteredUrlIpt = ref(null)

// COMPUTED

const modalShown = computed({
  get () {
    return props.shown
  },
  set(value) {
    emit('update:shown', value)
  }
})

// WATCHERS

watch(() => props.shown, (newValue) => {
  if (newValue) {
    generateUrl()
  }
})

// METHODS

function generateUrl () {
  const newUrl = new URL(window.location.href)
  const queryParams = []
  if (agendaStore.selectedCatSubs.length > 0 ) {
    queryParams.push(`filters=${agendaStore.selectedCatSubs.join(',')}`)
  }
  if (agendaStore.pickerMode && agendaStore.pickedEvents.length > 0 ) {
    const kwds = []
    for (const id of agendaStore.pickedEvents) {
      const session = find(agendaStore.scheduleAdjusted, ['id', id])
      if (session) {
        const suffix = session.sessionToken ? `-${session.sessionToken}` : ''
        kwds.push(`${session.acronym}${suffix}`)
      }
    }
    queryParams.push(`show=${kwds.join(',')}`)
  }
  newUrl.search = queryParams.length > 0 ? `?${queryParams.join('&')}` : ''
  state.filteredUrl = newUrl.toString()
}

async function copyFilteredUrl () {
  filteredUrlIpt.value?.select()

  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(state.filteredUrl)
    } else {
      if (!document.execCommand('copy')) {
        throw new Error('Copy failed')
      }
    }
    message.success('URL copied to clipboard successfully.')
  } catch (err) {
    message.error('Failed to copy URL to clipboard.')
  }
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-share {
  width: 90vw;
  max-width: 1000px;

  &-header {
    font-size: 20px;
    display: flex;
    align-items: center;

    > .bi {
      margin-right: 12px;
      font-size: 20px;
      color: $indigo;
    }
  }

  &-close .bi {
    font-size: 20px;
    color: inherit;
  }
}
</style>
