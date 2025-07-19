<template>
  <NavigationMenuRoot
    v-if="menuData"
    :disable-hover-trigger="true"
    class="NavigationMenuRoot"
  >
    <NavigationMenuList class="NavigationMenuList">
      <NavigationMenuItem value="Groups">
        <NavigationMenuTrigger class="dropdown-toggle NavigationMenuTrigger">
          Groups
        </NavigationMenuTrigger>
        <NavigationMenuContent class="NavigationMenuContent">
          <NavigationMenuSub default-value="0">
            <NavigationMenuList class="NavigationMenu-NoList">
              <NavigationMenuItem
                v-for="(menuItem, menuItemIndex) in menuData"
                :key="menuItemIndex"
                :val="menuItemIndex"
              >
                <NavigationMenuTrigger class="NavigationMenuLevel1">
                  {{ menuItem.label }}
                </NavigationMenuTrigger>
                <NavigationMenuContent>
                  <fieldset
                    v-for="(childrenItems, groupType, childrenIndex) in menuItem.children"
                    :key="childrenIndex"
                  >
                    <legend class="NavigationMenuLegend">
                      {{ groupType }}
                    </legend>
                    <ul class="NavigationMenu-NoList">
                      <li
                        v-for="(childrenItem, childrenItemIndex) in childrenItems"
                        :key="childrenItemIndex"
                      >
                        <NavigationMenuLink as-child>
                          <a :href="childrenItem.url" class="NavigationMenuLevel2">
                            {{ childrenItem.acronym }}
                            &mdash;
                            {{ childrenItem.name }}
                          </a>
                        </NavigationMenuLink>
                      </li>
                    </ul>
                  </fieldset>
                </NavigationMenuContent>
              </NavigationMenuItem>
            </NavigationMenuList>
          </NavigationMenuSub>
        </NavigationMenuContent>
      </NavigationMenuItem>
    </NavigationMenuList>
  </NavigationMenuRoot>
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
import { onMounted, ref } from 'vue'
import { groupBy } from 'lodash-es'


// type GroupMenuData = Record<string, {
//   "acronym": string
//   "name": string
//   "type": string
//   "url": string
// }[]>

// type MenuItem = {
//   label: string
//   href: string
//   parentId: string
//   children: GroupMenuData[string]
// }

const menuData = ref(null)

onMounted(async () => {
  // The previous Bootstrap menu would download menu JSON
  // and then attach to specific elements in the DOM that
  // had this prefix in the 'class' attribute.
  const GROUP_MENU_PREFIX = 'group-parent-'
  // so we'll scrape those in order to build data for a
  // Reka menu
  const groupsLink = document.querySelector('[data-groups]')
  const groupsList = groupsLink.nextElementSibling
  const groupParents = groupsList.querySelectorAll(`li[class*=${GROUP_MENU_PREFIX}]`)
  const menu = Array.from(groupParents).map(element => {
    const parentId = element.getAttribute('class')
      .split(' ')
      .filter(classItem => classItem.includes(GROUP_MENU_PREFIX))
      .reduce((_acc, classItem) => classItem.replace(GROUP_MENU_PREFIX, ''), null)

    const href = element.querySelector('a[href]').getAttribute('href')

    return {
      label: element.innerText,
      href,
      parentId,
    }
  })

  const updateMenu = (groupMenuData) => {
    menuData.value = menu.map(menuItem => ({
      ...menuItem,
      children: groupBy(groupMenuData[menuItem.parentId], 'type')
    }))
    console.log({ menuDataValue: menuData.value })

    // remove original 'Groups' menu
    groupsLink.parentNode.removeChild(groupsLink)
    groupsList.parentNode.removeChild(groupsList)
  }

  // Download JSON for menu
  const groupMenuDataUrl = document.body.dataset.groupMenuDataUrl
  const response = await fetch(groupMenuDataUrl)
  if (response.ok) {
    response.json().then((groupMenuData) => {
      updateMenu(groupMenuData)
    })
  } else {
    console.error(`Problem downloading ${groupMenuDataUrl} ${response.status} ${response.statusText}`, response)
  }
})

</script>

<style>
.NavigationMenuRoot {
}

.NavigationMenuList {
  list-style: none;
  margin: 0;
  padding: 0;
}

.NavigationMenuTrigger {
  outline: none;
  user-select: none;
  line-height: 1;
  border: 0;
  background-color: inherit;
  color: var(--bs-nav-link-color);
  padding: var(--bs-nav-link-padding-y) var(--bs-nav-link-padding-x);
}

.NavigationMenuLink {
  padding: 8px 12px;
  outline: none;
  user-select: none;
  font-weight: 500;
  line-height: 1;
  border: 0;
  display: block;
  text-decoration: none;
  line-height: 1;
}

.NavigationMenuContent {
  position: absolute;
  animation-duration: 250ms;
  animation-timing-function: ease;
  background-color: #212529;
  border: solid 1px #ffffff26;
  border-radius: .375rem;
  padding: 0.5rem 0;
  min-width: 300px;
}

.NavigationMenuContent[data-motion='from-start'] {
  animation-name: enterFromLeft;
}
.NavigationMenuContent[data-motion='from-end'] {
  animation-name: enterFromRight;
}
.NavigationMenuContent[data-motion='to-start'] {
  animation-name: exitToLeft;
}
.NavigationMenuContent[data-motion='to-end'] {
  animation-name: exitToRight;
}

.NavigationMenu-NoList {
  list-style: none;
  margin: 0;
  padding: 0;
}

.NavigationMenuLevel1 {
  border: 0;
  width: 100%;
  padding: 0.25rem 1rem;
  clear: both;
  color: #dee2e6;
  text-align:left;
  background: transparent;
}

.NavigationMenuLevel1:hover,
.NavigationMenuLevel1:focus {
  background: #2b3035;
}

.NavigationMenuLevel2 {
  border: 0;
  width: 100%;
  padding: 0.25rem 1rem;
  margin-left: 1rem;
  clear: both;
  color: #dee2e6;
  text-align:left;
  background: transparent;
}

.NavigationMenuLevel2:hover,
.NavigationMenuLevel2:focus {
  background: #2b3035;
}


.NavigationMenuLegend {
  margin-left: 1rem;
  opacity: 0.8;
  font-size: inherit;
}

.NavigationMenuViewport {
  position: fixed;
  transform-origin: top center;
  margin-top: 10px;
  width: 100%;
  background-color: white;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: hsl(206 22% 7% / 35%) 0px 10px 38px -10px, hsl(206 22% 7% / 20%) 0px 10px 20px -15px;
  height: var(--reka-navigation-menu-viewport-height);
  transition: width, height, 300ms ease;
}
.NavigationMenuViewport[data-state='open'] {
  animation: scaleIn 200ms ease;
}
.NavigationMenuViewport[data-state='closed'] {
  animation: scaleOut 200ms ease;
}
@media only screen and (min-width: 600px) {
  .NavigationMenuViewport {
    width: var(--reka-navigation-menu-viewport-width);
  }
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
