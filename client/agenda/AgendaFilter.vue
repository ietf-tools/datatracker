<template lang="pug">
n-drawer(v-model:show='state.isShown', placement='bottom', :height='state.drawerHeight')
  n-drawer-content.agenda-personalize
    template(#header)
      span Filter Areas + Groups
      .agenda-personalize-actions
        n-button.me-2(
          ghost
          color='gray'
          strong
          @click='clearFilter'
          )
          i.bi.bi-slash-square.me-2
          span Clear Selection
        n-button.me-2(
          ghost
          color='gray'
          strong
          @click='cancelFilter'
          )
          i.bi.bi-x-square.me-2
          span Cancel
        n-button(
          primary
          type='success'
          strong
          @click='saveFilter'
          )
          i.bi.bi-check-circle.me-2
          span Apply
    .agenda-personalize-content
      .agenda-personalize-category(
        v-for='(cat, idx) of agendaStore.categories'
        :key='`cat-` + idx'
        :class='{ "col-auto": (cat.length <= 2) }'
        )
        .agenda-personalize-area(
          v-for='area of cat'
          :key='area.keyword'
          )
          .agenda-personalize-areamain
            button(
              v-if='area.keyword'
              @click='toggleFilterArea(area.keyword)'
              )
              i.bi.bi-diagram-3
              span {{area.label}}
          .agenda-personalize-groups
            button.agenda-personalize-group(
              v-for='group of area.children'
              :key='group.keyword'
              :class='{"is-bof": group.is_bof, "is-checked": state.pendingSelection.includes(group.keyword)}'
              @click='toggleFilterGroup(group.keyword)'
              )
              span {{group.label}}
              n-popover(
                v-if='group.is_bof'
                trigger='hover'
                :width='250'
                )
                template(#trigger)
                  span.badge BoF
                span #[a(:href='getUrl(`bofDefinition`)', target='_blank') Birds of a Feather] sessions (BoFs) are initial discussions about a particular topic of interest to the IETF community.
</template>

<script setup>
import { nextTick, reactive, ref, unref, watch } from 'vue'
import intersection from 'lodash/intersection'
import difference from 'lodash/difference'
import union from 'lodash/union'
import {
  NButton,
  NDrawer,
  NDrawerContent,
  NPopover,
  useMessage
} from 'naive-ui'

import { useAgendaStore } from './store'
import { getUrl } from '../shared/urls'

// STORES

const agendaStore = useAgendaStore()

// STATE

const state = reactive({
  drawerHeight: 650,
  isShown: false,
  pendingSelection: []
})

const message = useMessage()

// WATCHERS

watch(() => agendaStore.filterShown, (newValue) => {
  if (newValue) {
    state.drawerHeight = window.innerHeight > 700 ? 650 : window.innerHeight - 50
    state.pendingSelection = unref(agendaStore.selectedCatSubs)
  }
  state.isShown = newValue
})
watch(() => state.isShown, (newValue) => {
  agendaStore.$patch({ filterShown: newValue })
})

// METHODS

function cancelFilter () {
  state.isShown = false
  state.pendingSelection = unref(agendaStore.selectedCatSubs)
}

function saveFilter () {
  const applyLoadingMsg = message.create('Applying filters...', { type: 'loading', duration: 0 })
  setTimeout(() => {
    agendaStore.$patch({ selectedCatSubs: state.pendingSelection })
    agendaStore.persistMeetingPreferences()
    state.isShown = false
    nextTick(() => {
      applyLoadingMsg.destroy()
    })
  }, 500)
}

function clearFilter () {
  state.pendingSelection = []
}

function toggleFilterArea (areaKeyword) {
  const affectedGroups = []
  let isAlreadySelected = false
  // -> Find affected categories / subs
  for (const cat of agendaStore.categories) {
    for (const area of cat) {
      if (area.keyword === areaKeyword) {
        isAlreadySelected = intersection(area.children.map(s => s.keyword), state.pendingSelection).length === area.children.length
      }
      for (const group of area.children) {
        if (group.toggled_by.includes(areaKeyword)) {
          affectedGroups.push(group.keyword)
        }
      }
    }
  }
  // -> Toggle depending on current state
  state.pendingSelection = (isAlreadySelected) ? difference(state.pendingSelection, affectedGroups) : union(state.pendingSelection, affectedGroups)
}

function toggleFilterGroup (key) {
  state.pendingSelection = state.pendingSelection.includes(key) ? state.pendingSelection.filter(k => k !== key) : [...state.pendingSelection, key]
  const affectedGroups = []
  for (const cat of agendaStore.categories) {
    for (const area of cat) {
      for (const group of area.children) {
        if (group.toggled_by.includes(key)) {
          affectedGroups.push(group.keyword)
        }
      }
    }
  }
  if (affectedGroups.length > 0) {
    state.pendingSelection = (!state.pendingSelection.includes(key)) ? difference(state.pendingSelection, affectedGroups) : union(state.pendingSelection, affectedGroups)
  }
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";
@import "../shared/breakpoints";

.agenda-personalize {
  .n-drawer-header {
    padding-top: 10px !important;
    padding-bottom: 10px !important;

    @media screen and (max-width: $bs5-break-sm) {
      padding-left: 10px !important;
      padding-right: 10px !important;
    }

    &__main {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;

      @media screen and (max-width: $bs5-break-sm) {
        justify-content: center;
        flex-wrap: wrap;
        font-size: .9em;
      }
    }
  }

  &-actions {
    @media screen and (max-width: $bs5-break-sm) {
      flex: 0 1 100%;
      margin-top: .75rem;
      display: flex;
      justify-content: center;
    }
  }

  .n-drawer-body-content-wrapper {
    @media screen and (max-width: $bs5-break-sm) {
      padding: 10px !important;
    }
  }

  &-category {
    background-color: $gray-200;
    padding: 5px;
    border-radius: 10px;

    @at-root .theme-dark & {
      background-color: $gray-800;
    }

    &:nth-child(2) {
      background-color: $blue-100;

      @at-root .theme-dark & {
        background-color: $gray-800;
      }

      .agenda-personalize-areamain {
        button {
          color: $blue-600;

          @at-root .theme-dark & {
            color: $blue-100;
          }
        }
      }

      .agenda-personalize-groups {
        background-color: lighten($blue-100, 7%);

        @at-root .theme-dark & {
          background-color: $gray-700;
        }
      }
    }
    &:nth-child(3) {
      background-color: $orange-100;

      @at-root .theme-dark & {
        background-color: $gray-800;
      }

      .agenda-personalize-areamain {
        button {
          color: $orange-600;

          @at-root .theme-dark & {
            color: $orange-100;
          }
        }
      }

      .agenda-personalize-groups {
        background-color: lighten($orange-100, 7%);

        @at-root .theme-dark & {
          background-color: $gray-700;
        }
      }
    }

    & + & {
      margin-top: 10px;
    }
  }

  &-area {
    display: flex;

    & + & {
      margin-top: 5px;
    }
  }

  &-areamain {
    flex: 0 1 200px;
    padding-right: 5px;

    @media screen and (max-width: $bs5-break-sm) {
      flex-basis: 60px;
    }

    button {
      width: 100%;
      height: 100%;
      border-radius: 5px;
      border: 1px solid #FFF;
      background-color: #FFF;
      color: $gray-600;
      box-shadow: 1px 1px 0px 0px rgba(0,0,0,.1);
      transition: background-color .5s ease;
      position: relative;

      @at-root .theme-dark & {
        background-color: $gray-600;
        border-color: $gray-700;
        color: #FFF;
      }

      > .bi {
        margin-right: .5rem;
      }

      @media screen and (max-width: $bs5-break-sm) {
        font-size: .8em;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;

        > .bi {
          margin-right: 0;
        }
      }

      &:hover {
        background-color: rgba(255,255,255,.4);
      }

      &:active {
        box-shadow: none;
        background-color: #FFF;
      }
    }
  }

  &-groups {
    background-color: $gray-100;
    padding: 0;
    border-radius: 5px;
    flex: 1;
    display: flex;
    flex-wrap: wrap;

    @at-root .theme-dark & {
      background-color: $gray-700;
    }
  }

  &-group {
    display: flex;
    align-items: center;
    padding: 5px 8px;
    position: relative;
    border: none;
    border-left: 1px solid #FFF;
    border-right: 1px solid rgba(0,0,0,.1);
    background-color: rgba(255,255,255,.7);
    color: $gray-600;
    margin-right: 0px;

    @at-root .theme-dark & {
      background-color: $gray-600;
      border-color: $gray-700;
      color: #FFF;
    }

    @media screen and (max-width: $bs5-break-sm) {
      font-size: .9em;
    }

    &:first-child {
      border-top-left-radius: 5px;
      border-bottom-left-radius: 5px;
    }
    &:last-child {
      border-top-right-radius: 5px;
      border-bottom-right-radius: 5px;
    }

    &.is-bof {
      border-top: 1px dotted $teal-300;
      border-bottom: 2px solid $teal-300;
      border-right: 2px solid $teal-300;
    }

    &.is-checked {
      background-color: $blue;
      color: #FFF;
    }

    .badge {
      font-size: 10px;
      background-color: $teal;
      margin-left: 5px;
    }
  }
}
</style>
