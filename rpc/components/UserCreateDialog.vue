<template>
  <HeadlessTransitionRoot as="template" :show="isShown">
    <HeadlessDialog as="div" class="relative z-50" @close="close">
      <HeadlessTransitionChild as="template" enter="ease-in-out duration-500" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in-out duration-500" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-gray-500 dark:bg-black bg-opacity-75 dark:bg-opacity-50 transition-opacity" />
      </HeadlessTransitionChild>
      <div class="fixed inset-0 overflow-hidden">
        <div class="absolute inset-0 overflow-hidden">
          <div class="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10 sm:pl-16">
            <HeadlessTransitionChild as="template" enter="transform transition ease-in-out duration-500 sm:duration-700" enter-from="translate-x-full" enter-to="translate-x-0" leave="transform transition ease-in-out duration-500 sm:duration-700" leave-from="translate-x-0" leave-to="translate-x-full">
              <HeadlessDialogPanel class="pointer-events-auto w-screen max-w-md">
                <form class="flex h-full flex-col divide-y divide-gray-200 bg-white dark:bg-neutral-800 shadow-xl">
                  <div class="h-0 flex-1 overflow-y-auto">
                    <div class="bg-violet-700 px-4 py-6 sm:px-6">
                      <div class="flex items-center justify-between">
                        <HeadlessDialogTitle class="text-base font-semibold leading-6 text-white">New Team Member</HeadlessDialogTitle>
                        <div class="ml-3 flex h-7 items-center">
                          <button type="button" class="relative rounded-md bg-violet-700 text-violet-200 hover:text-white focus:outline-none focus:ring-2 focus:ring-white" @click="close">
                            <span class="absolute -inset-2.5" />
                            <span class="sr-only">Close panel</span>
                            <Icon name="uil:times" class="h-6 w-6" aria-hidden="true" />
                          </button>
                        </div>
                      </div>
                      <div class="mt-1">
                        <p class="text-sm text-violet-300">Get started by filling in the information below to create a new team member.</p>
                      </div>
                    </div>
                    <div class="flex flex-1 flex-col justify-between">
                      <div class="divide-y divide-gray-200 px-4 sm:px-6">
                        <div class="space-y-6 pb-5 pt-6">
                          <div>
                            <label for="name" class="block text-sm font-medium leading-6 text-gray-900 dark:text-neutral-400">Name</label>
                            <div class="mt-2">
                              <input type="text" name="name" id="name" class="block w-full rounded-md border-0 py-1.5 bg-white dark:bg-neutral-900 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-neutral-600 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-violet-600 sm:text-sm sm:leading-6" />
                            </div>
                          </div>
                          <div>
                            <label for="email" class="block text-sm font-medium leading-6 text-gray-900 dark:text-neutral-400">Email</label>
                            <div class="mt-2">
                              <input type="text" name="email" id="email" class="block w-full rounded-md border-0 py-1.5 bg-white dark:bg-neutral-900 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-neutral-600 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-violet-600 sm:text-sm sm:leading-6" />
                            </div>
                          </div>
                          <div>
                            <label for="datatracker" class="block text-sm font-medium leading-6 text-gray-900 dark:text-neutral-400">Datatracker Login Email</label>
                            <div class="mt-2">
                              <input type="text" name="datatracker" id="datatracker" class="block w-full rounded-md border-0 py-1.5 bg-white dark:bg-neutral-900 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-neutral-600 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-violet-600 sm:text-sm sm:leading-6" />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="flex flex-shrink-0 justify-end px-4 py-4">
                    <button type="button" class="rounded-md bg-white dark:bg-neutral-600 px-3 py-2 text-sm font-semibold text-gray-900 dark:text-neutral-200 shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-neutral-500 hover:bg-gray-50 dark:hover:bg-neutral-700" @click="close">Cancel</button>
                    <button type="submit" class="ml-4 inline-flex justify-center rounded-md bg-violet-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-violet-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600">Save</button>
                  </div>
                </form>
              </HeadlessDialogPanel>
            </HeadlessTransitionChild>
          </div>
        </div>
      </div>
    </HeadlessDialog>
  </HeadlessTransitionRoot>
</template>

<script setup>
defineProps({
  isShown: {
    type: Boolean,
    default: false,
    required: true
  }
})

const emit = defineEmits(['update:isShown'])

function close () {
  emit('update:isShown')
}
</script>
