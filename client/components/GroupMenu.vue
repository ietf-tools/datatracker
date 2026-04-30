<template>
  <NavigationMenuRoot
    :disable-hover-trigger="true"
    v-model="menuTriggerRef"
  >
    <NavigationMenuList class="reka-root-list">
      <NavigationMenuItem value="Groups">
        <NavigationMenuTrigger
          class="reka-trigger"
          ref="buttonTriggerRef"
        >
          Groups
        </NavigationMenuTrigger>
        <NavigationMenuContent class="reka-root-content">
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
        <NavigationMenuViewport class="reka-viewport" />
      </div>
    </Teleport>
  </NavigationMenuRoot>
</template>

<script setup lang="js">
import {
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuList,
  NavigationMenuRoot,
  NavigationMenuTrigger,
  NavigationMenuViewport,
} from 'reka-ui'
import { onMounted, watch, ref, Teleport } from 'vue'
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
        .sort(([keyA], [keyB]) => keyB.localeCompare(keyA))
        .flatMap(([key, value], index) => {
          return [
            ...(index > 0 ? [
              {
                type: 'divider',
              }
            ] : []) ,
            {
              type: 'header',
              text: key,
            },
            ...value.map(groupMenuDataItem => ({
              type: "link",
              label: `${groupMenuDataItem.acronym} - ${groupMenuDataItem.name}`,
              href: groupMenuDataItem.url,
              children: undefined,
            }))
          ]
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

    /**
     * Reka expects submenus in a slightly different format, with submenus being in a contiguous list,
     * so we do some restructuring of the menu data to make it easier to render in Reka.
     */
    const convertMenuItemsToReka = (items) => {
      const grouped = items.reduce((acc, item, index, arr) => {
        if (item.type === 'group' && (index === 0 || arr[index - 1].type !== 'group')) {
          // new contiguous group
          
          const slice = arr.slice(index)
          console.log("New contiguous group?", slice)
          const afterEndIndex = slice.findIndex((item, i) => {
            console.log("-item ", i, item.type)
            return item.type !== 'group'
          })
          
          const contiguousGroupsChildren = slice
              .slice(0, afterEndIndex === -1 ? slice.length : afterEndIndex)
          
          console.log("= ", `(${afterEndIndex})`, slice, contiguousGroupsChildren.length, contiguousGroupsChildren)

          if(contiguousGroupsChildren.length === 1) {
            acc.push(
              {
                type: 'header',
                text: item.header,
              },
              ...convertMenuItemsToReka(item.children)
            )
          } else {
            const contiguousGroup = {
              type: 'submenuList',
              children: contiguousGroupsChildren.map(item => {
                if(item.type === 'group' && Array.isArray(item.children)) {
                  return {
                    type: 'menuItem',
                    label: item.header,
                    href: item.href,
                    children: convertMenuItemsToReka(item.children)
                  }
                }
                return item
              })
            }
            acc.push(contiguousGroup)
          }
        } else if(item.type === 'group') {
          // do nothing, it should have been added by a previous iteration
        } else {
          acc.push(item)
        }
        return acc
      }, [])

      return grouped
    }

    const hydratedGroupsMenuItems = groupsMenuItems.map(hydrateGroupParent)
    const groupsMenuValue = convertMenuItemsToReka(hydratedGroupsMenuItems)

    groupsMenu.value = groupsMenuValue

    console.log({ groupsMenuValue, hydratedGroupsMenuItems })

    // remove original 'Groups' menu
    legacyGroupsLink.parentNode.removeChild(legacyGroupsLink)
    legacyGroupsMenu.parentNode.removeChild(legacyGroupsMenu)
  }

  // Download JSON for menu
  const groupMenuDataUrl = document.body.dataset.groupMenuDataUrl
  const response = await fetch(groupMenuDataUrl)
  if (response.ok) {
    response.json().then(groupMenuData => updateMenu(groupMenuData))
  } else {
    console.error(`Problem downloading ${groupMenuDataUrl} ${response.status} ${response.statusText}`, response)
  }
})

</script>

<style>
.reka-root-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.reka-trigger {
  outline: none;
  user-select: none;
  border: 0;
  background-color: inherit;
  color: rgba(255, 255, 255, 0.65);
  padding: 0.5rem 0;
}

.reka-trigger::after {
  vertical-align: .255em;
  content: "";
  border: .3em solid #0000;
  border-top-color: currentColor;
  border-bottom: 0;
  margin-left: .255em;
  display: inline-block;
}

.reka-trigger[data-state=open] {
  color: #fff
}

.reka-root-content {
  position: absolute;
  animation-duration: 250ms;
  animation-timing-function: ease;
  background-color: #212529;
  border: solid 1px #ffffff26;
  border-radius: .375rem;
  padding: 0.5rem 0;
  z-index: 2000;
  width: 300px;
  top: calc(var(--trigger-button-top, 0px) + var(--reka-navigation-menu-viewport-top, 0px));
  left: calc(var(--trigger-button-left, 0px) + var(--reka-navigation-menu-viewport-left, 0px));  
}

.reka-root-content[data-motion='from-start'] {
  animation-name: enterFromLeft;
}

.reka-root-content[data-motion='from-end'] {
  animation-name: enterFromRight;
}

.reka-root-content[data-motion='to-start'] {
  animation-name: exitToLeft;
}

.reka-root-content[data-motion='to-end'] {
  animation-name: exitToRight;
}

.reka-viewport {
}

.reka-viewport[data-state='open'] {
  animation: scaleIn 200ms ease;
}

.reka-viewport[data-state='closed'] {
  animation: scaleOut 200ms ease;
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
