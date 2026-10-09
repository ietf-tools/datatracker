
<template>
  <DataTable
    caption="Individual addresses"
    :columns="{
      primary: 'Primary',
      active: 'Active',
      address: 'Address',
      urlize_origin_html: 'Origin',
      delete: 'Delete'
    }"
    :column-classes="{
      primary: 'emails-form-column',
      active: 'emails-form-column',
    }"
    :rows="emails"
    :sortable-columns="['primary', 'active', 'address']"
    :sort="{
      address: (addressA, addressB) => addressA.localeCompare(addressB)
    }"
    :cell-formatters="{
      primary: (val) => h('input', { type: 'radio', name: 'primary', checked: val, name: 'primary_email' }),
      active: (val) => h('input', { type: 'checkbox', name: 'primary', checked: val, name: 'active_emails' }),
      address: (val) => h('a', { href: `mailto:${val}` }, val),
      urlize_origin_html: (val) => h('span', { innerHTML: val }),
      delete: (_, row) => h('button', { type: 'button', 'onClick': () => { selectedEmailForDeletionModal = row.pk }, 'aria-label': `Open modal to confirm deletion of ${row.address}`, class: 'emails_email_delete' }, '&times;')
    }"
    table-class="w-100"
  />

  <div class="emails-add-form-container">
    <div class="emails-add-form">
      <label
        for="add_email_input"
        class="form-label add-email-label"
      >
        New email:
      </label>
      <input
        :class="['form-control', {
          'is-invalid': addEmailValue.length > 0 && !isEmailValid,
          'is-valid': addEmailValue.length > 0 && isEmailValid
        }]"
        id="add_email_input"
        name="new_email"
        type="email"
        :aria-describedby="['new_email_describedby', addEmailValueValidation].join(' ')"
        ref="emailInputElement"
        @change="validateEmail"
        v-model="addEmailValue"
      >
      <button
        type="button"
        class="btn btn-primary"
      >
        Add
      </button>
    </div>
    <p
      id="add_email_validation"
      v-if="addEmailValue.length > 0 && !isEmailValid"
    >
      Email is invalid
    </p>
    <p
      id="add_email_describedby"
      class="form-text"
    >
      Remember to submit the form for the new email challenge to be sent.
      To add an address that cannot be confirmed this way, contact the secretariat.
    </p>
  </div>

  <NModal v-model:show="selectedEmailForDeletionModal">
    <NCard
      style="width: 100%; max-width: 600px"
      title="Confirm email deletion"
      :bordered="false"
      size="huge"
      role="dialog"
      aria-modal="true"
    >
      <div>
        Do you really want to delete email <span class="font-monospace">{{ selectedEmailRow?.address }}</span>?
      </div>
      <template #header-extra>
        <button
          type="button"
          aria-label="Close modal"
          @click="selectedEmailForDeletionModal = false"
          class="emails_email_delete text-black"
        >
          &times;
        </button>
      </template>
      <template #footer>
        <div class="modal-footer">
          <button
            type="button"
            class="btn btn-primary"
          >
            Confirm delete
          </button>
        </div>
      </template>
    </NCard>
  </NModal>
</template>

<script setup>
import { h, ref, watch } from 'vue'
import { NModal, NCard } from 'naive-ui'
import DataTable from './DataTable.vue'

const DOM_ID = 'emails'
let emails = []
const emailsScript = document.getElementById(DOM_ID)
if (emailsScript) {
  emails = JSON.parse(emailsScript.innerHTML)
} else {
  console.error(`Developer: emails.vue requires a <script id="${DOM_ID}" type="application/json"> but couldn't find it.`)
}

const addEmailValue = ref("")
const isEmailValid = ref(false)
// undefined or a row pk (string)
const selectedEmailForDeletionModal = ref(undefined)
const selectedEmailRow = ref()
watch(
  selectedEmailForDeletionModal,
  () => {
    const selectedEmail = emails.find(email => email.pk === selectedEmailForDeletionModal.value)
    console.log("what", selectedEmail)
    selectedEmailRow.value = selectedEmail
  }
)

const emailInputElement = ref(null)

function validateEmail(){
  const isValid = emailInputElement.value?.checkValidity()
  console.log({ isValid })
  isEmailValid.value = addEmailValue.value.length === 0 ? true : isValid
}

</script>

<style>

.emails-form-column {
  text-align: center;
}

.modal-footer {
  text-align: right;
}

.emails-add-form-container {
  margin: 1rem 0 2rem 0;
  width: 100%;
  max-width: 600px;
}

.emails-add-form {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  justify-content: center;
}


.emails_email_delete {
  border: 1px solid var(--bs-secondary-bg);
  background-color: inherit;
  border-radius: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;  
}

.add-email-label {
  white-space: nowrap;
}

.emails_email_delete:focus,
.emails_email_delete:hover {
  border-color: var(--bs-highlight-color);
}

.text-black {
  color: black;
}

</style>
