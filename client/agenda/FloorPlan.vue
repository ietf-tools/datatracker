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
        router-link.list-group-item.list-group-item-action(
          v-for='room of floor.rooms'
          :key='room.id'
          :class='{ active: state.currentRoom === room.id }'
          :aria-current='state.currentRoom === room.id'
          @click='state.currentRoom = room.id'
          :to='{ query: { room: xslugify(room.name) } }'
          )
          .badge.me-3 {{floor.short}}
          span
            strong {{room.name}}
            small {{room.functionalName}}
    .col
      .card.floorplan-plan.shadow-sm
        .floorplan-plan-pin(
          v-if='state.currentRoom && state.isLoaded'
          :style='pinPosition'
          )
          i.bi.bi-geo-alt-fill
        img(
          :src='floor.image'
          ref='planImage'
          @load='planImageLoaded'
          )

</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import find from 'lodash/find'
import xslugify from '../shared/xslugify'
import { DateTime } from 'luxon'
import { useRoute } from 'vue-router'
import { useAgendaStore } from './store' 

import MeetingNavigation from './MeetingNavigation.vue'

// STORES

const agendaStore = useAgendaStore()

// ROUTER

const route = useRoute()

// STATE

const state = reactive({
  currentFloor: null,
  currentRoom: null,
  desiredRoom: null,
  isLoaded: false,
  awaitsPinDrop: false,
  xRatio: 1,
  yRatio: 1
})

// REFS

const planImage = ref(null)

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

const pinPosition = computed(() => {
  if (!state.currentRoom || !floor.value.rooms?.some(r => r.id === state.currentRoom)) {
    return {
      display: 'none'
    }
  } else {
    const room = find(floor.value.rooms, ['id', state.currentRoom])
    const xPos = Math.round((room.left + (room.right - room.left) / 2) * state.xRatio) - 25
    const yPos = Math.round((room.top + (room.bottom - room.top) / 2) * state.yRatio) - 40
    return {
      display: 'block',
      top: `${yPos}px`,
      left: `${xPos}px`
    }
  }
})

// WATCHERS

watch(() => agendaStore.floors, (newValue) => {
  if (newValue && newValue.length > 0 && !state.currentFloor) {
    state.currentFloor = newValue[0].id
  }
  handleDesiredRoom()
})
watch(() => state.currentFloor, () => {
  state.isLoaded = false
})
watch(() => state.currentRoom, () => {
  nextTick(() => {
    computePlanSizeRatio()
    setTimeout(() => {
      if (state.isLoaded) {
        document.querySelector('.floorplan-plan-pin').scrollIntoView({ behavior: 'smooth' })
      } else {
        state.awaitsPinDrop = true
      }
    }, 100)
  })
})
watch(() => agendaStore.viewport, () => {
  nextTick(() => {
    computePlanSizeRatio()
  })
})

// METHODS

function computePlanSizeRatio () {
  if (!planImage.value || !state.currentFloor) {
    return
  }
  state.xRatio = planImage.value.width / floor.value.width
  state.yRatio = planImage.value.height / floor.value.height
}

function planImageLoaded () {
  setTimeout(() => {
    state.isLoaded = true
    nextTick(() => {
      computePlanSizeRatio()
      if (state.awaitsPinDrop) {
        setTimeout(() => {
          document.querySelector('.floorplan-plan-pin').scrollIntoView({ behavior: 'smooth' })
        }, 100)
      }
    })
  }, 1000)
}

function handleDesiredRoom () {
  if (state.desiredRoom) {
    for (const fl of agendaStore.floors) {
      const rm = find(fl.rooms, ['slug', state.desiredRoom])
      if (rm) {
        state.currentFloor = fl.id
        state.currentRoom = rm.id
      }
    }
  }
}

// --------------------------------------------------------------------
// Handle browser resize
// --------------------------------------------------------------------

const resizeObserver = new ResizeObserver(entries => {
  agendaStore.$patch({ viewport: Math.round(window.innerWidth) })
})

onMounted(() => {
  resizeObserver.observe(planImage.value)
})

onBeforeUnmount(() => {
  resizeObserver.unobserve(planImage.value)
})

// MOUNTED

onMounted(() => {
  agendaStore.hideLoadingScreen()
  if (agendaStore.floors?.length > 0) {
    state.currentFloor = agendaStore.floors[0].id
  }
  if (route.query.room) {
    state.desiredRoom = route.query.room
    handleDesiredRoom()
  }
})

</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.floorplan {
  min-height: 500px;
  font-weight: 460;

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
      color: $red-500;
      font-size: 50px;
      animation: pinDropAnim .6s ease-out;
      
      > .bi {
        animation: pinColorAnim 1.2s ease infinite;
        text-shadow: 0 5px 10px #000;
      }
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

@keyframes pinDropAnim {
  0% {
    opacity: 0;
    transform: translateY(-200px);
  }
  60% {
    opacity: 1;
    transform: translateY(10px);
  }
  80% {
    transform: translateY(-5px);
  }
  100% {
    transform: translateY(0);
  }
}

@keyframes pinColorAnim {
  0% {
    color: $red-500;
  }
  33% {
    color: $yellow-500;
  }
  66% {
    color: $blue-500;
  }
  100% {
    color: $red-500;
  }
}
</style>
