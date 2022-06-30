<template lang="pug">
.agenda-table.mb-3
  n-checkbox-group(v-model:value='pickedEvents')
    table
      thead
        tr
          th.agenda-table-head-check(v-if='pickerModeActive') &nbsp;
          th.agenda-table-head-time Time
          th.agenda-table-head-location(colspan='2') Location
          th.agenda-table-head-event(colspan='2') {{ agendaStore.viewport < 990 ? '' : 'Event' }}
      tbody
        tr.agenda-table-display-noresult(
          v-if='!meetingEvents || meetingEvents.length < 1'
          )
          td(:colspan='pickerModeActive ? 6 : 5')
            i.bi.bi-exclamation-triangle.me-2
            span(v-if='agendaStore.searchVisible && agendaStore.searchText') No event matching your search query.
            span(v-else) Nothing to display
        tr(
          v-for='item of meetingEvents'
          :key='item.key'
          :id='`agenda-rowid-` + item.key'
          :class='item.cssClasses'
          )
          //- ROW - DAY HEADING -----------------------
          template(v-if='item.displayType === `day`')
            td(:id='`agenda-day-` + item.id', :colspan='pickerModeActive ? 6 : 5') {{item.date}}
          //- ROW - SESSION HEADING -------------------
          template(v-else-if='item.displayType === `session-head`')
            td.agenda-table-cell-check(v-if='pickerModeActive') &nbsp;
            td.agenda-table-cell-ts {{item.timeslot}}
            td.agenda-table-cell-name(colspan='4') {{item.name}}
          //- ROW - EVENT -----------------------------
          template(v-else-if='item.displayType === `event`')
            //- CELL - CHECKBOX -----------------------
            td.agenda-table-cell-check(
              v-if='pickerModeActive'
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
            td.agenda-table-cell-room(
              :colspan='!item.isSessionEvent ? 2 : 1'
              )
              template(v-if='item.location && item.location.short')
                n-popover(
                  trigger='hover'
                  v-if='agendaStore.floorIndicatorsShown'
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
              span.badge(v-if='agendaStore.areaIndicatorsShown && agendaStore.viewport > 1200') {{item.groupAcronym}}
              a.discreet(:href='`/group/` + item.acronym + `/about/`') {{item.acronym}}
            //- CELL - NAME ---------------------------
            td.agenda-table-cell-name
              i.bi.me-2(v-if='item.icon && agendaStore.eventIconsShown', :class='item.icon')
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
              template(v-if='state.selectedColorPicker === item.key')
                .agenda-table-colorchoices
                  .agenda-table-colorchoice(
                    @click='setEventColor(item.key, null)'
                    )
                    i.bi.bi-x
                  .agenda-table-colorchoice(
                    v-for='(color, idx) in agendaStore.colors'
                    :key='idx'
                    :style='{ "color": color.hex }'
                    @click='setEventColor(item.key, idx)'
                    )
              template(v-else)
                span.badge.is-cancelled(v-if='item.status === `canceled`') Cancelled
                span.badge.is-rescheduled(v-else-if='item.status === `resched`') Rescheduled
                .agenda-table-cell-links-buttons(v-else-if='agendaStore.viewport < 1200 && item.links && item.links.length > 0')
                  n-dropdown(
                    trigger='click'
                    :options='item.links'
                    key-field='id'
                    :render-icon='renderLinkIcon'
                    v-if='!agendaStore.colorPickerVisible'
                    )
                    n-button(size='tiny')
                      i.bi.bi-three-dots
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
                          :class='`text-` + lnk.color'
                          ): i.bi(:class='`bi-` + lnk.icon')
                      span {{lnk.label}}
                    
              .agenda-table-colorindicator(
                v-if='agendaStore.colorPickerVisible || getEventColor(item.key)'
                @click='agendaStore.colorPickerVisible && openColorPicker(item.key)'
                :class='{ "is-active": agendaStore.colorPickerVisible }'
                :style='{ "color": getEventColor(item.key) }'
                )

  .agenda-table-search
    n-popover
      template(#trigger)
        button(
          @click='toggleSearch'
          :aria-label='agendaStore.searchVisible ? `Close Search` : `Search Events`'
          )
          i.bi.bi-search
      span {{ agendaStore.searchVisible ? 'Close Search' : 'Search Events' }}

  .agenda-table-colorpicker
    n-popover
      template(#trigger)
        button(
          @click='toggleColorPicker'
          :aria-label='agendaStore.colorPickerVisible ? `Exit Colors Assignment Mode` : `Assign Colors to Events`'
          )
          i.bi.bi-palette
      span {{ agendaStore.colorPickerVisible ? 'Exit Colors Assignment Mode' : 'Assign Colors to Events' }}

  .agenda-table-redhand(
    v-if='agendaStore.redhandShown && state.redhandOffset > 0'
    :style='{ "top": state.redhandOffset + "px" }'
    )

  agenda-details-modal(
    v-model:shown='state.showEventDetails'
    :event='state.eventDetails'
    :meeting-number='agendaStore.meeting.number'
  )
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, reactive } from 'vue'
import { DateTime } from 'luxon'
import find from 'lodash/find'
import sortBy from 'lodash/sortBy'
import reduce from 'lodash/reduce'
import slugify from 'slugify'
import {
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NDropdown,
  NPopover
} from 'naive-ui'

import AgendaDetailsModal from './AgendaDetailsModal.vue'

import { useAgendaStore } from './store'

// STORES

const agendaStore = useAgendaStore()

// DATA

const state = reactive({
  showEventDetails: false,
  eventDetails: {},
  selectedColorPicker: null,
  redhandOffset: 0
})
let redhandScheduler = null

// COMPUTED

const pickerModeActive = computed(() => {
  return agendaStore.pickerMode && !agendaStore.pickerModeView
})

const meetingEvents = computed(() => {
  const meetingNumberInt = parseInt(agendaStore.meeting.number)
  const current = DateTime.local().setZone(agendaStore.timezone)

  return reduce(sortBy(agendaStore.scheduleAdjusted, 'adjustedStartDate'), (acc, item) => {
    const itemTimeSlot = agendaStore.viewport > 600 ?
      `${item.adjustedStart.toFormat('HH:mm')} - ${item.adjustedEnd.toFormat('HH:mm')}` :
      `${item.adjustedStart.toFormat('HH:mm')} ${item.adjustedEnd.toFormat('HH:mm')}`

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
          href: `/meeting/${agendaStore.meeting.number}/agenda/${item.acronym}-drafts.tgz`,
          color: 'brown'
        })
        links.push({
          id: `lnk-${item.id}-pdf`,
          label: 'Download meeting materials as PDF file',
          icon: 'file-pdf',
          href: `/meeting/${agendaStore.meeting.number}/agenda/${item.acronym}-drafts.pdf`,
          color: 'red'
        })
      }
      if (agendaStore.useHedgeDoc) {
        links.push({
          id: `lnk-${item.id}-note`,
          label: 'Notepad for note-takers',
          icon: 'journal-text',
          href: `https://notes.ietf.org/notes-ietf-${agendaStore.meeting.number}-${item.type === 'plenary' ? 'plenary' : item.acronym}`,
          color: 'blue'
        })
      }
      if (item.adjustedEnd > current) {
        // -> Pre/live event
        // -> Jabber logs
        links.push({
          id: `lnk-${item.id}-logs`,
          label: `Chat logs for ${item.acronym}`,
          icon: 'chat-left-text',
          href: `xmpp:${item.type === 'plenary' ? 'plenary' : item.acronym}@jabber.ietf.org?join`,
          color: 'green'
        })
        // -> Video stream
        if (item.links.videoStream) {
          links.push({
            id: `lnk-${item.id}-video`,
            label: 'Video stream',
            icon: 'camera-video',
            href: item.links.videoStream,
            color: 'purple'
          })
        }
        // -> Onsite tool
        if (item.links.onsiteTool) {
          links.push({
            id: `lnk-${item.id}-onsitetool`,
            label: 'Onsite tool',
            icon: 'telephone-outbound',
            href: item.links.onsiteTool,
            color: 'teal'
          })
        }
        // -> Audio stream
        if (item.links.audioStream) {
          links.push({
            id: `lnk-${item.id}-audio`,
            label: 'Audio stream',
            icon: 'headphones',
            href: item.links.audioStream,
            color: 'teal'
          })
        }
        // -> Remote call-in
        if (item.links.remoteCallIn) {
          links.push({
            id: `lnk-${item.id}-remotecallin`,
            label: 'Online conference',
            icon: 'people',
            href: item.links.remoteCallIn,
            color: 'teal'
          })
        }
        // -> Calendar item
        if (item.links.calendar) {
          links.push({
            id: `lnk-${item.id}-calendar`,
            label: `Calendar (.ics) entry for ${item.acronym} session on ${item.adjustedStart.toFormat('fff')}`,
            icon: 'calendar-check',
            href: item.links.calendar,
            color: 'pink'
          })
        }
      } else {
        // -> Post event
        if (meetingNumberInt >= 60) {
          // -> Jabber logs
          links.push({
            id: `lnk-${item.id}-logs`,
            label: `Chat logs for ${item.acronym}`,
            icon: 'chat-left-text',
            href: `https://www.ietf.org/jabber/logs/${item.type === 'plenary' ? 'plenary' : item.acronym}?C=M;O=D`,
            color: 'green'
          })
        }
        if (meetingNumberInt >= 80) {
          // -> Recordings
          for (const rec of item.links.recordings) {
            if (rec.url.indexOf('audio') > 0) {
              // -> Audio
              links.push({
                id: `lnk-${item.id}-audio-${rec.id}`,
                label: rec.title,
                icon: 'soundwave',
                href: rec.url
              })
            } else if (rec.url.indexOf('youtu') > 0) {
              // -> Youtube
              links.push({
                id: `lnk-${item.id}-youtube-${rec.id}`,
                label: rec.title,
                icon: 'youtube',
                href: rec.url,
                color: 'red'
              })
            } else {
              // -> Others
              links.push({
                id: `lnk-${item.id}-video-${rec.id}`,
                label: rec.title,
                icon: 'file-play',
                href: rec.url,
                color: 'purple'
              })
            }
          }
          if (item.links.videoStream) {
            links.push({
              id: `lnk-${item.id}-rec`,
              label: 'Session recording',
              icon: 'film',
              href: `https://www.meetecho.com/ietf${agendaStore.meeting.number}/recordings#${item.acronym.toUpperCase()}`,
              color: 'purple'
            })
          }
        }
      }
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
      // groupParentDescription: item.groupParent?.description,
      // groupParentName: item.groupParent?.name,
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

const pickedEvents = computed({
  get () {
    return agendaStore.pickedEvents
  },
  set (newValue) {
    agendaStore.$patch({
      pickedEvents: newValue
    })
  }
})

// METHODS

function toggleSearch () {
  agendaStore.$patch({
    searchText: '',
    searchVisible: !agendaStore.searchVisible
  })
}

function toggleColorPicker () {
  state.selectedColorPicker = null
  agendaStore.$patch({
    colorPickerVisible: !agendaStore.colorPickerVisible
  })
}

function showMaterials (eventId) {
  state.eventDetails = find(agendaStore.scheduleAdjusted, ['id', eventId])
  state.showEventDetails = true
}

function xslugify (str) {
  return slugify(str.replace('/', '-'), { lower: true })
}

function openColorPicker (itemKey) {
  state.selectedColorPicker = (state.selectedColorPicker === itemKey) ? null : itemKey
}

function setEventColor (itemKey, colorIdx) {
  agendaStore.$patch({
    colorAssignments: {
      ...agendaStore.colorAssignments,
      [itemKey]: colorIdx
    }
  })
  state.selectedColorPicker = null
  agendaStore.persistMeetingPreferences()
}

function getEventColor (itemKey) {
  const clIdx = agendaStore.colorAssignments[itemKey]
  if (clIdx || clIdx === 0) {
    return agendaStore.colors[clIdx]?.hex
  } else {
    return null
  }
}

function renderLinkIcon (opt) {
  return h('i', { class: `bi bi-${opt.icon} text-${opt.color}` })
}

// MOUNTED

onMounted(() => {
  // -> Update Redhand Position
  redhandScheduler = setInterval(() => {
    const lastEventId = agendaStore.findCurrentEventId()

    if (lastEventId) {
      state.redhandOffset = document.getElementById(`agenda-rowid-${lastEventId}`)?.offsetTop || 0
    } else {
      state.redhandOffset = 0
    }
  }, 5000)
})

// BEFORE UNMOUNT

onBeforeUnmount(() => {
  clearInterval(redhandScheduler)
})

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-table {
  border: 1px solid $gray-600;
  border-radius: 5px;
  font-size: 0.9rem;
  position: relative;

  &-redhand {
    position: absolute;
    top: 0;
    content: "";
    width: 100%;
    height: 2px;
    background-color: #F00;
    box-shadow: 0 0 5px 0 #F00;
    transition: top 1s ease;

    &::after {
      content: '';
      display: block;
      width: 0;
      height: 0;
      border-top: 7px solid transparent;
      border-bottom: 7px solid transparent;
      border-left: 7px solid #F00;
      transform: translate(0,-6px);
    }
  }

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

      @media screen and (max-width: 1300px) {
        width: 100px;
      }
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
  // tr td:nth-child(3) {
  //   width: 200px;
  // }

  tr:nth-child(odd) td {
    background-color: #F9F9F9;
  }

  &-display-noresult > td {
    background: linear-gradient(to bottom, $gray-400, $gray-100);
    height: 60px;
    padding: 0 12px;
    color: $gray-800;
    text-shadow: 1px 1px 0 #FFF;
    font-weight: 600;
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

    &.agenda-table-cell-ts {
      &.is-session-event {
        background: linear-gradient(to right, lighten($blue-100, 8%), lighten($blue-100, 5%));
        border-right: 1px solid $blue-200 !important;
        color: $blue-200;
        border-bottom: 1px solid #FFF;
      }
    }

    &.agenda-table-cell-room {
      color: $gray-700;
      border-right: 1px solid $gray-300 !important;
      white-space: nowrap;

      @media screen and (max-width: 1300px) {
        font-size: .85rem;
      }

      @media screen and (max-width: 600px) {
        white-space: initial;
      }

      .badge {
        display: inline-flex;
        min-width: 20px;
        height: 16px;
        font-size: .65em;
        background-color: $yellow-200;
        border-bottom: 1px solid $yellow-500;
        border-right: 1px solid $yellow-500;
        color: $yellow-900;
        text-transform: uppercase;
        font-weight: 700;
        margin-right: 10px;
        text-shadow: 1px 1px $yellow-100;
        padding: 0 4px;
        justify-content: center;
        align-items: center;

        margin-left: -12px;
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        margin-right: 6px;
      }
    }

    &.agenda-table-cell-group {
      color: $gray-700;
      border-right: 1px solid $gray-300 !important;
      white-space: nowrap;

      .badge {
        display: inline-flex;
        min-width: 32px;
        height: 16px;
        font-size: .65em;
        font-weight: 600;
        background-color: $gray-300;
        border-bottom: 1px solid $gray-500;
        border-right: 1px solid $gray-500;
        color: $gray-800;
        text-transform: uppercase;
        margin-right: 10px;
        text-shadow: 1px 1px $gray-200;
        padding: 0 4px;
        justify-content: center;
        align-items: center;

        margin-left: -12px;
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        margin-right: 6px;
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
      position: relative;

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
        white-space: nowrap;

        > a, > i {
          margin-left: 3px;
          color: #666;
          cursor: pointer;
          background-color: rgba(255, 255, 255, .8);
          border-radius: 3px;
          padding: 2px 3px;
          transition: background-color .6s ease;

          &:hover, &:focus {
            color: $blue;
          }

          &.text-red {
            color: $red-500;
            background-color: rgba($red-500, .1);

            &:hover, &:focus {
              background-color: rgba($red-500, .3);
            }
          }
          &.text-brown {
            color: $orange-700;
            background-color: rgba($orange-500, .1);

            &:hover, &:focus {
              background-color: rgba($orange-500, .3);
            }
          }
          &.text-blue {
            color: $blue-600;
            background-color: rgba($blue-300, .1);

            &:hover, &:focus {
              background-color: rgba($blue-300, .3);
            }
          }
          &.text-green {
            color: $green-500;
            background-color: rgba($green-300, .1);

            &:hover, &:focus {
              background-color: rgba($green-300, .3);
            }
          }
          &.text-purple {
            color: $purple-500;
            background-color: rgba($purple-400, .1);

            &:hover, &:focus {
              background-color: rgba($purple-400, .3);
            }
          }
          &.text-pink {
            color: $pink-500;
            background-color: rgba($pink-400, .1);

            &:hover, &:focus {
              background-color: rgba($pink-400, .3);
            }
          }
          &.text-teal {
            color: $teal-600;
            background-color: rgba($teal-400, .1);

            &:hover, &:focus {
              background-color: rgba($teal-400, .3);
            }
          }
        }
      }
    }
  }

  &-cell-ts {
    border-right: 1px solid $gray-300 !important;
    // -> Use system font instead of Montserrat so that all digits align vertically
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    text-align: right;
    white-space: nowrap;

    @media screen and (max-width: 1300px) {
      font-size: .9rem;
    }

    @media screen and (max-width: 600px) {
      white-space: initial;
    }
  }

  // -> Row BG Color Highlight
  &-status-canceled td {
    background-color: rgba($red, .15) !important;
    border-top: 1px solid darken($red-100, 5%);
    border-bottom: 1px solid darken($red-100, 5%);

    &:first-child {
      border-top: none;
      border-bottom: none;
    }

    &.agenda-table-cell-room {
      border-right: 1px solid darken($red-100, 5%) !important;
    }

    &:last-child {
      background: linear-gradient(to right, rgba($red, 0), rgba($red, .5));
    }
  }
  &-status-resched td {
    background-color: rgba($orange, .15) !important;
    border-top: 1px solid darken($orange-100, 5%);
    border-bottom: 1px solid darken($orange-100, 5%);

    &:first-child {
      border-top: none;
      border-bottom: none;
    }

    &.agenda-table-cell-room {
      border-right: 1px solid darken($orange-100, 5%) !important;
    }

    &:last-child {
      background: linear-gradient(to right, rgba($orange, 0), rgba($orange, .5));
    }
  }
  &-type-break td {
    background-color: rgba($indigo, .1) !important;
    border-top: 1px solid darken($indigo-100, 5%);
    border-bottom: 1px solid darken($indigo-100, 5%);

    &.agenda-table-cell-ts {
      background: linear-gradient(to right, lighten($indigo-100, 8%), lighten($indigo-100, 5%));
      color: $indigo-700;
      border-right: 1px solid $indigo-100 !important;
    }

    &.agenda-table-cell-room {
      border-right: 1px solid $indigo-100 !important;
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
    border-top: 1px solid darken($teal-100, 5%);
    border-bottom: 1px solid darken($teal-100, 5%);

    &.agenda-table-cell-ts {
      background: linear-gradient(to right, lighten($teal-100, 8%), lighten($teal-100, 2%));
      border-right: 1px solid $teal-200 !important;
    }

    &.agenda-table-cell-room {
      border-right: 1px solid $teal-200 !important;
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

  // -> TOP RIGHT BUTTONS

  &-search, &-colorpicker {
    position: absolute;
    display: flex;
    top: 15px;
    align-items: center;

    > button {
      border: 1px solid #FFF;
      border-radius: 5px;
      background-color: lighten($gray-600, 6%);
      background-image: linear-gradient(to bottom, lighten($gray-600, 6%), darken($gray-600, 6%));
      height: 40px;
      width: 40px;
      color: #FFF;

      &:hover {
        background-color: lighten($gray-600, 8%);
        background-image: linear-gradient(to bottom, lighten($gray-600, 8%), darken($gray-600, 0%));
      }

      &:focus {
        box-shadow: 0 0 0 5px rgba(255,255,255,.1);
      }

      &:active {
        background-color: $gray-600;
        background-image: none;
      }
    }
  }

  &-search {
    right: 15px;
  }

  &-colorpicker {
    right: 70px;
  }

  // -> COLOR PICKER

  &-colorindicator {
    color: #999;
    position: absolute;
    top: 2px;
    bottom: 2px;
    right: -9px;
    content: '';
    width: 15px;
    height: 15px;
    margin: auto 0;
    background-color: currentColor;
    border: 6px solid currentColor;
    border-radius: 7px;
    animation: fadeInAnim 1s ease;
    box-shadow: 0 0 6px 1px currentcolor;
    transition: all .4s ease;

    &.is-active {
      background-color: #FFF;
      cursor: pointer;

      &:hover {
        border-width: 2px;
      }
    }
  }

  &-colorchoices {
    display: flex;
    align-items: center;
    justify-content: end;
  }

  &-colorchoice {
    width: 22px;
    height: 22px;
    content: '';
    background-color: currentColor;
    border-radius: 5px;
    margin-left: 3px;
    animation: fadeInAnim .4s ease forwards;
    opacity: 0;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    > .bi {
      color: #FFF;
    }

    &:hover {
      border: 3px solid rgba(0,0,0,.25);
    }

    &:first-child {
      margin-left: 0;
    }

    @for $i from 1 through 5 {
      &:nth-child(#{$i}) {
        animation-delay: #{(5 - $i) * .05}s;
      }
    }
  }
}

@keyframes fadeInAnim {
  0% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}

</style>
