<template>
  <div class="relative isolate overflow-hidden">
    <!-- Secondary navigation -->
    <header class="pb-4 pt-6 sm:pb-6">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center gap-6 px-4 sm:flex-nowrap sm:px-6 lg:px-8">
        <h1 class="text-base font-semibold leading-7 text-gray-900 dark:text-neutral-400">Queue</h1>
        <div class="order-last flex w-full gap-x-8 text-sm font-semibold leading-6 sm:order-none sm:w-auto sm:border-l sm:border-gray-200 dark:sm:border-neutral-600 sm:pl-6 sm:leading-7">
          <a v-for="item in secondaryNavigation" :key="item.name" :href="item.href" :class="item.current ? 'text-violet-600 dark:text-violet-500' : 'text-gray-700 dark:text-neutral-500'">{{ item.name }}</a>
        </div>
        <a href="#" class="ml-auto flex items-center gap-x-1 rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          <Icon name="uil:plus" class="-ml-1.5 h-5 w-5" aria-hidden="true" />
          Add Document
        </a>
      </div>
    </header>

    <!-- Stats -->
    <div class="border-b border-b-gray-900/10 dark:border-b-neutral-50/20 lg:border-t lg:border-t-gray-900/5 dark:lg:border-t-neutral-50/10">
      <dl class="mx-auto grid max-w-7xl grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 lg:px-2 xl:px-0">
        <div v-for="(stat, statIdx) in stats" :key="stat.name" :class="[statIdx % 2 === 1 ? 'sm:border-l' : statIdx === 2 ? 'lg:border-l' : '', 'flex items-baseline flex-wrap justify-between gap-y-2 gap-x-4 border-t border-gray-900/5 dark:border-neutral-50/10 px-4 py-10 sm:px-6 lg:border-t-0 xl:px-8']">
          <dt class="text-sm font-medium leading-6 text-gray-500 dark:text-neutral-400">{{ stat.name }}</dt>
          <dd :class="[stat.changeType === 'negative' ? 'text-rose-600' : 'text-gray-700 dark:text-neutral-400', 'text-xs font-medium']">{{ stat.change }}</dd>
          <dd class="w-full flex-none text-3xl font-medium leading-10 tracking-tight text-gray-900 dark:text-neutral-300">{{ stat.value }}</dd>
        </div>
      </dl>
    </div>

    <div class="absolute left-0 top-full -z-10 mt-96 origin-top-left translate-y-40 -rotate-90 transform-gpu opacity-20 blur-3xl sm:left-1/2 sm:-ml-96 sm:-mt-10 sm:translate-y-0 sm:rotate-0 sm:transform-gpu sm:opacity-50" aria-hidden="true">
      <div class="aspect-[1154/678] w-[72.125rem] bg-gradient-to-br from-[#FF80B5] to-[#9089FC]" style="clip-path: polygon(100% 38.5%, 82.6% 100%, 60.2% 37.7%, 52.4% 32.1%, 47.5% 41.8%, 45.2% 65.6%, 27.5% 23.4%, 0.1% 35.3%, 17.9% 0%, 27.7% 23.4%, 76.2% 2.5%, 74.2% 56%, 100% 38.5%)" />
    </div>
  </div>
</template>

<script setup>
const secondaryNavigation = [
  { name: 'All-time', href: '#', current: true },
  { name: 'Last 30 days', href: '#', current: false },
  { name: 'Last 90 days', href: '#', current: false },
]

const stats = [
  { name: 'Submissions', value: '17', change: '+4.75%', changeType: 'positive' },
  { name: 'Pending assignment', value: '10', change: '+54.02%', changeType: 'negative' },
  { name: 'Exceptions', value: '3', change: '-1.39%', changeType: 'negative' },
  { name: 'In Process', value: '23', change: '+10.18%', changeType: 'negative' },
]
</script>
