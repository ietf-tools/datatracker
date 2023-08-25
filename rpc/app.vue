<template>
  <div>
    <HeadlessTransitionRoot as="template" :show="sidebarOpen">
      <HeadlessDialog as="div" class="relative z-50 lg:hidden" @close="sidebarOpen = false">
        <HeadlessTransitionChild as="template" enter="transition-opacity ease-linear duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="transition-opacity ease-linear duration-300" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-gray-900/80" />
        </HeadlessTransitionChild>

        <div class="fixed inset-0 flex">
          <HeadlessTransitionChild as="template" enter="transition ease-in-out duration-300 transform" enter-from="-translate-x-full" enter-to="translate-x-0" leave="transition ease-in-out duration-300 transform" leave-from="translate-x-0" leave-to="-translate-x-full">
            <HeadlessDialogPanel class="relative mr-16 flex w-full max-w-xs flex-1">
              <HeadlessTransitionChild as="template" enter="ease-in-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in-out duration-300" leave-from="opacity-100" leave-to="opacity-0">
                <div class="absolute left-full top-0 flex w-16 justify-center pt-5">
                  <button type="button" class="-m-2.5 p-2.5" @click="sidebarOpen = false">
                    <span class="sr-only">Close sidebar</span>
                    <Icon name="uil:times" class="h-6 w-6 text-white" aria-hidden="true" />
                  </button>
                </div>
              </HeadlessTransitionChild>
              <div class="flex grow flex-col gap-y-5 overflow-y-auto bg-white px-6 pb-2">
                <div class="flex h-16 shrink-0 items-center">
                  <img class="h-8 w-auto" src="https://tailwindui.com/img/logos/mark.svg?color=violet&shade=600" alt="Your Company" />
                </div>
                <nav class="flex flex-1 flex-col">
                  <ul role="list" class="flex flex-1 flex-col gap-y-7">
                    <li>
                      <ul role="list" class="-mx-2 space-y-1">
                        <li v-for="item in navigation" :key="item.name">
                          <a :href="item.href" :class="[item.current ? 'bg-gray-50 text-violet-600' : 'text-gray-700 hover:text-violet-600 hover:bg-gray-50', 'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold']">
                            <component :is="item.icon" :class="[item.current ? 'text-violet-600' : 'text-gray-400 group-hover:text-violet-600', 'h-6 w-6 shrink-0']" aria-hidden="true" />
                            {{ item.name }}
                          </a>
                        </li>
                      </ul>
                    </li>
                    <li>
                      <div class="text-xs font-semibold leading-6 text-gray-400">Your teams</div>
                      <ul role="list" class="-mx-2 mt-2 space-y-1">
                        <li v-for="team in teams" :key="team.name">
                          <a :href="team.href" :class="[team.current ? 'bg-gray-50 text-violet-600' : 'text-gray-700 hover:text-violet-600 hover:bg-gray-50', 'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold']">
                            <span :class="[team.current ? 'text-violet-600 border-violet-600' : 'text-gray-400 border-gray-200 group-hover:border-violet-600 group-hover:text-violet-600', 'flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-[0.625rem] font-medium bg-white']">{{ team.initial }}</span>
                            <span class="truncate">{{ team.name }}</span>
                          </a>
                        </li>
                      </ul>
                    </li>
                  </ul>
                </nav>
              </div>
            </HeadlessDialogPanel>
          </HeadlessTransitionChild>
        </div>
      </HeadlessDialog>
    </HeadlessTransitionRoot>

    <!-- Static sidebar for desktop -->
    <div class="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-72 lg:flex-col">
      <!-- Sidebar component, swap this element with another sidebar if you like -->
      <div class="flex grow flex-col gap-y-5 overflow-y-auto border-r border-gray-200 dark:border-violet-600 bg-white dark:bg-violet-900 bg-gradient-to-tr from-violet-50 to-white dark:from-violet-950 dark:to-violet-900 px-6">
        <div class="flex h-16 shrink-0 items-center text-violet-500 dark:text-violet-300 font-light">
          <Icon name="uil:edit-alt" class="w-6 h-auto mr-2" aria-hidden="true" />
          RFC Production Center
        </div>
        <nav class="flex flex-1 flex-col">
          <ul role="list" class="flex flex-1 flex-col gap-y-7">
            <li>
              <ul role="list" class="-mx-2 space-y-1">
                <li v-for="item in navigation" :key="item.name">
                  <NuxtLink :to="item.href" :class="[item.href === currentBaseLink ? 'bg-violet-50 dark:bg-violet-600 text-violet-600 dark:text-white' : 'text-gray-700 dark:text-violet-300 hover:text-violet-600 hover:bg-violet-50 dark:hover:text-violet-100 dark:hover:bg-violet-800', 'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold']">
                    <component :is="item.icon" :class="[item.href === currentBaseLink ? 'text-violet-600 dark:text-white' : 'text-gray-400 dark:text-violet-400 group-hover:text-violet-600 dark:group-hover:text-violet-100', 'h-6 w-6 shrink-0']" aria-hidden="true" />
                    {{ item.name }}
                  </NuxtLink>
                </li>
              </ul>
            </li>
            <li>
              <div class="text-xs font-semibold leading-6 text-gray-400 dark:text-violet-400">Misc</div>
              <ul role="list" class="-mx-2 mt-2 space-y-1">
                <li v-for="team in teams" :key="team.name">
                  <a :href="team.href" :class="[team.current ? 'bg-gray-50 text-violet-600' : 'text-gray-700 dark:text-violet-300 hover:text-violet-600 hover:bg-gray-50', 'group flex gap-x-3 rounded-md p-2 text-sm leading-6 font-semibold']">
                    <span :class="[team.current ? 'text-violet-600 border-violet-600' : 'text-gray-400 dark:text-violet-400 border-gray-200 dark:border-violet-500 group-hover:border-violet-600 group-hover:text-violet-600', 'flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-[0.625rem] font-medium bg-white dark:bg-black/20']">{{ team.initial }}</span>
                    <span class="truncate">{{ team.name }}</span>
                  </a>
                </li>
              </ul>
            </li>
            <li class="-mx-6 mt-auto">
              <a href="https://datatracker.ietf.org" class="flex items-center gap-x-4 px-6 py-3 text-sm font-semibold leading-6 text-gray-500 dark:text-violet-400 hover:bg-violet-500/5">
                <Icon name="uil:arrow-left" class="h-8 w-8 text-gray-400 dark:text-violet-400" aria-hidden="true" />
                <span>Go to Datatracker</span>
              </a>
            </li>
          </ul>
        </nav>
      </div>
    </div>

    <main class="lg:pl-72">
      <div class="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-x-4 border-b border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-4 shadow-sm sm:gap-x-6 sm:px-6 lg:px-8">
        <button type="button" class="-m-2.5 p-2.5 text-gray-700 lg:hidden" @click="sidebarOpen = true">
          <span class="sr-only">Open sidebar</span>
          <Icon name="uil:bars" class="h-6 w-6" aria-hidden="true" />
        </button>

        <!-- Separator -->
        <div class="h-6 w-px bg-gray-900/10 lg:hidden" aria-hidden="true" />

        <div class="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
          <form class="relative flex flex-1" action="#" method="GET">
            <label for="search-field" class="sr-only">Search</label>
            <Icon name="uil:search" class="pointer-events-none absolute inset-y-0 left-0 h-full w-5 text-gray-400" aria-hidden="true" />
            <input id="search-field" class="block h-full w-full border-0 py-0 pl-8 pr-0 bg-white dark:bg-neutral-900 text-gray-900 dark:text-neutral-200 placeholder:text-gray-400 dark:placeholder:text-neutral-400 focus:ring-0 sm:text-sm" placeholder="Search..." type="search" name="search" />
          </form>
          <div class="flex items-center gap-x-4 lg:gap-x-6">
            <!-- Site Theme Switcher -->
            <HeadlessMenu as="div" class="relative inline-block mr-4">
              <HeadlessMenuButton class="rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500">
                <span class="sr-only">Site Theme</span>
                <ColorScheme placeholder="..." tag="span">
                  <Icon v-if="$colorMode.value === 'dark'" name="uil:moon" class="text-gray-500 dark:text-neutral-400 hover:text-violet-400 dark:hover:text-violet-400" size="1.25em" aria-hidden="true" />
                  <Icon v-else name="uil:sun" class="text-gray-500 dark:text-white hover:text-violet-400 dark:hover:text-violet-400" size="1.25em" aria-hidden="true" />
                </ColorScheme>
              </HeadlessMenuButton>

              <transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
                <HeadlessMenuItems class="absolute right-0 z-10 mt-2 w-40 origin-top-right rounded-md bg-white dark:bg-neutral-800/90 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                  <div class="py-1">
                    <HeadlessMenuItem v-slot="{ active }">
                      <a @click="$colorMode.preference = 'dark'" :class="[active ? 'text-violet-500 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/5' : 'text-gray-700 dark:text-gray-100', 'flex items-center px-4 py-2 text-sm cursor-pointer']">
                        <Icon name="uil:moon" class="mr-3" />
                        Dark
                      </a>
                    </HeadlessMenuItem>
                    <HeadlessMenuItem v-slot="{ active }">
                      <a @click="$colorMode.preference = 'light'" :class="[active ? 'text-violet-500 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/5' : 'text-gray-700 dark:text-gray-100', 'flex items-center px-4 py-2 text-sm cursor-pointer']">
                        <Icon name="uil:sun" class="mr-3" />
                        Light
                      </a>
                    </HeadlessMenuItem>
                    <HeadlessMenuItem v-slot="{ active }">
                      <a @click="$colorMode.preference = 'system'" :class="[active ? 'text-violet-500 dark:text-violet-300 bg-violet-50 dark:bg-violet-500/5' : 'text-gray-700 dark:text-gray-100', 'flex items-center px-4 py-2 text-sm cursor-pointer']">
                        <Icon name="uil:desktop" class="mr-3" />
                        System
                      </a>
                    </HeadlessMenuItem>
                  </div>
                </HeadlessMenuItems>
              </transition>
            </HeadlessMenu>

            <!-- View Notifications -->
            <button type="button" class="-m-2.5 mr-2 text-gray-400 dark:text-neutral-400 hover:text-gray-500 dark:hover:text-violet-400">
              <span class="sr-only">View notifications</span>
              <Icon name="ci:bell" size="1.25em" aria-hidden="true" />
            </button>

            <!-- Separator -->
            <div class="hidden lg:block lg:h-6 lg:w-px lg:bg-gray-900/10 dark:lg:bg-white/20" aria-hidden="true" />

            <!-- Profile dropdown -->
            <HeadlessMenu as="div" class="relative">
              <HeadlessMenuButton class="-m-1.5 flex items-center p-1.5">
                <span class="sr-only">Open user menu</span>
                <img class="h-8 w-8 rounded-full bg-gray-50" src="https://i.pravatar.cc/150?img=5" alt="" />
                <span class="hidden lg:flex lg:items-center">
                  <span class="ml-4 text-sm font-semibold leading-6 text-gray-900 dark:text-neutral-300" aria-hidden="true">Jean Mahoney</span>
                  <Icon name="uil:angle-down" class="ml-2 h-5 w-5 text-gray-400 dark:text-neutral-400" aria-hidden="true" />
                </span>
              </HeadlessMenuButton>
              <transition enter-active-class="transition ease-out duration-100" enter-from-class="transform opacity-0 scale-95" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-75" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-95">
                <HeadlessMenuItems class="absolute right-0 z-10 mt-2.5 w-32 origin-top-right rounded-md bg-white py-2 shadow-lg ring-1 ring-gray-900/5 focus:outline-none">
                  <HeadlessMenuItem v-for="item in userNavigation" :key="item.name" v-slot="{ active }">
                    <a :href="item.href" :class="[active ? 'bg-gray-50' : '', 'block px-3 py-1 text-sm leading-6 text-gray-900']">{{ item.name }}</a>
                  </HeadlessMenuItem>
                </HeadlessMenuItems>
              </transition>
            </HeadlessMenu>
          </div>
        </div>
      </div>
      <div class="px-4 py-10 sm:px-6 lg:px-8 lg:py-6">
        <NuxtLayout>
          <NuxtPage />
        </NuxtLayout>
      </div>
    </main>
  </div>
</template>

<script setup>
import { Icon } from '#components'

const colorMode = useColorMode()

colorMode.preference = 'light'

useHead({
  link: [
    { rel: 'preconnect', href: 'https://rsms.me' },
    { rel: 'stylesheet', href: 'https://rsms.me/inter/inter.css' }
  ],
  bodyAttrs: {
    class: 'h-full'
  },
  htmlAttrs: {
    class: 'h-full'
  }
})

const navigation = [
  { name: 'Dashboard', href: '/', icon: h(Icon, { name: 'uil:dashboard' }), current: true },
  { name: 'Queue', href: '/queue', icon: h(Icon, { name: 'uil:list-ui-alt' }), current: false },
  { name: 'Documents', href: '/docs', icon: h(Icon, { name: 'uil:file-copy-alt' }), current: false },
  { name: 'Team', href: '/team', icon: h(Icon, { name: 'uil:users-alt' }), current: false },
  { name: 'Statistics', href: '/stats', icon: h(Icon, { name: 'uil:graph-bar' }), current: false },
  { name: 'Final Reviews', href: '/auth48', icon: h(Icon, { name: 'uil:cell' }), current: false },
]

const teams = [
  { id: 1, name: 'Manage RFC Numbers', href: '#', initial: '#', current: false },
  { id: 2, name: 'Cluster Management', href: '#', initial: 'C', current: false },
  { id: 3, name: 'Legal Requests', href: '#', initial: 'L', current: false },
]

const userNavigation = [
  { name: 'Your profile', href: '#' },
  { name: 'Sign out', href: '#' },
]

const route = useRoute()
const currentBaseLink = computed(() => route.path.indexOf('/', 1) > 0 ? `/` + route.path.split('/')[1] : route.path)

const sidebarOpen = ref(false)
</script>

<style lang="scss">
:root { font-family: 'Inter', sans-serif; }
@supports (font-variation-settings: normal) {
  :root { font-family: 'Inter var', sans-serif; }
}

body {
  background-color: #f9fafb;
}
.dark body {
  background-color: #0a0a0a;
}
</style>
