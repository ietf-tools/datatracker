<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='250')
  n-drawer-content.agenda-downloadics
    template(#header)
      div
        span Download as .ics
        div(style='font-size: 11px; margin-top: 6px; color: #777;') Select the categories to include in the calendar (.ics) file.
      div
        n-button.me-2(
          ghost
          color='gray'
          strong
          @click='close'
          )
          i.bi.bi-x-square.me-2
          span Close
        n-button(
          primary
          type='primary'
          strong
          @click='download'
          )
          i.bi.bi-download.me-2
          span Download
    .agenda-downloadics-content
      .agenda-downloadics-grcat(
        v-for='(grcat, idx) of props.categories'
        :key='`grcat-` + idx'
        :class='`test-` + idx'
        )
        template(
          v-for='cat of grcat'
          :key='cat.keyword'
          )
          button(
            v-if='cat.keyword'
            @click='toggleCat(cat.keyword, cat.children)'
            :class='currentSelection.includes(cat.keyword) ? `is-selected` : ``'
            )
            i.bi.bi-grid-fill.me-2
            span {{cat.label}}
          button(
            v-else
            @click='toggleCat(`nonarea`, cat.children)'
            :class='currentSelection.includes(`nonarea`) ? `is-selected` : ``'
            )
            i.bi.bi-grid-fill.me-2
            span Non-Area Events
</template>

<script setup>
import { ref, toRefs, watch } from 'vue'
import difference from 'lodash/difference'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  useMessage
} from 'naive-ui'

// PROPS

const props = defineProps({
  shown: {
    type: Boolean,
    required: true,
    default: false
  },
  categories: {
    type: Array,
    required: true
  },
  meetingNumber: {
    type: String,
    required: true
  }
})

// EMITS

const emit = defineEmits(['update:shown'])

// STATE

const isShown = ref(props.shown)
const currentSelection = ref([])
const currentSubs = ref([])
const message = useMessage()

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

const download = () => {
  if (currentSubs.value.length > 0) {
    window.location.assign(`/meeting/${props.meetingNumber.value}/agenda.ics?show=${currentSubs.value.join(',')}`)
  } else {
    window.location.assign(`/meeting/${props.meetingNumber.value}/agenda.ics`)
  }
  message.loading('Generating calendar file... Download will begin shortly.')
  emit('update:shown', false)
  isShown.value = false
}

const toggleCat = (catKeyword, children) => {
  if (!currentSelection.value.includes(catKeyword)) {
    currentSelection.value = [...currentSelection.value, catKeyword]
    currentSubs.value = [...currentSubs.value, ...children.map(c => c.keyword)]
  } else {
    currentSelection.value = currentSelection.value.filter(c => c !== catKeyword)
    currentSubs.value = difference(currentSubs.value, children.map(c => c.keyword))
  }
}
</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-downloadics {
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

  &-grcat {
    flex: 1 1;
    background-color: $gray-200;
    padding: 10px;
    border-radius: 10px;
    margin-left: 10px;
    display: flex;
    justify-content: stretch;
    flex-wrap: wrap;

    &:first-child {
      margin-left: 0;
    }

    &:nth-child(2) {
      background-color: $teal-100;

      .agenda-downloadics-catmain {
        button {
          color: $teal-600;
        }
      }
    }
    &:nth-child(3) {
      background-color: $orange-100;

      .agenda-downloadics-catmain {
        button {
          color: $orange-600;
        }
      }
    }

    button {
      border-radius: 5px;
      border: 1px solid #FFF;
      background-color: #FFF;
      color: $gray-600;
      margin: 3px;
      box-shadow: 1px 1px 0px 0px rgba(0,0,0,.1);
      transition: background-color .5s ease;
      position: relative;
      padding: 12px;

      &:hover {
        background-color: rgba(255,255,255,.4);
      }

      &:active {
        box-shadow: none;
        background-color: #FFF;
      }

      &.is-selected {
        background: #444 linear-gradient(to bottom, #555, #444);
        color: #FFF;
      }
    }
  }
}
</style>
