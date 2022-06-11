import { defineStore } from 'pinia'
import { DateTime } from 'luxon'
import uniqBy from 'lodash/uniqBy'

export const useAgendaStore = defineStore('agenda', {
  state: () => ({
    calendarShown: false,
    categories: [],
    dayIntersectId: '',
    filterShown: false,
    isCurrentMeeting: false,
    meeting: {},
    mobileMode: window.innerWidth < 1400,
    pickerMode: false,
    pickerModeView: false,
    schedule: [],
    searchText: '',
    searchVisible: false,
    selectedCatSubs: [],
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
        return {
          ...s,
          adjustedStart: eventStartDate,
          adjustedEnd: eventEndDate,
          adjustedStartDate: eventStartDate.toISODate(),
          adjustedStartDateTime: eventStartDate.toISO(),
          adjustedEndDateTime: eventEndDate.toISO()
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
    }
  }
})
