import { defineStore } from 'pinia'
import { DateTime } from 'luxon'
import uniqBy from 'lodash/uniqBy'
import murmur from 'murmurhash-js/murmurhash3_gc'

const urlRe = /http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+/
const conferenceDomains = ['webex.com', 'zoom.us', 'jitsi.org', 'meetecho.com', 'gather.town']

export const useAgendaStore = defineStore('agenda', {
  state: () => ({
    areaIndicatorsShown: true,
    calendarShown: false,
    categories: [],
    currentDateTime: DateTime.local(),
    dayIntersectId: '',
    filterShown: false,
    floorIndicatorsShown: true,
    infoNoteShown: true,
    isCurrentMeeting: false,
    listDayCollapse: false,
    meeting: {},
    infoNoteHash: '',
    mobileMode: window.innerWidth < 1400,
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
    useHedgeDoc: false,
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
          const searchStr = `${s.name} ${s.groupName} ${s.room} ${s.note}`
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
            recordings: s.links.recordings,
            videoStream: formatLinkUrl(s.links.videoStream, s, state.meeting.number),
            onsiteTool: formatLinkUrl(s.links.onsiteTool, s, state.meeting.number),
            audioStream: formatLinkUrl(s.links.audioStream, s, state.meeting.number),
            remoteCallIn: remoteCallInUrl,
            calendar: s.links.calendar
          },
          sessionKeyword: s.sessionToken ? `${s.groupAcronym}-${s.sessionToken}` : s.groupAcronym
        }
      })
    },
    meetingDays () {
      return uniqBy(this.scheduleAdjusted, 'adjustedStartDate').sort().map(s => ({
        slug: s.id.toString(),
        ts: s.adjustedStartDate,
        label: DateTime.fromISO(s.adjustedStartDate).toLocaleString(DateTime.DATE_HUGE)
      }))
    },
    isMeetingLive (state) {
      const current = DateTime.local().setZone(state.timezone)
      const isAfterStart = this.scheduleAdjusted.some(s => s.adjustedStart < current)
      const isBeforeEnd = this.scheduleAdjusted.some(s => s.adjustedEnd > current)
      return isAfterStart && isBeforeEnd
    }
  },
  actions: {
    fetch () {
      const agendaData = JSON.parse(document.getElementById('agenda-data').textContent)

      // -> Switch to meeting timezone
      this.timezone = agendaData.meeting.timezone

      // -> Load meeting data
      this.categories = agendaData.categories
      this.isCurrentMeeting = agendaData.isCurrentMeeting
      this.meeting = agendaData.meeting
      this.schedule = agendaData.schedule
      this.useHedgeDoc = agendaData.useHedgeDoc

      this.infoNoteHash = murmur(agendaData.meeting.infoNote, 0).toString()

      // -> Load meeting-specific preferences
      this.infoNoteShown = !(window.localStorage.getItem(`agenda.${agendaData.meeting.number}.hideInfo`) === this.infoNoteHash)
    },
    persistMeetingPreferences () {
      if (this.infoNoteShown) {
        window.localStorage.removeItem(`agenda.${this.meeting.number}.hideInfo`)
      } else {
        window.localStorage.setItem(`agenda.${this.meeting.number}.hideInfo`, this.infoNoteHash)
      }
    }
  },
  persist: {
    enabled: true,
    strategies: [
      {
        storage: localStorage,
        paths: [
          'areaIndicatorsShown',
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
