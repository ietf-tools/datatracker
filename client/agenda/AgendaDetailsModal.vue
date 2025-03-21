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
        n-button.float-end(
          ghost
          color='gray'
          strong
          tag='a'
          :href='eventDetails.detailsUrl'
          target='_blank'
          aria-label='Materials page'
        )
          span.me-2 {{props.event.groupAcronym}} materials page
          i.bi.bi-box-arrow-up-right
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
      nav.detail-nav.nav.nav-pills.nav-justified.mt-3
        a.nav-link(
          :class='{ active: state.tab === `agenda` }'
          @click='state.tab = `agenda`'
          )
          i.bi.bi-list-columns-reverse.me-2
          span Agenda
        a.nav-link(
          :class='{ active: state.tab === `slides` }'
          @click='state.tab = `slides`'
          )
          i.bi.bi-easel.me-2
          span Slides
        a.nav-link(
          :class='{ active: state.tab === `minutes` }'
          @click='state.tab = `minutes`'
          )
          i.bi.bi-journal-text.me-2
          span Minutes
      .detail-text(v-if='eventDetails.materialsUrl')
        template(v-if='state.tab === `agenda`')
          iframe(
            :src='eventDetails.materialsUrl'
            )
        template(v-else-if='state.tab === `slides`')
          n-card(
            :bordered='false'
            size='small'
            )
            .text-center(v-if='state.isLoading')
              n-spin(description='Loading slides...')
            .text-center.p-3(v-else-if='!state.materials || !state.materials.slides || !state.materials.slides.decks || state.materials.slides.decks.length < 1')
              span No slides submitted for this session.
            .list-group(v-else)
              a.list-group-item(
                v-for='deck of state.materials.slides.decks'
                :key='deck.id'
                :href='deck.url'
                target='_blank'
                )
                i.bi.me-2(:class='`bi-filetype-` + deck.ext')
                span {{deck.title}}
            template(#action, v-if='state.materials.slides.actions')
                n-button(
                  v-for='action of state.materials.slides.actions'
                  tag='a'
                  :href='action.url'
                  ) {{action.label}}
        template(v-else)
          .text-center(v-if='state.isLoading')
            n-spin(description='Loading minutes...')
          .text-center.p-3(v-else-if='!state.materials || !state.materials.minutes')
            span No minutes submitted for this session.
          iframe(
            v-else
            :src='state.materials.minutes.url'
            )
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import {
  NButton,
  NCard,
  NModal,
  NPopover,
  NSpin,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'
import { getUrl } from '../shared/urls'

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

// MESSAGE PROVIDER

const message = useMessage()

// STORES

const agendaStore = useAgendaStore()

// EMIT

const emit = defineEmits(['update:shown'])

// STATE

const state = reactive({
  tab: 'agenda',
  isLoading: false,
  materials: {}
})

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
    detailsUrl: getUrl('meetingDetails', {
      meetingNumber: agendaStore.meeting.number,
      eventAcronym: props.event.acronym
    }),
    tarUrl: getUrl('meetingMaterialsTar', {
      meetingNumber: agendaStore.meeting.number,
      eventAcronym: props.event.acronym
    }),
    pdfUrl: getUrl('meetingMaterialsPdf', {
      meetingNumber: agendaStore.meeting.number,
      eventAcronym: props.event.acronym
    }),
    notepadUrl: getUrl('meetingNotes', {
      meetingNumber: agendaStore.meeting.number,
      eventAcronym: props.event.type === 'plenary' ? 'plenary' : props.event.acronym
    })
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

// WATCHERS

watch(() => props.shown, (newValue) => {
  if (newValue) {
    state.materials = {}
    state.tab = 'agenda'
    if (props.event.flags.showAgenda) {
      fetchSessionMaterials()
    }
  }
})

// METHODS

async function fetchSessionMaterials () {
  if (!props.event) { return null }

  state.isLoading = true

  try {
    const resp = await fetch(
        `/api/meeting/session/${props.event.sessionId}/materials`,
        { credentials: 'include' }
    )
    if (!resp.ok) {
      throw new Error(resp.statusText)
    }
    state.materials = await resp.json()
  } catch (err) {
    console.warn(err)
    message.error('Failed to fetch session materials.')
  }
  state.isLoading = false
}

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

    @at-root .theme-dark & {
      color: $indigo-300;
    }
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

  nav.detail-nav {
    padding: 5px;
    background-color: #FFF;
    border: 1px solid $gray-300;
    border-radius: 5px;
    font-weight: 500;

    @at-root .theme-dark & {
      background-color: $gray-900;
      border-color: $gray-700;
    }

    a {
      cursor: pointer;

      .bi {
        font-size: inherit;
        color: inherit;
      }

      &:not(.active):hover {
        background-color: rgba($blue-100, .25);
      }
    }
  }

  .detail-text {
    padding: 12px;
    background-color: #FAFAFA;
    color: #666;
    border: 1px solid #AAA;
    margin-top: 12px;
    border-radius: 5px;

    @at-root .theme-dark & {
      background-color: $gray-900;
      border-color: $gray-700;
    }

    .bi {
      color: $blue;
    }

    > iframe {
      width: 100%;
      height: 50vh;
      background-color: #FAFAFA;
      overflow: auto;
      border: none;
      border-radius: 5px;
      display: block;

      @at-root .theme-dark & {
        background-color: $gray-900;
      }
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
