<template lang="pug">
n-theme
  n-message-provider
    h1 {{title}}
    h4
      span {{meeting.city}}, {{ meetingDate }}
      h6.float-end(v-if='meetingUpdated') #[span.text-muted Updated:] {{ meetingUpdated }}

    ul.nav.nav-tabs.my-3
      li.nav-item(v-for='tab of tabs')
        a.nav-link.agenda-link.filterable(
          :class='{ active: tab.key === currentTab }'
          @click.prevent='switchTab(tab.key)'
          :href='tab.key'
          )
          i.bi.me-2(:class='tab.icon')
          span {{tab.title}}

    .row
      .col

        // ----------------------------
        // -> Subtitle + Timezone Bar
        // ----------------------------
        .row
          .col
            h2 {{ currentTab === 'personalize' ? 'Session Selection' : 'Schedule'}}
          .col-auto.d-flex.align-items-center
            i.bi.bi-globe.me-2
            small.me-2: strong Timezone:
            n-button-group.me-2
              n-button(
                :type='isTimezoneMeeting ? `primary` : `default`'
                @click='setTimezone(`meeting`)'
                ) Meeting
              n-button(
                :type='isTimezoneLocal ? `primary` : `default`'
                @click='setTimezone(`local`)'
                ) Local
              n-button(
                :type='timezone === `UTC` ? `primary` : `default`'
                @click='setTimezone(`UTC`)'
                ) UTC
            n-select.agenda-timezone-ddn(
              v-model:value='timezone'
              :options='timezones'
              placeholder='Select Time Zone'
              filterable
              )

        .alert.alert-warning.mt-3(v-if='isCurrentMeeting || true') #[strong Note:] IETF agendas are subject to change, up to and during a meeting.
        .agenda-infonote.my-3(v-if='meeting.infoNote', v-html='meeting.infoNote')

        // -----------------------------------
        // -> Drawers
        // -----------------------------------
        agenda-download-ics(v-model:shown='downloadIcsShown', :categories='categories', :meeting-number='meeting.number')
        agenda-filter(v-model:shown='filterShown', v-model:selection='selectedCatSubs', :categories='categories')

        // -----------------------------------
        // -> SCHEDULE - VIEW SELECTOR
        // -----------------------------------
        n-tabs(type='segment', size='large', v-model:value='scheduleTab')
          n-tab-pane(name='list', tab='List View')
            template(v-slot:tab)
              i.bi.bi-list-columns-reverse.me-2
              span List View
            agenda-schedule-list(
              :events='scheduleAdjusted'
              :picker-mode='pickerMode'
              :meeting-number='meeting.number'
              :use-codi-md='useCodiMd'
              )
          n-tab-pane(name='weekview', tab='Calendar View')
            template(v-slot:tab)
              i.bi.bi-calendar2-range.me-2
              span Calendar View
            agenda-schedule-calendar(:events='scheduleAdjusted')

      // -----------------------------------
      // -> Anchored Day Quick Access Menu
      // -----------------------------------
      .col-auto.d-print-none
        .agenda-quickaccess
          n-affix(:top='240')
            .card.shadow-sm
              .card-body
                n-button(
                  block
                  type='success'
                  size='large'
                  strong
                  @click='showFilter'
                  )
                  //- n-badge(:value='selectedCatSubs.length', processing)
                  i.bi.bi-ui-checks-grid.me-2
                  span Filter Agenda...
                n-button.mt-2(
                  v-if='!pickerMode'
                  block
                  secondary
                  type='success'
                  size='large'
                  strong
                  @click='pickerMode = true'
                  )
                  i.bi.bi-ui-checks.me-2
                  span Pick Sessions...
                .agenda-quickaccess-btnrow(v-else)
                  .agenda-quickaccess-btnrow-title Session Selection
                  n-button.me-1(
                    v-if='!pickerModeView'
                    type='success'
                    size='large'
                    strong
                    @click='pickerModeView = true'
                    )
                    i.bi.bi-check2-square.me-2
                    span Apply
                  n-button.me-1(
                    v-else
                    color='#6f42c1'
                    size='large'
                    strong
                    @click='pickerModeView = false'
                    )
                    i.bi.bi-pencil-square.me-2
                    span Modify
                  n-button.ms-1(
                    secondary
                    color='#666'
                    size='large'
                    strong
                    @click='pickerMode = false'
                    )
                    i.bi.bi-x-square.me-2
                    span Discard
                n-button.mt-2(
                  block
                  secondary
                  type='primary'
                  size='large'
                  strong
                  @click='downloadIcsShown = true'
                  )
                  i.bi.bi-calendar3.me-2
                  span Download as .ics...
                n-divider: small.text-muted Quick Access
                ul.nav.nav-pills.flex-column.small
                  li.nav-item
                    a.nav-link.active(href='#now')
                      i.bi.bi-arrow-right-short.me-2
                      span Now
                  li.nav-item(v-for='day of meetingDays')
                    a.nav-link(:href='`#slot-` + day.slug')
                      i.bi.bi-arrow-right-short.me-2
                      span {{day.label}}


    div(style='border-top: 10px solid #F00; margin: 25px 0;')
</template>

<script>
import { h } from 'vue'
import uniqBy from 'lodash/uniqBy'
import { DateTime } from 'luxon'
import {
  NAffix,
  NBadge,
  NButtonGroup,
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NDataTable,
  NDivider,
  NDrawer,
  NDrawerContent,
  NDropdown,
  NInput,
  NMessageProvider,
  NPopover,
  NSelect,
  NTabPane,
  NTabs
  } from 'naive-ui'
import NTheme from '../components/n-theme.vue'
import AgendaDownloadIcs from './AgendaDownloadIcs.vue'
import AgendaFilter from './AgendaFilter.vue'
import AgendaScheduleList from './AgendaScheduleList.vue'
import AgendaScheduleCalendar from './AgendaScheduleCalendar.vue'
import timezones from '../shared/timezones'

export default {
  components: {
    AgendaDownloadIcs,
    AgendaFilter,
    AgendaScheduleList,
    AgendaScheduleCalendar,
    NAffix,
    NBadge,
    NButton,
    NButtonGroup,
    NCheckbox,
    NCheckboxGroup,
    NDataTable,
    NDivider,
    NDrawer,
    NDrawerContent,
    NDropdown,
    NInput,
    NMessageProvider,
    NPopover,
    NSelect,
    NTheme,
    NTabPane,
    NTabs
  },
  props: {
    meeting: {
      type: Object,
      default: () => ({})
    },
    categories: {
      type: Array,
      default: () => ([])
    },
    isCurrentMeeting: {
      type: Boolean,
      default: false
    },
    useCodiMd: {
      type: Boolean,
      default: false
    },
    schedule: {
      type: Array,
      default: () => ([])
    }
  },
  data () {
    return {
      currentTab: 'agenda',
      timezone: DateTime.local().zoneName,
      tabs: [
        { key: 'agenda', title: 'Agenda', icon: 'bi-calendar3' },
        // { key: 'personalize', title: 'Personalize Agenda', icon: 'bi-calendar2-check' },
        { key: 'floorplan', title: 'Floor plan', icon: 'bi-pin-map' },
        { key: 'plaintext', title: 'Plaintext', icon: 'bi-file-text' }
      ],
      scheduleTab: 'list',
      searchText: '',
      downloadIcsShown: false,
      filterShown: false,
      pickerMode: false,
      pickerModeView: false,
      selectedCatSubs: [],
      downloadOptions: [
        {
          label: 'Current Selection...',
          key: 'current',
          icon () {
            return h('i', { class: 'bi bi-calendar2-check' })
          }
        },
        {
          type: 'divider',
          key: 'd1'
        },
        {
          label: 'ART',
          key: 'art'
        },
        {
          label: 'GEN',
          key: 'gen'
        }
      ]
    }
  },
  computed: {
    timezones () { return timezones },
    isTimezoneLocal () { return this.timezone === DateTime.local().zoneName },
    isTimezoneMeeting () { return this.timezone === this.meeting.timezone },
    title () {
      let title = `IETF ${this.meeting.number} Meeting Agenda`
      if (this.timezone === 'UTC') {
        title = `${title} (UTC)`
      }
      if (this.currentTab === 'personalize') {
        title = `${title} Personalization`
      }
      return title
    },
    meetingDate () {
      const start = DateTime.fromISO(this.meeting.startDate).setZone(this.timezone)
      const end = DateTime.fromISO(this.meeting.endDate).setZone(this.timezone)
      if (start.month === end.month) {
        return `${start.toFormat('MMMM d')} - ${end.toFormat('d, y')}`
      } else {
        return `${start.toFormat('MMMM d')} - ${end.toFormat('MMMM d, y')}`
      }
    },
    meetingDays () {
      return uniqBy(this.scheduleAdjusted, 'adjustedStartDate').sort().map(s => ({
        slug: s.id,
        label: DateTime.fromISO(s.adjustedStartDate).toLocaleString(DateTime.DATE_HUGE)
      }))
    },
    scheduleAdjusted () {
      return this.schedule.filter(s => {
        // -> Apply filters
        if (this.selectedCatSubs.length > 0 && !s.filterKeywords.some(k => this.selectedCatSubs.includes(k))) {
          return false
        }
        if (s.type === 'lead') { return false }
        return true
      }).map(s => {
        // -> Adjust times to selected timezone
        const eventStartDate = DateTime.fromISO(s.startDateTime, { zone: this.meeting.timezone }).setZone(this.timezone)
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
    meetingUpdated () {
      return this.meeting.updated ? DateTime.fromISO(this.meeting.updated).setZone(this.timezone).toFormat(`DD 'at' tt ZZZZ`) : false
    }
  },
  created () {
    // Handle loading tab directly based on URL
    if (window.location.pathname.indexOf('-utc') >= 0) {
      this.timezone = 'UTC'
    } else if (window.location.pathname.indexOf('personalize') >= 0) {
      this.currentTab = 'personalize'
    }
  },
  methods: {
    switchTab (key) {
      this.currentTab = key
      window.history.pushState({}, '', key)
    },
    setTimezone (tz) {
      switch (tz) {
        case 'meeting':
          this.timezone = this.meeting.timezone
          break
        case 'local':
          this.timezone = DateTime.local().zoneName
          break
        default:
          this.timezone = tz
          break
      }
    },
    showFilter () {
      this.filterShown = true
    }
  }
}
</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda {
  &-timezone-ddn {
    min-width: 350px;
  }

  &-infonote {
    border: 1px solid $blue-400;
    border-radius: .25rem;
    background: linear-gradient(to top, lighten($blue-100, 2%), lighten($blue-100, 5%));
    box-shadow: inset 0 0 0 1px #FFF;
    padding: 1rem;
    font-size: .9rem;
    color: $blue-700;
  }

  &-quickaccess {
    width: 300px;

    .card {
      width: 300px;
    }

    &-btnrow {
      border: 1px solid #CCC;
      padding: 8px 6px 6px 6px;
      border-radius: 5px;
      display: flex;
      justify-content: stretch;
      position: relative;
      text-align: center;
      margin-top: 12px;

      &-title {
        position: absolute;
        top: -8px;
        font-size: 9px;
        font-weight: 600;
        color: #999;
        left: 50%;
        padding: 0 5px;
        background-color: #FFF;
        transform: translate(-50%, 0);
        text-transform: uppercase;
      }

      button {
        flex: 1;
      }
    }
  }
}
</style>
