<template>
  <template v-if="isVNode(val)">
    <component :is="val" />
  </template>
  <template v-else>
    {{ val }}
  </template>
</template>
<script setup lang="ts">
import { isVNode } from 'vue'

const props = defineProps({
  /**
   * Definitions of columns and their labels
   **/
  val: {
    type: [String, Object],
    required: true
  },
})
</script>
