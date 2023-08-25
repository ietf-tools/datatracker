<template>
  <div>
    <div class="sm:flex sm:items-center">
      <div class="sm:flex-auto">
        <h1 class="text-base font-semibold leading-6 text-gray-900 dark:text-neutral-200">
          Manage Team Members
        </h1>
        <p class="mt-2 text-sm text-gray-700 dark:text-neutral-400">
          A list of all the users having access to this tool.
        </p>
      </div>
      <div class="mt-4 sm:ml-16 sm:mt-0 sm:flex-none">
        <button type="button" @click="createDialogShown = true" class="flex items-center rounded-md bg-violet-600 px-3 py-2 text-center text-sm font-semibold text-white shadow-sm hover:bg-violet-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600">
          <Icon name="uil:plus" class="-ml-1 h-5 w-5 mr-2" aria-hidden="true" />
          Add user
        </button>
      </div>
    </div>
    <div class="mt-8 flow-root">
      <div class="-mx-4 -my-2 overflow-x-auto sm:-mx-6 lg:-mx-8">
        <div class="inline-block min-w-full py-2 align-middle sm:px-6 lg:px-8">
          <div class="overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
            <table class="min-w-full divide-y divide-gray-300 dark:divide-neutral-600">
              <thead class="bg-gray-50 dark:bg-neutral-800">
                <tr>
                  <th scope="col" class="py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 dark:text-neutral-400 sm:pl-6">Name</th>
                  <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900 dark:text-neutral-400">Roles</th>
                  <th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900 dark:text-neutral-400">Expertise</th>
                  <th scope="col" class="relative py-3.5 pl-3 pr-4 sm:pr-6">
                    <span class="sr-only">Edit</span>
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-200 dark:divide-neutral-700 bg-white dark:bg-neutral-900">
                <tr v-for="person in people" :key="person.email">
                  <td class="whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 dark:text-neutral-100 sm:pl-6">{{ person.name }}</td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500 dark:text-neutral-400">{{ person.roles }}</td>
                  <td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500 dark:text-neutral-400">{{ person.expertise }}</td>
                  <td class="relative whitespace-nowrap py-4 pl-3 pr-4 text-right text-sm font-medium sm:pr-6">
                    <a href="#" class="text-violet-600 hover:text-indigo-900 dark:text-violet-400 dark:hover:text-violet-200">Edit<span class="sr-only">, {{ person.name }}</span></a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <UserCreateDialog v-model:isShown="createDialogShown" />
  </div>
</template>

<script setup>
const people = [
  { name: 'Alice Russo', roles: 'Format, PE, FinRev, mgr', expertise: 'Code Components, Cluster, IANA' },
  { name: 'Jean Mahoney', roles: 'Format, PE, RE, FinRev, PUB', expertise: 'Code Components, Cluster, Formatting, IANA' },
  { name: 'Sandy Ginoza', roles: 'Format, PE, FinRev', expertise: 'Formatting, IANA' },
]

const createDialogShown = ref(false)
</script>
