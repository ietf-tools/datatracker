// Copyright The IETF Trust 2024-2025, All Rights Reserved
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('delete_recordings_form')
    const dialog = document.getElementById('delete_confirm_dialog')
    const dialog_link = document.getElementById('delete_confirm_link')
    const dialog_submit = document.getElementById('delete_confirm_submit')
    const dialog_cancel = document.getElementById('delete_confirm_cancel')

    dialog.style.maxWidth = '30vw'

    form.addEventListener('submit', (e) => {
        e.preventDefault()
        dialog_submit.value = e.submitter.value
        const recording_link = e.submitter.closest('tr').querySelector('a')
        dialog_link.setAttribute('href', recording_link.getAttribute('href'))
        dialog_link.textContent = recording_link.textContent
        dialog.showModal()
    })

    dialog_cancel.addEventListener('click', (e) => {
        e.preventDefault()
        dialog.close()
    })

    document.addEventListener('keydown', (e) => {
        if (dialog.open && e.key === 'Escape') {
            dialog.close()
        }
    })
})
