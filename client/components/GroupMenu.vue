<template>
  <NavigationMenuRoot
    :disable-hover-trigger="true"
    v-model="menuTriggerRef"
    class="NavigationMenuRoot"
  >
    <NavigationMenuList class="NavigationMenuList">
      <NavigationMenuItem value="Groups">
        <NavigationMenuTrigger
          class="dropdown-toggle NavigationMenuTrigger"
          ref="buttonTriggerRef"
        >
          Groups
        </NavigationMenuTrigger>
        <NavigationMenuContent class="NavigationMenuContent">
          <MenuItem
            v-for="(item, itemIndex) in groupsMenu"
            :key="itemIndex"
            :item="item"
            :depth="0"
          />
        </NavigationMenuContent>
      </NavigationMenuItem>
    </NavigationMenuList>
    <Teleport to="body">
      <div ref="viewportWrapperRef">
        <NavigationMenuViewport />
      </div>
    </Teleport>
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
import { onMounted, watch, watchEffect, ref, Teleport } from 'vue'
import { groupBy } from 'lodash-es'
import MenuItem from '../GroupMenu/MenuItem.vue'

const viewportWrapperRef = ref(null)
const buttonTriggerRef = ref(null)
const menuTriggerRef = ref(null)

watch([menuTriggerRef, viewportWrapperRef, buttonTriggerRef], ()=> {
  // We're Vue Teleporting the <NavigationMenuViewport /> to escape the `position: fixed`
  // navbar, because when a Bootstrap OR Reka menu renders in a `position: fixed` we
  // can't scroll to reveal more menu options. It seems menus aren't designed to work
  // inside a `position: fixed` navbar.
  //
  // The teleporting to <body> however requires some additional repositioning of the
  // NavigationMenuContent which is rendered by Reka into the NavigationMenuViewport.
  // Reka normally assumes that the viewport is adjacent to the trigger in the DOM but
  // due to the Vue Teleport it is not.
  //
  // So this code sets some CSS variables which can be used in positioning calc()ulations
  const extractElement = (refValue) => {
    if(refValue instanceof HTMLElement) {
      return refValue
    }
    if(refValue && typeof refValue === 'object' && '$el' in refValue && refValue.$el instanceof HTMLElement) {
      return refValue.$el
    }
    return null
  }

  const buttonTrigger = buttonTriggerRef.value
  const viewportWrapper = viewportWrapperRef.value
  if(!buttonTrigger || !viewportWrapper) {
    console.log("Couldn't find ref value (at least one of)", { buttonTrigger, viewportWrapper })
    return
  }
  const buttonTriggerElement = extractElement(buttonTrigger)
  const viewportWrapperElement = extractElement(viewportWrapper)
  if(!buttonTriggerElement || !viewportWrapperElement) {
    console.log("Couldn't find element (at least one of)", { buttonTriggerElement, viewportWrapperElement })
    return
  }
  const rect = buttonTriggerElement.getBoundingClientRect()
  viewportWrapperElement.style.setProperty('--trigger-button-top', `${rect.top + rect.height + window.scrollY}px`)
  viewportWrapperElement.style.setProperty('--trigger-button-left', `${rect.left + window.scrollX}px`)
})

const groupsMenu = ref(null)

const DROPDOWN_TOGGLE_SELECTOR = '.dropdown a.dropdown-toggle'

// The previous Bootstrap menu would download menu JSON
// and then attach to specific elements in the DOM that
// had this prefix in the 'class' attribute.
const GROUP_PARENT_PREFIX = 'group-parent-'

onMounted(async () => {
  const legacyGroupsLink = Array.from(
    document.querySelectorAll(DROPDOWN_TOGGLE_SELECTOR)
  ).filter(
    elm => elm.innerText.includes('Groups')
  ).reduce((acc, elm, index, arr) => {
    if(arr.length !== 1) {
      console.log("Details", arr)
      throw Error(`Unable to scrape unique 'Groups' dropdown link`)
    }
    return elm
  }, null)

  if (!legacyGroupsLink) {
    throw Error('Unable to find groups link')
  }

  const groupsContainer = legacyGroupsLink.parentElement
  const legacyGroupsMenu = legacyGroupsLink.nextElementSibling

  const walk = (list) => {
    const items = []
    if (!(list instanceof HTMLElement) || list.nodeName.toLowerCase() !== 'ul') {
      console.warn("Unable to scrape ", list)
      return []
    }

    const findUniqueChild = (elm, filterFn, throwOnError) => {
      const result = Array.from(elm.children)
        .filter(filterFn)
        .reduce((_acc, item, _index, arr) => {
          if(throwOnError && arr.length !== 1) {
            console.log("Details", elm, filterFn)
            throw Error(`Unable to find unique item (was arr.length=${arr.length}). See console for more`)
          }
          return item
        }, null)
      if(throwOnError && !result) {
        console.log("Details", elm, filterFn)
        throw Error(`Unable to find unique item. See console for more`)
      }
      return result
    }

    Array.from(list.children)
      .forEach(level0 => {
        if(!(level0 instanceof HTMLElement)) {
          console.warn("Unable to scape", level0)
          return
        }
        
        if (level0.classList.contains('dropdown-header')) {
          items.push({
            type: 'group',
            header: level0.innerText,
            children: [],
          })
        } else if (level0.matches(`li[class*=${GROUP_PARENT_PREFIX}]`)) {
          // these have children later prefilled from JSON
          const groupParentId = level0.getAttribute('class')
            .split(' ')
            .filter(classItem => classItem.includes(GROUP_PARENT_PREFIX))
            .reduce((_acc, classItem) => classItem.replace(GROUP_PARENT_PREFIX, ''), null)
          
          const groupParentLink = findUniqueChild(
            level0,
            (node) => node instanceof HTMLElement && node.classList.contains('dropdown-item'),
            true,
          )
          const href = groupParentLink.getAttribute('href')
          if (!href) {
            throw Error("Couldn't extract groupParentLink href")
          }
          const label = groupParentLink.innerText
          if (
            !label.trim() // ensure we don't get an empty string
          ) {
            throw Error("Couldn't extract groupParentLink label")
          }

          if (items.length === 0) {
            console.log("Details", items)
            throw Error("Expected preexisting items to add groupParent")
          }

          const lastItem = items[items.length - 1]

          lastItem.children.push({
            type: 'groupParent',
            groupParentId,
            href,
            label,
          })
        } else if(level0.nodeName.toLowerCase() === 'li'){
          const divider = findUniqueChild(
            level0,
            (node) => node instanceof HTMLElement && node.nodeName.toLowerCase() === 'hr',
            false,
          )

          if (divider) {
            items.push({
              type: 'divider',
            })
            return
          }

          const link = findUniqueChild(
            level0,
            (node) => node instanceof HTMLElement && node.nodeName.toLowerCase() === 'a',
            true,
          )
          
          // const dropdownMenu = findUniqueChild(
          //   level1,
          //   node => node instanceof HTMLElement && node.classList.contains('dropdown-menu'),
          //   false,
          // )

          let listItemChildren = []
          // if(dropdownMenu) {
          //   listItemChildren = []
            // Array.from(dropdownMenu.children)
            //   .filter(dropdownMenuChild => (
            //     dropdownMenuChild instanceof HTMLElement &&
            //     dropdownMenuChild.nodeName.toLowerCase() === 'li'
            //   ))
            //   .map(walk)
          //}

          const children = listItemChildren ?? []

          const href = link.getAttribute('href')
          if (!href) {
            throw Error("Couldn't extract link href")
          }
          const label = link.innerText
          if (
            !label.trim() // ensure we don't get an empty string
          ) {
            throw Error("Couldn't extract link label")
          }

          const lastItem = items[items.length - 1]

          if(lastItem.type === 'group') {
            lastItem.children.push({
              type: 'link',
              label,
              href,
              children,
            })
          } else {
            items.push({
              type: 'link',
              label,
              href,
              children,
            })
          }
        }
      })
    
    return items
  }

  const groupsMenuItems = Array.from(groupsContainer.children).flatMap(walk)
      
  const updateMenu = (groupMenuData) => {
    const groupedMenuDataToGroups = (groupedMenuData) => {
      return Object.entries(groupedMenuData)
        .sort(([keyA], [keyB]) => keyA.localeCompare(keyB))
        .map(([key, value]) => {
          return {
            type: 'group',
            header: key,
            children: value.map(groupMenuDataItem => ({
              type: "link",
              label: `${groupMenuDataItem.acronym} - ${groupMenuDataItem.name}`,
              href: groupMenuDataItem.url,
              children: undefined,
            })),
          }
        })
    }

    const hydrateGroupParent = (item) => {
      switch(item.type) {
        case 'group':
          return {
            ...item,
            children: item.children.map(hydrateGroupParent)
          }
        case 'groupParent':
          return {
            type: 'group',
            header: item.label,
            href: item.href,
            children: groupedMenuDataToGroups(groupBy(groupMenuData[item.groupParentId], 'type'))
          }
        default:
          return item
      }
    }

    const groupsMenuValue = groupsMenuItems.map(hydrateGroupParent)
    
    console.log({ groupsMenuValue })

    groupsMenu.value = groupsMenuValue

    // remove original 'Groups' menu
    legacyGroupsLink.parentNode.removeChild(legacyGroupsLink)
    legacyGroupsMenu.parentNode.removeChild(legacyGroupsMenu)

    console.log({ groupsContainer })
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
.NavigationMenuRoot {}

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
  z-index: 2000;
  width: var(--reka-navigation-menu-viewport-width, 300px);
  top: calc(var(--trigger-button-top, 0px) + var(--reka-navigation-menu-viewport-top, 0px));
  left: calc(var(--trigger-button-left, 0px) + var(--reka-navigation-menu-viewport-left, 0px));  
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
  text-align: left;
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
  text-align: left;
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
