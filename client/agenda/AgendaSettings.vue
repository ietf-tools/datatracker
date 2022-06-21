<template lang="pug">
n-drawer(v-model:show='isShown', placement='right', :width='500')
  n-drawer-content.agenda-settings
    template(#header)
      span Agenda Settings
      div
        n-button(
          ghost
          color='gray'
          strong
          @click='close'
          )
          i.bi.bi-x-lg.me-2
          span Close

    .agenda-settings-content

      n-divider(title-placement='left')
        i.bi.bi-globe.me-2
        small Timezone
      n-button-group.mt-2(style='justify-content: stretch; width: 100%;')
        n-button(
          style='flex-grow: 1;'
          :type='agendaStore.isTimezoneMeeting ? `primary` : `default`'
          @click='setTimezone(`meeting`)'
          ) Meeting
        n-button(
          style='flex-grow: 1;'
          :type='agendaStore.isTimezoneLocal ? `primary` : `default`'
          @click='setTimezone(`local`)'
          ) Local
        n-button(
          style='flex-grow: 1;'
          :type='agendaStore.timezone === `UTC` ? `primary` : `default`'
          @click='setTimezone(`UTC`)'
          ) UTC
      n-select.mt-2(
        v-model:value='agendaStore.timezone'
        :options='timezones'
        placeholder='Select Time Zone'
        filterable
        )

      n-divider(title-placement='left')
        i.bi.bi-sliders.me-2
        small Display
      .d-flex.align-items-center.mt-3
        n-switch.me-3(v-model:value='agendaStore.listDayCollapse', disabled)
        span.small Collapse Days by Default
      .d-flex.align-items-center.mt-3
        n-switch.me-3(v-model:value='agendaStore.areaIndicatorsShown')
        span.small Display Group Area Indicators
      .d-flex.align-items-center.mt-3
        n-switch.me-3(v-model:value='agendaStore.infoNoteShown')
        span.small.me-2 Display Current Meeting Info Note
        n-popover
          template(#trigger)
            i.bi.bi-info-circle
          span Any update to the note will result in this setting being turned back on.
      .d-flex.align-items-center.mt-3
        n-switch.me-3(v-model:value='agendaStore.floorIndicatorsShown')
        span.small Display Floor Indicators
      .d-flex.align-items-center.mt-3
        n-switch.me-3(v-model:value='agendaStore.redhandShown')
        span.small Display Realtime Red Line

      n-divider(title-placement='left')
        i.bi.bi-clock-history.me-2
        small Override Current Local DateTime
      n-date-picker(
        v-model:value='state.currentDateTime'
        type='datetime'
        style='width: 100%;'
        )
        template(#date-icon)
          i.bi.bi-calendar-check
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { DateTime } from 'luxon'
import {
  NButton,
  NButtonGroup,
  NDatePicker,
  NDivider,
  NDrawer,
  NDrawerContent,
  NPopover,
  NSelect,
  NSwitch,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'
import timezones from '../shared/timezones'

// STORES

const agendaStore = useAgendaStore()

// STATE

const isShown = ref(false)
const state = reactive({
  currentDateTime: agendaStore.currentDateTime.toMillis()
})
const message = useMessage()

// WATCHERS

watch(() => agendaStore.settingsShown, (newValue) => {
  isShown.value = newValue
})
watch(isShown, (newValue) => {
  agendaStore.$patch({ settingsShown: newValue })
})
watch(() => agendaStore.infoNoteShown, () => {
  agendaStore.persistMeetingPreferences()
})

// METHODS

function close () {
  isShown.value = false
}

function setTimezone (tz) {
  switch (tz) {
    case 'meeting':
      agendaStore.$patch({ timezone: agendaStore.meeting.timezone })
      break
    case 'local':
      agendaStore.$patch({ timezone: DateTime.local().zoneName })
      break
    default:
      agendaStore.$patch({ timezone: tz })
      break
  }
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-settings {
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

  .n-divider {
    margin-top: 24px;
    margin-bottom: 12px;

    &:first-child {
      margin-top: 0;
    }
  }
}
</style>
