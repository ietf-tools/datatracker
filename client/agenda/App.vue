<template lang="pug">
n-theme
  n-message-provider
    router-view.meeting
</template>

<script setup>
import { NMessageProvider } from 'naive-ui'

import { useAgendaStore } from './store'

import NTheme from '../components/n-theme.vue'

// STORES

const agendaStore = useAgendaStore()

// INIT

agendaStore.fetch()
</script>

<style lang="scss">
@import "bootstrap/scss/functions";
@import "bootstrap/scss/variables";

.meeting {
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

  &-h1-badges {
    display: flex;
    justify-content: end;
    align-items: center;

    > span {
      font-size: 13px;
      font-weight: 700;
      background-color: $pink-500;
      box-shadow: 0 0 5px 0 rgba($pink-500, .5);
      color: #FFF;
      padding: 5px 8px;
      border-radius: 6px;

      & + span {
        margin-left: 10px;
      }
    }
  }

  &-warning {
    background-color: $red-500 !important;
    box-shadow: 0 0 5px 0 rgba($red-500, .5) !important;
    color: #FFF;
    animation: warningBorderFlash 1s ease infinite;
  }
}
</style>
