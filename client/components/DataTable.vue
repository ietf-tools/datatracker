<template>
  <table :class="['datatable', tableClass]">
    <caption
      v-if="caption"
      class="datatable_caption"
    >
      <Renderable :val="caption" />
    </caption>
    <thead class="datatable_thead">
      <tr class="datatable_tr">
        <th
          v-for="columnKey in columnKeys"
          :key="columnKey"
          :aria-sort="
            state.sortColumn === columnKey
              ? state.sortDirection === 'asc'
                ? 'ascending'
                : 'descending'
              : undefined
          "
          :class="['datatable_th', columnClasses?.[columnKey]]"
          scope="col"
        >
          <template v-if="sortableColumns?.includes(columnKey)">
            <button
              type="button"
              @click="sortBy(columnKey)"
              :class="[
                'datatable_sortButton',
                {
                  datatable_sortButtonUnsorted: state.sortColumn !== columnKey,
                  datatable_sortButtonAsc:
                    state.sortColumn === columnKey &&
                    state.sortDirection === 'asc',
                  datatable_sortButtonDesc:
                    state.sortColumn === columnKey &&
                    state.sortDirection === 'desc'
                }
              ]"
              :aria-pressed="state.sortColumn === columnKey"
            >
              <Renderable :val="columns[columnKey]" />
              <span class="datatable_sortIcon">
                <template v-if="state.sortColumn === columnKey">
                  <template v-if="state.sortDirection === 'asc'">
                    <Renderable :val="sortAscIcon" />
                  </template>
                  <template v-else-if="state.sortDirection === 'desc'">
                    <Renderable :val="sortDescIcon" />
                  </template>
                </template>
                <template v-else>
                  <Renderable :val="unsortedIcon" />
                </template>
              </span>
            </button>
          </template>
          <template v-else>
            <Renderable :val="columns[columnKey]" />
          </template>
        </th>
      </tr>
    </thead>
    <tbody class="datatable_tbody">
      <tr
        v-for="(row, index) in sortedRows"
        :key="index"
        class="datatable_tr"
      >
        <td
          v-for="(columnKey, columnKeyIndex) in columnKeys"
          :key="columnKey"
          :class="['datatable_td', columnClasses?.[columnKey]]"
        >
          <component
            :is="columnKeyIndex === 0 && rowLink ? rowLink(row) : VFragment"
          >
            <template v-if="cellFormatters?.[columnKey]">
              <Renderable
                :val="cellFormatters[columnKey](row[columnKey], row)"
              />
            </template>
            <template v-else>
              <Renderable :val="row[columnKey]" />
            </template>
          </component>
        </td>
      </tr>
    </tbody>
    <tfoot v-if="$slots.tfoot">
      <slot
        name="tfoot"
        :column-count="Object.keys(props.columns).length"
      />
    </tfoot>
  </table>
</template>
<script setup>
import { reactive, computed } from 'vue'
import { orderBy } from 'lodash-es'
import VFragment from './VFragment.vue'
import Renderable from './Renderable.vue'
const props = defineProps({
  /**
   * Definitions of columns and their labels
   **/
  columns: {
    type: Object,
    required: true
  },
  /**
   * The data of the table.
   * 
   * An array of objects where each object has keys of the `columns` prop.
   **/
  rows: {
    type: Array,
    required: true
  },
  /**
   * Formatters per cell in a row.
   * 
   * An object of keys from the `columns` prop where the value returns a formatted
   * value as a string or `h()`.
   */
  cellFormatters: {
    type: Object,
    required: false,
    default: undefined
  },
  /**
   * Per column (<th> and <td>) classes
   */
  columnClasses: {
    type: Object,
    required: false,
    default: undefined
  },
  /**
   * An optional wrapper link per row around the first cell.
   *
   * Devs should return a conventional link or an SPA link for the row.
   *
   * The link can be made to cover the whole row through CSS. Set `trClass` to a
   * class resolving to `position: relative` (tailwind: `relative`) and return a link
   * with a class resolving to `position: absolute; inset: 0` (tailwind: `absolute inset-0`)
   *
   * Troubleshooting: don't include 'children' in your returned link (3rd arg in `h()`)
   *
   * Usage:
   * ```
   * :rowLink="(row) => h('a', { href: `/{row.something}/info` })"
   * ```
   */
  rowLink: {
    type: Function,
    required: false,
    default: undefined
  },
  /**
   * A list of columns which can be sorted clientside.
   **/
  sortableColumns: {
    type: Array,
    required: false,
    default: undefined
  },
  /**
   * Specifies the title of the table
   * https://developer.mozilla.org/en-US/docs/Web/HTML/Element/caption
   **/
  caption: {
    type: String,
    required: false,
    default: undefined
  },
  /**
   * Custom sorting of rows by functions per column
   **/
  sort: {
    type: Object,
    required: false,
    default: undefined
  },
  tableClass: {
    type: String,
    required: false,
    default: undefined
  },
  sortAscIcon: {
    type: String,
    required: false,
    default: '\u2193'
  },
  sortDescIcon: {
    type: String,
    required: false,
    default: '\u2191'
  },
  unsortedIcon: {
    type: String,
    required: false,
    default: '\u21C5'
  },
})
const columnKeys = Object.keys(props.columns)
const state = reactive({
  sortColumn: undefined,
  sortDirection: 'asc'
})
function sortBy(columnKey) {
  state.sortColumn = columnKey
  if (state.sortColumn === columnKey) {
    state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc'
  } else {
    state.sortDirection = 'asc'
  }
}
const sortedRows = computed(() => {
  if (state.sortColumn) {
    const columnSort = props.sort?.[state.sortColumn]
    if (columnSort) {
      return props.rows.toSorted((rowA, rowB) => {
        const cellA = rowA[state.sortColumn]
        const cellB = rowB[state.sortColumn]
        const sortNumber = columnSort(cellA, cellB, rowA, rowB)
        return state.sortDirection === 'asc' ? sortNumber : -1 * sortNumber
      })
    }
    return orderBy(props.rows, [state.sortColumn], [state.sortDirection])
  } else {
    return props.rows
  }
})
</script>
<style>
.datatable {
  caption-side: top;
  border: solid 1px var(--bs-secondary-bg);
}
.datatable_caption {
  font-weight: bold;
  text-align: left;
}
.datatable_tr {}
.datatable_tbody .datatable_tr:nth-child(odd) {
  background-color: var(--bs-secondary-bg);
}
.datatable_thead {}
.datatable_th {
  font-weight: bold;
  padding: 0.4rem 0.5rem;
}
.datatable_tbody {}
.datatable_td {
  padding: 0.4rem 0.5rem;
}
.datatable_sortButton {
  border: 0;
  background-color: inherit;
  display: block;
  font-weight: inherit;
  padding: 0;
  margin: 0;
}
.datatable_sortIcon {
  display: inline-block;
  width: 1.8rem;
}
.datatable_sortButtonUnsorted {
  cursor: ns-resize;
}
.datatable_sortButtonAsc {
  cursor: n-resize;
 }
.datatable_sortButtonDesc {
  cursor: s-resize;
}
</style>
