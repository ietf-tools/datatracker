<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='650')
  n-drawer-content.agenda-personalize
    template(#header)
      span Filter Areas + Groups
      div
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
              i.bi.bi-diagram-3.me-2
              span {{area.label}}
          .agenda-personalize-groups
            button.agenda-personalize-group(
              v-for='group of area.children'
              :key='group.keyword'
              :class='{"is-bof": group.is_bof, "is-checked": pendingSelection.includes(group.keyword)}'
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
                span #[a(href='https://www.ietf.org/how/bofs/', target='_blank') Birds of a Feather] sessions (BoFs) are initial discussions about a particular topic of interest to the IETF community.
</template>

<script setup>
import { ref, unref, watch } from 'vue'
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

// STORES

const agendaStore = useAgendaStore()

// STATE

const isShown = ref(false)
const pendingSelection = ref([])
const message = useMessage()

// WATCHERS

watch(() => agendaStore.filterShown, (newValue) => {
  if (newValue) {
    pendingSelection.value = unref(agendaStore.selectedCatSubs)
  }
  isShown.value = newValue
})
watch(isShown, (newValue) => {
  agendaStore.$patch({ filterShown: newValue })
})

// METHODS

function cancelFilter () {
  isShown.value = false
  pendingSelection.value = unref(agendaStore.selectedCatSubs)
}

function saveFilter () {
  agendaStore.$patch({ selectedCatSubs: pendingSelection.value })
  isShown.value = false
}

function clearFilter () {
  pendingSelection.value = []
}

function toggleFilterArea (areaKeyword) {
  const affectedGroups = []
  let isAlreadySelected = false
  // -> Find affected categories / subs
  for (const cat of agendaStore.categories) {
    for (const area of cat) {
      if (area.keyword === areaKeyword) {
        isAlreadySelected = intersection(area.children.map(s => s.keyword), pendingSelection.value).length === area.children.length
      }
      for (const group of area.children) {
        if (group.toggled_by.includes(areaKeyword)) {
          affectedGroups.push(group.keyword)
        }
      }
    }
  }
  // -> Toggle depending on current state
  pendingSelection.value = (isAlreadySelected) ? difference(pendingSelection.value, affectedGroups) : union(pendingSelection.value, affectedGroups)
}

function toggleFilterGroup (key) {
  pendingSelection.value = pendingSelection.value.includes(key) ? pendingSelection.value.filter(k => k !== key) : [...pendingSelection.value, key]
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
    pendingSelection.value = (!pendingSelection.value.includes(key)) ? difference(pendingSelection.value, affectedGroups) : union(pendingSelection.value, affectedGroups)
  }
}

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.agenda-personalize {
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

  &-category {
    background-color: $gray-200;
    padding: 5px;
    border-radius: 10px;

    &:nth-child(2) {
      background-color: $teal-100;

      .agenda-personalize-areamain {
        button {
          color: $teal-600;
        }
      }

      .agenda-personalize-groups {
        background-color: lighten($teal-100, 7%);
      }
    }
    &:nth-child(3) {
      background-color: $orange-100;

      .agenda-personalize-areamain {
        button {
          color: $orange-600;
        }
      }

      .agenda-personalize-groups {
        background-color: lighten($orange-100, 7%);
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

    &:first-child {
      border-top-left-radius: 5px;
      border-bottom-left-radius: 5px;
    }
    &:last-child {
      border-top-right-radius: 5px;
      border-bottom-right-radius: 5px;
    }

    &.is-bof {
      border-top: 1px dotted $pink-300;
      border-bottom: 2px solid $pink-300;
      border-right: 2px solid $pink-300;
    }

    &.is-checked {
      background-color: $blue;
      color: #FFF;
    }

    .badge {
      font-size: 10px;
      background-color: $pink;
      margin-left: 5px;
    }
  }
}
</style>
