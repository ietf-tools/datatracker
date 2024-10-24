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

type Props = {
  val: ReturnType<typeof h> | any
}

defineProps<Props>()
</script>
