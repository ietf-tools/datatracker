<template lang="pug">
n-modal(v-model:show='modalShown')
  n-card.agenda-eventdetails(
    :bordered='false'
    segmented
    role='dialog'
    aria-modal='true'
    v-if='eventDetails'
    )
    template(#header-extra)
      .detail-header
        i.bi.bi-clock-history
        strong {{eventDetails.start}} - {{eventDetails.end}}
        n-button.ms-4.detail-close(
          ghost
          color='gray'
          strong
          @click='modalShown = false'
          )
          i.bi.bi-x
    template(#header)
      .detail-header
        i.bi.bi-calendar-check
        span {{eventDetails.day}}
    template(#action, v-if='eventDetails.showAgenda')
      .detail-action
        template(v-if='eventDetails.materialsUrl')
          n-button.me-2(
            ghost
            color='gray'
            strong
            :href='eventDetails.tarUrl'
            tag='a'
            aria-label='Download as tarball'
            )
            i.bi.bi-file-zip.me-2
            span Download as tarball
          n-button.me-2(
            ghost
            color='gray'
            strong
            :href='eventDetails.pdfUrl'
            tag='a'
            aria-label='Download as PDF'
            )
            i.bi.bi-file-pdf.me-2
            span Download as PDF
        n-button.me-2(
          ghost
          color='gray'
          strong
          :href='eventDetails.notepadUrl'
          tag='a'
          aria-label='Notepad'
          )
          i.bi.bi-journal-text.me-2 
          span Notepad
    .detail-content
      .detail-title
        h6
          i.bi.bi-arrow-right-square
          span {{eventDetails.title}}
        .detail-location
          i.bi.bi-geo-alt-fill
          n-popover(
            v-if='eventDetails.locationName'
            trigger='hover'
            )
            template(#trigger)
              span.badge {{eventDetails.locationShort}}
            span {{eventDetails.locationName}}
          span {{eventDetails.room}}
      .detail-text(v-if='eventDetails.materialsUrl')
        iframe(
          :src='eventDetails.materialsUrl'
          )
</template>

<script setup>
import { computed } from 'vue'
import {
  NButton,
  NCard,
  NModal,
  NPopover
} from 'naive-ui'

import { useAgendaStore } from './store'

// PROPS

const props = defineProps({
  shown: {
    type: Boolean,
    required: true,
    default: false
  },
  event: {
    type: Object,
    required: true
  }
})

// STORES

const agendaStore = useAgendaStore()

// EMIT

const emit = defineEmits(['update:shown'])

// COMPUTED

const eventDetails = computed(() => {

  if (!props.event) { return null }

  const materialsUrl = props.event.agenda?.url ? (new URL(props.event.agenda.url)).pathname : null

  return {
    start: props.event.adjustedStart?.toFormat('T'),
    end: props.event.adjustedEnd?.toFormat('T'),
    day: props.event.adjustedStart?.toFormat('DDDD'),
    locationShort: props.event.location?.short,
    locationName: props.event.location?.name,
    room: props.event.room,
    title: props.event.type === 'regular' ? `${props.event.groupName} (${props.event.acronym})` : props.event.name,
    showAgenda: props.event.flags.showAgenda,
    materialsUrl: materialsUrl,
    tarUrl: `/meeting/${agendaStore.meeting.number}/agenda/${props.event.acronym}-drafts.tgz`,
    pdfUrl: `/meeting/${agendaStore.meeting.number}/agenda/${props.event.acronym}-drafts.pdf`,
    notepadUrl: `https://notes.ietf.org/notes-ietf-${agendaStore.meeting.number}-${props.event.type === 'plenary' ? 'plenary' : props.event.acronym}`
  }
})

const modalShown = computed({
  get () {
    return props.shown
  },
  set(value) {
    emit('update:shown', value)
  }
})

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-eventdetails {
  width: 90vw;
  max-width: 1000px;

  .bi {
    font-size: 20px;
    color: $indigo;
  }

  .detail-header {
    font-size: 20px;
    display: flex;
    align-items: center;

    > .bi {
      margin-right: 12px;
    }
  }

  .detail-title {
    font-size: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;

    .bi {
      margin-right: 12px;
    }

    h6 {
      display: flex;
      align-items: center;
    }
  }

  .detail-close .bi {
    font-size: 20px;
    color: inherit;
  }

  .detail-location {
    display: flex;
    align-items: center;
    background-color: rgba($indigo, .05);
    padding: 5px 12px;
    border-radius: 5px;

    .badge {
      width: 30px;
      font-size: .7em;
      background-color: $yellow-200;
      border-bottom: 1px solid $yellow-500;
      border-right: 1px solid $yellow-500;
      color: $yellow-900;
      text-transform: uppercase;
      font-weight: 700;
      margin-right: 10px;
      text-shadow: 1px 1px $yellow-100;
    }
  }

  .detail-text {
    padding: 12px;
    background-color: #FAFAFA;
    color: #666;
    border: 1px solid #AAA;
    margin-top: 12px;
    border-radius: 5px;

    > iframe {
      width: 100%;
      height: 50vh;
      background-color: #FAFAFA;
      overflow: auto;
      border: none;
      border-radius: 5px;
      display: block;
    }
  }

  .detail-action {
    .bi {
      color: inherit;
      font-size: 16px;
    }
  }
}
</style>
