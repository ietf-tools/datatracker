<template lang="pug">
.agenda-table.mb-3
  table
    thead
      tr
        th.agenda-table-head-check(v-if='agendaStore.pickerMode') &nbsp;
        th.agenda-table-head-time Time
        th.agenda-table-head-location Location
        th.agenda-table-head-event(colspan='3') Event
    tbody
      tr(
        v-for='item of meetingEvents'
        :key='item.key'
        :class='item.cssClasses'
        )
        //- ROW - DAY HEADING -----------------------
        template(v-if='item.displayType === `day`')
          td(:id='`agenda-day-` + item.id', :colspan='agendaStore.pickerMode ? 6 : 5') {{item.date}}
        //- ROW - SESSION HEADING -------------------
        template(v-else-if='item.displayType === `session-head`')
          td.agenda-table-cell-check(v-if='agendaStore.pickerMode') &nbsp;
          td.agenda-table-cell-ts {{item.timeslot}}
          td.agenda-table-cell-name(colspan='4') {{item.name}}
        //- ROW - EVENT -----------------------------
        template(v-else-if='item.displayType === `event`')
          //- CELL - CHECKBOX -----------------------
          td.agenda-table-cell-check(
            v-if='agendaStore.pickerMode'
            )
            n-checkbox(
              :value='item.key'
              )
          //- CELL - TIME ---------------------------
          td.agenda-table-cell-ts(
            :class='{ "is-session-event": item.isSessionEvent }'
            )
            span(v-if='item.isSessionEvent') &mdash;
            span(v-else) {{item.timeslot}}
          //- CELL - ROOM ---------------------------
          td.agenda-table-cell-room
            template(v-if='item.location && item.location.short')
              n-popover(
                trigger='hover'
                )
                template(#trigger)
                  span.badge {{item.location.short}}
                span {{item.location.name}}
              a.discreet(
                :href='`/meeting/` + agendaStore.meeting.number + `/floor-plan?room=` + xslugify(item.room)'
                :aria-label='item.room'
                ) {{item.room}}
            span(v-else) {{item.room}}
          //- CELL - GROUP --------------------------
          td.agenda-table-cell-group(v-if='item.type === `regular`')
            n-popover(
              trigger='hover'
              :width='250'
              )
              template(#trigger)
                span.badge {{item.groupAcronym}}
              .agenda-table-cell-group-hover
                strong {{item.groupParentName}}
                span {{item.groupParentDescription}}
            a.discreet(:href='`/group/` + item.acronym + `/about/`') {{item.acronym}}
          //- CELL - NAME ---------------------------
          td.agenda-table-cell-name(
            :colspan='!item.isSessionEvent ? 2 : 1'
            )
            i.bi.me-2(v-if='item.icon', :class='item.icon')
            a.discreet(
              v-if='item.flags.agenda'
              :href='item.agenda.url'
              :aria-label='item.isSessionEvent ? item.groupName : item.name'
              ) {{item.isSessionEvent ? item.groupName : item.name}}
            span(v-else) {{item.isSessionEvent ? item.groupName : item.name}}
            n-popover(
              v-if='item.isBoF'
              trigger='hover'
              :width='250'
              )
              template(#trigger)
                span.badge.is-bof BoF
              span #[a(href='https://www.ietf.org/how/bofs/', target='_blank') Birds of a Feather] sessions (BoFs) are initial discussions about a particular topic of interest to the IETF community.
            .agenda-table-note(v-if='item.note')
              i.bi.bi-arrow-return-right.me-1
              span {{item.note}}
          //- CELL - LINKS --------------------------
          td.agenda-table-cell-links
            span.badge.is-cancelled(v-if='item.status === `canceled`') Cancelled
            span.badge.is-rescheduled(v-else-if='item.status === `resched`') Rescheduled
            .agenda-table-cell-links-buttons(v-else-if='item.links && item.links.length > 0')
              template(v-if='item.flags.agenda')
                n-popover
                  template(#trigger)
                    i.bi.bi-collection(@click='showMaterials(item.key)')
                  span Show meeting materials
              n-popover(v-for='lnk of item.links', :key='lnk.id')
                template(#trigger)
                  a(
                    :href='lnk.href'
                    :aria-label='lnk.label'
                    ): i.bi(:class='`bi-` + lnk.icon')
                span {{lnk.label}}

  agenda-details-modal(
    v-model:shown='state.showEventDetails'
    :event='state.eventDetails'
    :meeting-number='agendaStore.meeting.number'
  )
</template>

<script setup>
import { computed, reactive } from 'vue'
import { DateTime } from 'luxon'
import find from 'lodash/find'
import sortBy from 'lodash/sortBy'
import reduce from 'lodash/reduce'
import slugify from 'slugify'
import {
  NCheckbox,
  NPopover
} from 'naive-ui'

import AgendaDetailsModal from './AgendaDetailsModal.vue'

import { useAgendaStore } from './store'

// STORES

const agendaStore = useAgendaStore()

// DATA

const state = reactive({
  showEventDetails: false,
  eventDetails: {}
})

// COMPUTED

const meetingEvents = computed(() => {
  return reduce(sortBy(agendaStore.scheduleAdjusted, 'adjustedStartDate'), (acc, item) => {
    const itemTimeSlot = `${item.adjustedStart.toFormat('HH:mm')} - ${item.adjustedEnd.toFormat('HH:mm')}`

    // -> Add date row
    const itemDate = DateTime.fromISO(item.adjustedStartDate)
    if (itemDate.toISODate() !== acc.lastDate) {
      acc.result.push({
        id: item.id,
        key: `day-${itemDate.toISODate()}`,
        displayType: 'day',
        date: itemDate.toLocaleString(DateTime.DATE_HUGE),
        cssClasses: 'agenda-table-display-day'
      })
    }
    acc.lastDate = itemDate.toISODate()

    // -> Add session header row
    if (item.type === 'regular' && acc.lastTypeName !== `${item.type}-${item.name}`) {
      acc.result.push({
        key: `sesshd-${item.id}`,
        displayType: 'session-head',
        timeslot: itemTimeSlot,
        name: `${item.adjustedStart.toFormat('cccc')} ${item.name}`,
        cssClasses: 'agenda-table-display-session-head'
      })
    }
    acc.lastTypeName = `${item.type}-${item.name}`

    // -> Populate event links
    const links = []
    if (item.flags.showAgenda) {
      if (item.flags.agenda) {
        links.push({
          id: `lnk-${item.id}-tar`,
          label: 'Download meeting materials as .tar archive',
          icon: 'file-zip',
          href: `/meeting/${agendaStore.meeting.number}/agenda/${item.acronym}-drafts.tgz`
        })
        links.push({
          id: `lnk-${item.id}-pdf`,
          label: 'Download meeting materials as PDF file',
          icon: 'file-pdf',
          href: `/meeting/${agendaStore.meeting.number}/agenda/${item.acronym}-drafts.pdf`
        })
      }
      if (agendaStore.useCodiMd) {
        links.push({
          id: `lnk-${item.id}-note`,
          label: 'Notepad for note-takers',
          icon: 'journal-text',
          href: `https://notes.ietf.org/notes-ietf-${agendaStore.meeting.number}-${item.type === 'plenary' ? 'plenary' : item.acronym}`
        })
      }
      links.push({
        id: `lnk-${item.id}-logs`,
        label: `Chat logs for ${item.acronym}`,
        icon: 'chat-left-text'
      })
      links.push({
        id: `lnk-${item.id}-audio`,
        label: `Audio recording for ${item.adjustedStart.toFormat('ff')}`,
        icon: 'soundwave'
      })
      links.push({
        id: `lnk-${item.id}-video`,
        label: `Video recording for ${item.adjustedStart.toFormat('ff')}`,
        icon: 'file-play'
      })
      links.push({
        id: `lnk-${item.id}-rec`,
        label: 'Session recording',
        icon: 'film'
      })
    }

    // Event icon
    let icon = null
    switch (item.type) {
      case 'break':
        icon = 'bi-cup-straw'
        break
      case 'plenary':
        icon = 'bi-flower3 bi-green'
        break
      case 'other':
        if (item.name.toLowerCase().indexOf('office hours') >= 0) {
          icon = 'bi-building'
        } else if (item.name.toLowerCase().indexOf('hackathon') >= 0) {
          icon = 'bi-command bi-pink'
        }
        break
    }

    // -> Add event item
    acc.result.push({
      key: item.id,
      acronym: item.acronym,
      cssClasses: [
        `agenda-table-display-event`,
        `agenda-table-status-${item.status}`,
        `agenda-table-type-${item.type}`,
        item.note ? 'agenda-table-has-note' : ''
      ].join(' '),
      agenda: item.agenda,
      displayType: 'event',
      end: item.adjustedEnd,
      flags: item.flags,
      groupAcronym: item.groupParent?.acronym,
      groupName: item.groupName,
      groupParentDescription: item.groupParent?.description,
      groupParentName: item.groupParent?.name,
      icon,
      isBoF: item.isBoF,
      isSessionEvent: item.type === 'regular',
      links,
      location: item.location,
      name: item.name,
      note: item.note,
      room: item.room,
      sessionName: item.sessionName,
      start: item.adjustedStart,
      status: item.status,
      timeslot: itemTimeSlot,
      type: item.type
    })

    return acc
  }, {
    lastDate: null,
    lastTypeName: null,
    result: []
  }).result
})

// METHODS

function showMaterials (eventId) {
  state.eventDetails = find(agendaStore.scheduleAdjusted, ['id', eventId])
  state.showEventDetails = true
}

function xslugify (str) {
  return slugify(str.replace('/', '-'), { lower: true })
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-table {
  border: 1px solid $gray-600;
  border-radius: 5px;
  font-size: 0.9rem;

  table {
    width: 100%;
    border: 1px solid #FFF;
    border-radius: 5px;
    border-collapse: separate;
    border-spacing: 0;
  }

  // -> Table HEADER

  th {
    vertical-align: middle;
    height: 34px;
    line-height: 0.9rem;
    border: 0;
    text-align: center;
    // background: linear-gradient(to bottom, desaturate($blue-700, 50%), desaturate($blue-500, 65%));
    background: linear-gradient(to bottom, lighten($gray-800, 8%), lighten($gray-600, 4%));
    color: #FFF;
    border: 0;
    border-bottom: 1px solid #FFF;
    padding: 0 12px;
    font-weight: 600;
    border-right: 1px solid #FFF;

    &:first-child {
      border-top-left-radius: 5px;
    }

    &.agenda-table-head-check {
      width: 10px;
    }
    &.agenda-table-head-time {
      width: 125px;
    }
    &.agenda-table-head-location {
      width: 250px;
    }
    // .agenda-table-head-event {
    //   width: 10px;
    // }

    &:last-child {
      border-top-right-radius: 5px;
      border-right: none;
    }
  }

  td {
    vertical-align: middle;
    height: 34px;
    // line-height: 16px;
    border: 0;
  }

  // -> Column Sizes
  tr td:nth-child(3) {
    width: 200px;
  }

  tr:nth-child(odd) td {
    background-color: #F9F9F9;
  }

  &-display-day > td {
    background: linear-gradient(to top, lighten($gray-900, 8%), lighten($gray-700, 4%));
    color: #FFF;
    border: 0;
    border-bottom: 1px solid #FFF;
    padding: 0 12px;
    font-weight: 600;
    scroll-margin-top: 25px;
  }

  &-display-session-head > td {
    background: linear-gradient(to top, lighten($blue-200, 8%), lighten($blue-200, 4%)) !important;
    border-bottom: 1px solid $blue;
    border-top: 1px solid $blue;
    padding: 0 12px;
    color: #333;

    &.agenda-table-cell-ts {
      border-right: 1px solid $blue-200 !important;
      color: $blue-700;
    }

    &.agenda-table-cell-name {
      color: $blue-700;
      font-weight: 600;
    }
  }

  &-display-event > td {
    border: 0;
    padding: 0 12px;
    color: #333;

    &.agenda-table-cell-check {
      background-color: desaturate($blue-700, 50%) !important;
      border-bottom: 1px solid #FFF;
      padding-bottom: 2px;
    }

    &.agenda-table-cell-ts.is-session-event {
      background: linear-gradient(to right, lighten($blue-100, 8%), lighten($blue-100, 5%));
      border-right: 1px solid $blue-200 !important;
      color: $blue-200;
      border-bottom: 1px solid #FFF;
    }

    &.agenda-table-cell-room {
      color: $gray-700;
      border-right: 1px solid $gray-300 !important;

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

    &.agenda-table-cell-group {
      color: $gray-700;

      .badge {
        width: 40px;
        font-size: .7em;
        background-color: $gray-700;
        text-transform: uppercase;
        font-weight: 600;
        margin-right: 10px;
      }
    }

    &.agenda-table-cell-name {
      .badge.is-bof {
        background-color: $teal-500;
        margin: 0 8px;
      }

      .bi {
        &.bi-brown {
          color: $indigo-500;
        }
        &.bi-green {
          color: $green-500;
        }
        &.bi-pink {
          color: $pink-500;
        }
      }
    }

    &.agenda-table-cell-links {
      text-align: right;

      .badge.is-cancelled {
        background-color: $red-500;
        text-transform: uppercase;
        margin-left: 8px;
      }

      .badge.is-rescheduled {
        background-color: $orange-500;
        text-transform: uppercase;
        margin-left: 8px;
      }

      .agenda-table-cell-links-buttons {
        > a, > i {
          margin-left: 5px;
          color: #666;
          cursor: pointer;

          &:hover, &:focus {
            color: $blue;
          }
        }
      }
    }
  }

  &-cell-ts {
    border-right: 1px solid $gray-300 !important;
    font-size: 1rem;
    font-weight: 700;
    text-align: right;
  }

  // -> Row BG Color Highlight
  &-status-canceled td {
    background-color: rgba($red, .15) !important;

    &:last-child {
      background: linear-gradient(to right, rgba($red, 0), rgba($red, .5));
    }
  }
  &-status-resched td {
    background-color: rgba($orange, .15) !important;

    &:last-child {
      background: linear-gradient(to right, rgba($orange, 0), rgba($orange, .5));
    }
  }
  &-type-break td {
    background-color: rgba($indigo, .1) !important;

    &.agenda-table-cell-ts {
      background: linear-gradient(to right, lighten($indigo-100, 8%), lighten($indigo-100, 5%));
      color: $indigo-700;
    }

    &.agenda-table-cell-name {
      color: $indigo-700;
      font-style: italic;
    }

    &.agenda-table-cell-links {
      background: linear-gradient(to right, lighten($indigo-100, 5%), lighten($indigo-100, 8%));
    }
  }
  &-type-plenary td {
    background-color: rgba($teal, .15) !important;
    color: $teal-800;

    &.agenda-table-cell-ts {
      background: linear-gradient(to right, lighten($teal-100, 8%), lighten($teal-100, 2%));
    }

    &.agenda-table-cell-name {
      font-weight: 600;
      color: $teal-700;
    }

    &.agenda-table-cell-links {
      background: linear-gradient(to right, rgba(lighten($teal, 54%), 0), lighten($teal, 54%));
    }
  }

  &-has-note td {
    &.agenda-table-cell-name {
      padding: 7px 12px;

      .agenda-table-note {
        font-weight: 600;
        font-size: .95em;
        color: $pink-500;
      }
    }
  }

  // -> Popovers
  &-cell-group-hover {
    > strong {
      display: block;
      margin-bottom: 8px;
    }
    > span {
      font-size: .9em;
      display: -webkit-box;
      -webkit-line-clamp: 4;
      -webkit-box-orient: vertical;
      text-overflow: ellipsis;
      overflow: hidden;
      max-height: 200px; // just in case line-clamp not supported
    }
  }

  .badge {
    transform: translateY(-2px);
  }

  a.discreet {
    color: inherit;
    text-decoration: none;

    &:hover, &:focus {
      color: $blue-500;
      text-decoration: underline;
    }

    &:active {
      color: $indigo-500;
    }
  }
}
</style>
