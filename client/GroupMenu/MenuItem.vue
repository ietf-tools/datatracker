<template>
  <div v-if="props.item.type === 'link'">
    <NavigationMenuLink as-child>
      <a
        :href="item.href"
        class="reka-link"
      >
        {{ item.label }}
      </a>
    </NavigationMenuLink>
  </div>
  <div v-if="props.item.type === 'header'">
    <span class="reka-heading">{{ props.item.text }}</span>
  </div>
  <div v-else-if="props.item.type === 'divider'">
    <hr class="reka-divider">
  </div>
  <div v-else-if="props.item.type === 'submenuList'">
    <NavigationMenuSub default-value="0">
      <NavigationMenuList class="reka-submenulist">
        <NavigationMenuItem
          v-for="(menuItem, menuItemIndex) in item.children"
          :key="menuItemIndex"
          :value="menuItemIndex"
        >
          <NavigationMenuTrigger class="reka-menuitem">
            {{ menuItem.label }}
          </NavigationMenuTrigger>
          <NavigationMenuContent class="reka-menuitem-content">
            <MenuItem
              v-for="(level0, level0Index) in menuItem.children"
              :key="level0Index"
              :item="level0"
              :depth="props.depth + 1"
            />
          </NavigationMenuContent>
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenuSub>
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

<style>

.reka-heading {
  padding: 0.5rem 1rem;
  color: #6c757d;
  font-size: .875rem;
}

.reka-divider {
  height: 0px;
  border-top: solid 1px #ffffff26;
  margin: 0.5rem 0
}

.reka-submenulist {
  list-style: none;
  padding: 0;
  margin: 0;
}

.reka-menuitem {
  color: #dee2e6;
  padding: 0.25rem 1rem;
  width: 100%;
  display: block;
  text-align: left;
  background: transparent;
  border: 0;
}

.reka-menuitem:hover,
.reka-menuitem:focus {
  color: #dee2e6;
  background-color: #2b3035;
}

.reka-menuitem::after {
  vertical-align: .255em;
  content: "";
  border: .3em solid #0000;
  border-left-color: currentColor;
  border-right: 0;
  margin-left: .255em;
  display: inline-block;
}

.reka-menuitem-arrow {
  position: relative;
  top: -0.2rem;
  font-size: 0.6rem;
}

.reka-menuitem-content {
  position: absolute;
  left: 95%;
  animation-duration: 250ms;
  animation-timing-function: ease;
  background-color: #212529;
  border: solid 1px #ffffff26;
  border-radius: .375rem;
  padding: 0.5rem 0;
  z-index: 2000;
  width: 300px;
}

.reka-link {
  padding: 0.25rem 1rem;
  color: #dee2e6;
  display: block;
  width: 100%;
  text-decoration: none;
}

.reka-link:hover,
.reka-link:focus {
  color: #dee2e6;
  background-color: #2b3035;
}


@keyframes enterFromRight {
  from {
    opacity: 0;
    transform: translateX(200px);
  }

  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes enterFromLeft {
  from {
    opacity: 0;
    transform: translateX(-200px);
  }

  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes exitToRight {
  from {
    opacity: 1;
    transform: translateX(0);
  }

  to {
    opacity: 0;
    transform: translateX(200px);
  }
}

@keyframes exitToLeft {
  from {
    opacity: 1;
    transform: translateX(0);
  }

  to {
    opacity: 0;
    transform: translateX(-200px);
  }
}

@keyframes scaleIn {
  from {
    opacity: 0;
    transform: rotateX(-30deg) scale(0.9);
  }

  to {
    opacity: 1;
    transform: rotateX(0deg) scale(1);
  }
}

@keyframes scaleOut {
  from {
    opacity: 1;
    transform: rotateX(0deg) scale(1);
  }

  to {
    opacity: 0;
    transform: rotateX(-10deg) scale(0.95);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }

  to {
    opacity: 0;
  }
}
</style>
