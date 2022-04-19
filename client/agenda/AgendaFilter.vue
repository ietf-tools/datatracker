<template lang="pug">
n-drawer(v-model:show='isShown', placement='bottom', :height='650')
  n-drawer-content.agenda-personalize
    template(#header)
      span Filter Agenda
      div
        n-button.me-2(
          ghost
          color='gray'
          strong
          @click='clearFilter'
          )
          i.bi.bi-slash-square.me-2
          span Clear Selection
        n-button(
          primary
          type='success'
          strong
          @click='saveFilter'
          )
          i.bi.bi-check-circle.me-2
          span Apply
    .agenda-personalize-content
      n-checkbox-group(v-model:value='pendingSelection')
        .agenda-personalize-grcat(
          v-for='(grcat, idx) of categories'
          :key='`grcat-` + idx'
          :class='{ "col-auto": (grcat.length <= 2) }'
          )
          .agenda-personalize-cat(
            v-for='cat of grcat'
            :key='cat.keyword'
            )
            .agenda-personalize-catmain
              button(
                v-if='cat.keyword'
                @click='toggleFilterCat(cat.keyword)'
                )
                i.bi.bi-grid-fill.me-2
                span {{cat.label}}
            .agenda-personalize-catsubs
              .agenda-personalize-sub(
                v-for='sub of cat.children'
                :key='sub.keyword'
                :class='{"is-bof": sub.is_bof}'
                )
                n-checkbox(
                  :value='sub.keyword'
                  :label='sub.label'
                  @click='filterCheckboxChanged(sub.keyword)'
                  )
                n-popover(
                  v-if='sub.is_bof'
                  trigger='hover'
                  :width='250'
                  )
                  template(#trigger)
                    span.badge BoF
                  span #[a(href='https://www.ietf.org/how/bofs/', target='_blank') Birds of a Feather] sessions (BoFs) are initial discussions about a particular topic of interest to the IETF community.
</template>

<script>
import { ref, toRefs, watch } from 'vue'
import intersection from 'lodash/intersection'
import difference from 'lodash/difference'
import union from 'lodash/union'
import {
  NButton,
  NCheckbox,
  NCheckboxGroup,
  NDrawer,
  NDrawerContent,
  NPopover
  } from 'naive-ui'

export default {
  components: {
    NButton,
    NCheckbox,
    NCheckboxGroup,
    NDrawer,
    NDrawerContent,
    NPopover
  },
  props: {
    shown: {
      type: Boolean,
      required: true,
      default: false
    },
    selection: {
      type: Array,
      required: true
    },
    categories: {
      type: Array,
      required: true
    }
  },
  emit: ['update:shown', 'update:selection'],
  setup (props, context) {
    const { categories, shown, selection } = toRefs(props)
    const isShown = ref(shown.value)
    const pendingSelection = ref(selection.value)

    watch(shown, (newValue) => {
      isShown.value = newValue
    })
    watch(isShown, (newValue) => {
      context.emit('update:shown', newValue)
    })

    const saveFilter = () => {
      context.emit('update:selection', pendingSelection.value)
      context.emit('update:shown', false)
      isShown.value = false
    }

    const clearFilter = () => {
      pendingSelection.value = []
    }

    const toggleFilterCat = (catKeyword) => {
      const affectedSubs = []
      let isAlreadySelected = false
      // -> Find affected categories / subs
      for (const catgr of props.categories) {
        for (const cat of catgr) {
          if (cat.keyword === catKeyword) {
            isAlreadySelected = intersection(cat.children.map(s => s.keyword), pendingSelection.value).length === cat.children.length
          }
          for (const sub of cat.children) {
            if (sub.toggled_by.includes(catKeyword)) {
              affectedSubs.push(sub.keyword)
            }
          }
        }
      }
      // -> Toggle depending on current state
      pendingSelection.value = (isAlreadySelected) ? difference(pendingSelection.value, affectedSubs) : union(pendingSelection.value, affectedSubs)
    }

    const filterCheckboxChanged = (key) => {
      const affectedSubs = []
      for (const catgr of props.categories) {
        for (const cat of catgr) {
          for (const sub of cat.children) {
            if (sub.toggled_by.includes(key)) {
              affectedSubs.push(sub.keyword)
            }
          }
        }
      }
      if (affectedSubs.length > 0) {
        pendingSelection.value = (!pendingSelection.value.includes(key)) ? difference(pendingSelection.value, affectedSubs) : union(pendingSelection.value, affectedSubs)
      }
    }

    return {
      isShown,
      pendingSelection,
      categories,
      clearFilter,
      saveFilter,
      toggleFilterCat,
      filterCheckboxChanged
    }
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

  &-grcat {
    background-color: $gray-200;
    padding: 5px;
    border-radius: 10px;

    &:nth-child(2) {
      background-color: $teal-100;

      .agenda-personalize-catmain {
        button {
          color: $teal-600;
        }
      }

      .agenda-personalize-catsubs {
        background-color: lighten($teal-100, 7%);
      }
    }
    &:nth-child(3) {
      background-color: $orange-100;

      .agenda-personalize-catmain {
        button {
          color: $orange-600;
        }
      }

      .agenda-personalize-catsubs {
        background-color: lighten($orange-100, 7%);
      }
    }

    & + & {
      margin-top: 10px;
    }
  }

  &-cat {
    display: flex;

    & + & {
      margin-top: 5px;
    }
  }

  &-catmain {
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

  &-catsubs {
    background-color: $gray-100;
    padding: 5px;
    border-radius: 5px;
    flex: 1;
    display: flex;
    flex-wrap: wrap;
  }

  &-sub {
    display: flex;
    align-items: center;
    padding: 5px;
    position: relative;

    &.is-bof {
      border-radius: 5px;
      border: 1px dotted $pink-300;
      margin: 0 3px;
    }

    .badge {
      font-size: 10px;
      background-color: $pink;
    }

    button {
      width: 100%;
      border: none;
      background-color: transparent;
      color: $gray-600;

      &:hover {
        border-color: $blue;
      }
    }
  }
}
</style>
