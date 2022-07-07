<template lang="pug">
.floorplan
  h1
    span #[strong IETF {{agendaStore.meeting.number}}] Floor Plan
    .meeting-h1-badges
      span.meeting-warning(v-if='agendaStore.meeting.warningNote') {{agendaStore.meeting.warningNote}}
      span.meeting-beta BETA
  h4
    span {{agendaStore.meeting.city}}, {{ meetingDate }}

  .floorplan-topnav.my-3
    meeting-navigation

  nav.floorplan-floors.nav.nav-pills.nav-justified
    a.nav-link(
      v-for='floor of agendaStore.floors'
      :key='floor.id'
      :name='floor.name'
      :class='{ active: state.currentFloor === floor.id }'
      @click='state.currentFloor = floor.id'
      )
      i.bi.bi-arrow-down-right-square.me-2
      span {{floor.name}}

  .row.mt-3
    .col-auto
      .floorplan-rooms.list-group.shadow-sm
        a.list-group-item.list-group-item-action(
          v-for='room of floor.rooms'
          :key='room.id'
          :class='{ active: state.currentRoom === room.id }'
          :aria-current='state.currentRoom === room.id'
          @click='state.currentRoom = room.id'
          )
          .badge.me-3 {{floor.short}}
          span
            strong {{room.name}}
            small {{room.functionalName}}
    .col
      .card.floorplan-plan.shadow-sm
        .floorplan-plan-pin(
          v-if='state.currentRoom'
          :style='room.styles'
          )
        img(:src='floor.image')

</template>

<script setup>
import { computed, onMounted, reactive, watch } from 'vue'
import find from 'lodash/find'
import { DateTime } from 'luxon'
import { useAgendaStore } from './store' 

import MeetingNavigation from './MeetingNavigation.vue'

// STORES

const agendaStore = useAgendaStore()

// STATE

const state = reactive({
  currentFloor: null,
  currentRoom: null
})

// COMPUTED

const meetingDate = computed(() => {
  const start = DateTime.fromISO(agendaStore.meeting.startDate).setZone(agendaStore.timezone)
  const end = DateTime.fromISO(agendaStore.meeting.endDate).setZone(agendaStore.timezone)
  if (start.month === end.month) {
    return `${start.toFormat('MMMM d')} - ${end.toFormat('d, y')}`
  } else {
    return `${start.toFormat('MMMM d')} - ${end.toFormat('MMMM d, y')}`
  }
})

const floor = computed(() => {
  return state.currentFloor ? find(agendaStore.floors, ['id', state.currentFloor]) : {}
})

const room = computed(() => {
  return state.currentRoom ? find(floor.value?.rooms, ['id', state.currentRoom]) : {}
})

// WATCHERS

watch(() => agendaStore.floors, (newValue) => {
  if (newValue && newValue.length > 0) {
    state.currentFloor = newValue[0].id
  }
})

// MOUNTED

onMounted(() => {
  agendaStore.hideLoadingScreen()
  if (agendaStore.floors?.length > 0) {
    state.currentFloor = agendaStore.floors[0].id
  }
})

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.floorplan {
  min-height: 500px;
  font-weight: 460;

  > h1 {
    font-weight: 500;
    color: $gray-700;
    display: flex;
    justify-content: space-between;
    align-items: center;

    strong {
      font-weight: 700;
      background: linear-gradient(220deg, $blue-500 20%, $purple-500 70%);
      background-clip: text;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      box-decoration-break: clone;
    }
  }

  nav.floorplan-floors {
    padding: 5px;
    background-color: #FFF;
    border: 1px solid $gray-300;
    border-radius: 5px;
    font-weight: 500;

    a {
      cursor: pointer;

      &:not(.active):hover {
        background-color: rgba($blue-100, .25);
      }
    }
  }

  &-rooms {
    width: 350px;
    font-size: .9rem;
    font-weight: 500;

    a {
      cursor: pointer;
      display: flex;
      align-items: center;

      .badge {
        background-color: $blue-500;
        color: #FFF;
      }

      span {
        display: block;
      }

      strong {
        font-weight: 600;
      }

      small {
        display: block;
      }

      &.active {
        .badge {
          background-color: $blue-100;
          color: $blue-500;
        }
      }
    }
  }

  &-plan {
    position: relative;

    img {
      width: 100%;
      animation: planInAnim 1s ease-out;
    }

    &-pin {
      position: absolute;
      top: 100px;
      left: 100px;
      width: 20px;
      height: 20px;
      background-color: #F00;
    }
  }
}

@keyframes planInAnim {
  0% {
    opacity: 0;
    transform: scale(.9, .9);
  }
  100% {
    opacity: 1;
    transform: scale(1, 1);
  }
}
</style>
