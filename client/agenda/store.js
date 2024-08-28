import { defineStore } from 'pinia'
import { DateTime } from 'luxon'
import uniqBy from 'lodash/uniqBy'
import murmur from 'murmurhash-js/murmurhash3_gc'

import { useSiteStore } from '../shared/store'
import { storageAvailable } from '../shared/feature-detect'

const urlRe = /http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+/
const conferenceDomains = ['webex.com', 'zoom.us', 'jitsi.org', 'meetecho.com', 'gather.town']

export const useAgendaStore = defineStore('agenda', {
  state: () => ({
    areaIndicatorsShown: true,
    bolderText: false,
    debugTools: false,
    calendarShown: false,
    categories: [],
    colorLegendShown: true,
    colorPickerVisible: false,
    colors: [
      { hex: '#0d6efd', tag: 'Interesting' },
      { hex: '#6f42c1', tag: 'Might Attend' },
      { hex: '#d63384', tag: 'Important' },
      { hex: '#ffc107', tag: 'Food' },
      { hex: '#20c997', tag: 'Attended' }
    ],
    colorAssignments: {},
    currentTab: 'agenda',
    dayIntersectId: '',
    defaultCalendarView: 'week',
    eventIconsShown: true,
    filterShown: false,
    floorIndicatorsShown: true,
    floors: [],
    infoNoteHash: '',
    infoNoteShown: true,
    isCurrentMeeting: false,
    isLoaded: false,
    listDayCollapse: false,
    meeting: {},
    nowDebugDiff: null,
    pickerMode: false,
    pickerModeView: false,
    pickedEvents: [],
    redhandShown: true,
    schedule: [],
    searchText: '',
    searchVisible: false,
    selectedCatSubs: [],
    settingsShown: false,
    timezone: DateTime.local().zoneName,
    usesNotes: false,
    visibleDays: []
  }),
  getters: {
    isTimezoneLocal (state) {
      return state.timezone === DateTime.local().zoneName
    },
    isTimezoneMeeting (state) {
      return state.timezone === state.meeting.timezone
    },
    scheduleAdjusted (state) {
      return state.schedule.filter(s => {
        // -> Apply category filters
        if (state.selectedCatSubs.length > 0 && !s.filterKeywords.some(k => state.selectedCatSubs.includes(k))) {
          return false
        }

        // -> Don't show events of type lead
        if (s.type === 'lead') { return false }

        // -> Filter individual events if picker mode active
        if (state.pickerMode && state.pickerModeView && !state.pickedEvents.includes(s.id)) {
          return false
        }

        // -> Filter by search text if present
        if (state.searchVisible && state.searchText) {
          const searchStr = `${s.name} ${s.groupName} ${s.acronym} ${s.room} ${s.note}`
          if (searchStr.toLowerCase().indexOf(state.searchText) < 0) {
            return false
          }
        }
        return true
      }).map(s => {
        // -> Adjust times to selected timezone
        const eventStartDate = DateTime.fromISO(s.startDateTime, { zone: state.meeting.timezone }).setZone(state.timezone)
        const eventEndDate = eventStartDate.plus({ seconds: s.duration })

        // -> Find remote call-in URL
        let remoteCallInUrl = null
        if (s.note) {
          remoteCallInUrl = findFirstConferenceUrl(s.note)
        }
        if (!remoteCallInUrl && s.remoteInstructions) {
          remoteCallInUrl = findFirstConferenceUrl(s.remoteInstructions)
        }
        if (!remoteCallInUrl && s.links.webex) {
          remoteCallInUrl = s.links.webex
        }

        return {
          ...s,
          adjustedStart: eventStartDate,
          adjustedEnd: eventEndDate,
          adjustedStartDate: eventStartDate.toISODate(),
          adjustedStartDateTime: eventStartDate.toISO(),
          adjustedEndDateTime: eventEndDate.toISO(),
          links: {
            ...s.links,
            videoStream: formatLinkUrl(s.links.videoStream, s, state.meeting.number),
            onsiteTool: formatLinkUrl(s.links.onsiteTool, s, state.meeting.number),
            audioStream: formatLinkUrl(s.links.audioStream, s, state.meeting.number),
            remoteCallIn: remoteCallInUrl
          },
          sessionKeyword: s.sessionToken ? `${s.groupAcronym}-${s.sessionToken}` : s.groupAcronym
        }
      })
    },
    meetingDays () {
      const siteStore = useSiteStore()
      return uniqBy(this.scheduleAdjusted, 'adjustedStartDate').sort().map(s => ({
        slug: daySlug(s),
        ts: s.adjustedStartDate,
        label: siteStore.viewport < 1350 ? DateTime.fromISO(s.adjustedStartDate).toFormat('ccc LLL d') : DateTime.fromISO(s.adjustedStartDate).toLocaleString(DateTime.DATE_HUGE)
      }))
    },
    isMeetingLive (state) {
      const current = (state.nowDebugDiff ? DateTime.local().minus(state.nowDebugDiff) : DateTime.local()).setZone(state.timezone)
      const isAfterStart = this.scheduleAdjusted.some(s => s.adjustedStart < current)
      const isBeforeEnd = this.scheduleAdjusted.some(s => s.adjustedEnd > current)
      return isAfterStart && isBeforeEnd
    }
  },
  actions: {
    async fetch (meetingNumber) {
      try {
        if (!meetingNumber) {
          const meetingData = JSON.parse(document.getElementById('meeting-data').textContent)
          meetingNumber = meetingData.meetingNumber
        }

        const resp = await fetch(`/api/meeting/${meetingNumber}/agenda-data`, { credentials: 'omit' })
        if (!resp.ok) {
          throw new Error(resp.statusText)
        }
        const agendaData = await resp.json()

        // -> Switch to meeting timezone
        if (storageAvailable('localStorage')) {
          this.timezone = window.localStorage.getItem(`agenda.${agendaData.meeting.number}.timezone`) || agendaData.meeting.timezone
        } else {
          this.timezone = agendaData.meeting.timezone
        }

        // -> Load meeting data
        this.categories = agendaData.categories
        this.floors = agendaData.floors
        this.isCurrentMeeting = agendaData.isCurrentMeeting
        this.meeting = agendaData.meeting
        this.schedule = agendaData.schedule
        this.usesNotes = agendaData.usesNotes

        // -> Compute current info note hash
        this.infoNoteHash = murmur(agendaData.meeting.infoNote, 0).toString()

        // -> Load meeting-specific preferences
        if (storageAvailable('localStorage')) {
          this.infoNoteShown = !(window.localStorage.getItem(`agenda.${agendaData.meeting.number}.hideInfo`) === this.infoNoteHash)
          this.colorAssignments = JSON.parse(window.localStorage.getItem(`agenda.${agendaData.meeting.number}.colorAssignments`) || '{}')
          this.selectedCatSubs = JSON.parse(window.localStorage.getItem(`agenda.${agendaData.meeting.number}.filters`) || '[]')
          this.pickedEvents = JSON.parse(window.localStorage.getItem(`agenda.${agendaData.meeting.number}.pickedEvents`) || '[]')
        } else {
          this.infoNoteShown = true
          this.colorAssignments = {}
          this.selectedCatSubs = []
          this.pickedEvents = []
        }

        this.isLoaded = true
      } catch (err) {
        console.error(err)
        const siteStore = useSiteStore()
        siteStore.$patch({
          criticalError: `Failed to load this meeting: ${err.message}`,
          criticalErrorLink: meetingNumber ? `/meeting/${meetingNumber}/agenda.txt` : `/meeting/agenda.txt`,
          criticalErrorLinkText: 'Switch to text-only agenda version'
        })
      }

      this.hideLoadingScreen()
    },
    persistMeetingPreferences () {
      if (!storageAvailable('localStorage')) { return }
      
      if (this.infoNoteShown) {
        window.localStorage.removeItem(`agenda.${this.meeting.number}.hideInfo`)
      } else {
        window.localStorage.setItem(`agenda.${this.meeting.number}.hideInfo`, this.infoNoteHash)
      }
      window.localStorage.setItem(`agenda.${this.meeting.number}.colorAssignments`, JSON.stringify(this.colorAssignments))
      window.localStorage.setItem(`agenda.${this.meeting.number}.filters`, JSON.stringify(this.selectedCatSubs))
      window.localStorage.setItem(`agenda.${this.meeting.number}.pickedEvents`, JSON.stringify(this.pickedEvents))
      window.localStorage.setItem(`agenda.${this.meeting.number}.timezone`, this.timezone)
    },
    findCurrentEventId () {
      const current = (this.nowDebugDiff ? DateTime.local().minus(this.nowDebugDiff) : DateTime.local()).setZone(this.timezone)

      // -> Find last event before current time
      let lastEvent = {}
      for(const sh of this.scheduleAdjusted) {
        if (sh.adjustedStart <= current && sh.adjustedEnd > current) {
          // -> Use the first event of multiple events having identical times
          if (lastEvent.start === sh.adjustedStart.toMillis()) {
            continue
          } else {
            lastEvent = {
              id: sh.id,
              start: sh.adjustedStart.toMillis(),
              end: sh.adjustedEnd.toMillis()
            }
          }
        }
        // -> Skip future events
        if (sh.adjustedStart > current) {
          break
        }
      }

      return lastEvent.id || null
    },
    hideLoadingScreen () {
      // -> Hide loading screen
      const loadingRef = document.querySelector('#app-loading')
      if (loadingRef) {
        loadingRef.remove()
      }
    }
  },
  persist: {
    enabled: storageAvailable('localStorage'),
    strategies: [
      {
        storage: storageAvailable('localStorage') ? localStorage : null,
        paths: [
          'areaIndicatorsShown',
          'bolderText',
          'colorLegendShown',
          'colors',
          'defaultCalendarView',
          'eventIconsShown',
          'floorIndicatorsShown',
          'listDayCollapse',
          'redhandShown'
        ]
      }
    ]
  }
})

/**
 * Format URL by replacing inline variables
 * 
 * @param {String} url 
 * @param {Object} session 
 * @param {String} meetingNumber 
 * @returns Formatted URL
 */
function formatLinkUrl (url, session, meetingNumber) {
  return url ? url.replace('{meeting.number}', meetingNumber)
    .replace('{group.acronym}', session.groupAcronym)
    .replace('{short}', session.short)
    .replace('{order_number}', session.orderInMeeting) : url
}

/**
 * Find the first URL in text matching a conference domain
 * 
 * @param {String} txt 
 * @returns First URL found
 */
function findFirstConferenceUrl (txt) {
  try {
    const fUrl = txt.match(urlRe)
    if (fUrl && fUrl[0].length > 0) {
      const pUrl = new URL(fUrl[0])
      if (conferenceDomains.some(d => pUrl.hostname.endsWith(d))) {
        return fUrl[0]
      }
    }
  } catch (err) { }
  return null
}

export const daySlugPrefix = 'agenda-day-'
export function daySlug(s) {
  return `${daySlugPrefix}${s.adjustedStartDate}` // eg 'agenda-day-2024-08-13'
}
