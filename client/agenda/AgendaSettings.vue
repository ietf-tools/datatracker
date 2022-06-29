<template lang="pug">
n-drawer(v-model:show='isShown', placement='right', :width='500')
  n-drawer-content.agenda-settings
    template(#header)
      span Agenda Settings
      .d-flex.justify-content-end
        n-dropdown(
          :options='actionOptions'
          size='large'
          :show-arrow='true'
          trigger='click'
          @select='actionClick'
          )
          n-button.me-2(
            ghost
            color='#6c757d'
            strong
            )
            i.bi.bi-three-dots-vertical
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
        span.small.me-2 Display Group Area Indicators
        n-popover
          template(#trigger)
            i.bi.bi-info-circle
          span Will not be shown on smaller screens, regardless of this setting.
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
        n-switch.me-3(v-model:value='agendaStore.redhandShown', disabled)
        span.small Display Realtime Red Line

      n-divider(title-placement='left')
        i.bi.bi-palette.me-2
        small Custom Colors / Tags
      .d-flex.align-items-center.mt-3(v-for='cl of state.colors')
        n-color-picker.me-3(
          :modes='[`hex`]'
          :render-label='() => {}'
          :show-alpha='false'
          size='small'
          :swatches='swatches'
          v-model:value='cl.hex'
        )
        n-input(
          type='text'
          v-model:value='cl.tag'
        )

      n-divider(title-placement='left')
        i.bi.bi-clock-history.me-2
        small Override Local DateTime
      n-date-picker(
        v-model:value='state.currentDateTime'
        type='datetime'
        style='width: 100%;'
        )
        template(#date-icon)
          i.bi.bi-calendar-check
</template>

<script setup>
import { h, onMounted, ref, reactive, watch } from 'vue'
import { DateTime } from 'luxon'
import cloneDeep from 'lodash/cloneDeep'
import debounce from 'lodash/debounce'
import { fileOpen } from 'browser-fs-access'
import FileSaver from 'file-saver'
import {
  NButton,
  NButtonGroup,
  NColorPicker,
  NDatePicker,
  NDivider,
  NDrawer,
  NDrawerContent,
  NDropdown,
  NInput,
  NPopover,
  NSelect,
  NSwitch,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'
import timezones from '../shared/timezones'

// MESSAGE PROVIDER

const message = useMessage()

// STORES

const agendaStore = useAgendaStore()

// STATE

const isShown = ref(false)
const state = reactive({
  currentDateTime: agendaStore.currentDateTime.toMillis(),
  colors: []
})
const swatches = [
  '#0d6efd',
  '#6610f2',
  '#6f42c1',
  '#d63384',
  '#dc3545',
  '#fd7e14',
  '#ffc107',
  '#198754',
  '#20c997',
  '#0dcaf0',
  '#adb5bd',
  '#000000'
]
const actionOptions = [
  {
    label: 'Export Configuration...',
    key: 'export',
    icon: () => h('i', { class: 'bi bi-box-arrow-down' })
  },
  {
    label: 'Import Configuration...',
    key: 'import',
    icon: () => h('i', { class: 'bi bi-box-arrow-in-down' })
  },
  {
    type: 'divider',
    key: 'divider1'
  },
  {
    label: 'Clear Color Assignments',
    key: 'clearColors',
    icon: () => h('i', { class: 'bi bi-palette' })
  }
]

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
watch(() => state.colors, debounce(() => {
  agendaStore.$patch({
    colors: cloneDeep(state.colors)
  })
}, 1000), { deep: true })

// METHODS

function close () {
  isShown.value = false
}

async function actionClick (key) {
  switch (key) {
    case 'export': {
      try {
        const configBlob = new Blob([
          JSON.stringify({
            areaIndicatorsShown: agendaStore.areaIndicatorsShown,
            colors: agendaStore.colors,
            floorIndicatorsShown: agendaStore.floorIndicatorsShown,
            listDayCollapse: agendaStore.listDayCollapse,
            redhandShown: agendaStore.redhandShown
          }, null, 2)
        ], {
          type: 'application/json;charset=utf-8'
        })
        FileSaver.saveAs(configBlob, 'agenda-settings.json')
      } catch (err) {
        console.warn(err)
        message.error('Failed to generate JSON config for download.')
      }
      break
    }
    case 'import': {
      try {
        const blob = await fileOpen({
          mimeTypes: ['application/json'],
          extensions: ['.json'],
          startIn: 'downloads',
          excludeAcceptAllOption: true
        })
        const configRaw = await blob.text()
        const configJson = JSON.parse(configRaw)
        if (!Array.isArray(configJson.colors) || configJson.colors.length !== agendaStore.colors.length) {
          throw new Error('Config contains invalid colors array.')
        }
        agendaStore.$patch({
          areaIndicatorsShown: configJson.areaIndicatorsShown === true,
          colors: configJson.colors.map(c => ({
            hex: c.hex || '#FF0000',
            tag: c.tag || 'Unknown Color'
          })),
          floorIndicatorsShown: configJson.floorIndicatorsShown === true,
          listDayCollapse: configJson.listDayCollapse === true,
          redhandShown: configJson.redhandShown === true
        })
        state.colors = cloneDeep(agendaStore.colors)
      } catch (err) {
        console.warn(err)
        message.error('Failed to import JSON config.')
      }
      break
    }
    case 'clearColors': {
      agendaStore.colorAssignments = {}
      agendaStore.persistMeetingPreferences()
      message.info('All color assignments cleared.')
      close()
    }
  }
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

// MOUNTED

onMounted(() => {
  state.currentDateTime = agendaStore.currentDateTime.toMillis()
  state.colors = cloneDeep(agendaStore.colors)
})

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

  .n-color-picker {
    width: 40px;
  }
}
</style>
