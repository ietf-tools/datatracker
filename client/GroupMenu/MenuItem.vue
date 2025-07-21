<template>
  <div v-if="props.item.type === 'link'">
    <NavigationMenuLink as-child>
      <a :href="item.href" class="NavigationMenuLevel2">
        {{ item.label }}
      </a>
    </NavigationMenuLink>
  </div>
  <div v-else-if="props.item.type === 'divider'">
    <hr>
  </div>
  <div v-else-if="props.item.type === 'group'">
    <fieldset>
      <legend>
        <NavigationMenuLink
          v-if="item.href"
          as-child
        >
          <a
            :href="item.href"
            class="legend-link"
          >
            {{ item.header }}
          </a>
        </NavigationMenuLink>
        <span
          v-else
          class="legend"
        >
          {{ item.header }}
        </span>
      </legend>
      <NavigationMenuSub default-value="0">
        <NavigationMenuList>
          <NavigationMenuItem
            v-for="(level1, level1Index) in item.children"
            :key="level1Index"
            :value="level1Index"
          >
            <NavigationMenuTrigger> {{ level1. }}</NavigationMenuTrigger>
            <NavigationMenuContent>
              <MenuItem
                :item="level1"
                :depth="props.depth + 1"
              />
            </NavigationMenuContent>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenuSub>
      <ul class="NavigationMenu-NoList">
        <li
          
        >

        </li>
      </ul>
    </fieldset>
  </div>
</template>

<script setup lang="js">
import {
  NavigationMenuContent,
  NavigationMenuIndicator,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuRoot,
  NavigationMenuSub,
  NavigationMenuTrigger,
  NavigationMenuViewport,
} from 'reka-ui'
import MenuItem from './MenuItem.vue'

const props = defineProps({
  item: {
    type: Object,
    required: true
  },
  depth: {
    type: Number,
    required: true
  }
})

</script>

<style scoped>

.legend {
  font-size: 12px;
  color: #999;
}

.legend-link {
  font-size: 12px;
  color: #fff;
}

</style>
