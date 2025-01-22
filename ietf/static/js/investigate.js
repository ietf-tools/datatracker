// Copyright The IETF Trust 2025, All Rights Reserved
document.addEventListener('DOMContentLoaded', () => {
    const investigateForm = document.forms['investigate']
    investigateForm.addEventListener('submit', (event) => {
        // Intercept submission unless we've filled in the task_id field
        if (!investigateForm.elements['id_task_id'].value) {
            event.preventDefault()
            runInvestigation()
        }
    })

    const runInvestigation = async () => {
        // Submit the request
        const response = await fetch('', {
            method: investigateForm.method, body: new FormData(investigateForm)
        })
        if (!response.ok) {
            loadResultsFromTask('bogus-task-id') // bad task id will generate an error from Django
        }
        const taskId = (await response.json()).id
        // Poll for completion of the investigation up to 60*10 = 600 seconds 
        waitForResults(taskId, 60)
    }

    const waitForResults = async (taskId, retries) => {
        // indicate that investigation is in progress
        document.querySelectorAll('.investigation-indicator').forEach(elt => elt.classList.remove('d-none'))
        document.getElementById('investigate-button').disabled = true
        investigateForm.elements['id_name_fragment'].disabled = true

        const response = await fetch('?' + new URLSearchParams({ id: taskId }))
        if (!response.ok) {
            loadResultsFromTask('bogus-task-id') // bad task id will generate an error from Django
        }
        const result = await response.json()
        if (result.status !== 'ready' && retries > 0) {
            // 10 seconds per retry
            setTimeout(waitForResults, 10000, taskId, retries - 1)
        } else {
            /* Either the response is ready or we timed out waiting. In either case, submit
               the task_id via POST and let Django display an error if it's not ready. Before
               submitting, re-enable the form fields so the POST is valid. Other in-progress
               indicators will be reset when the POST response is loaded. */
            loadResultsFromTask(taskId)
        }
    }

    const loadResultsFromTask = (taskId) => {
        investigateForm.elements['id_name_fragment'].disabled = false
        investigateForm.elements['id_task_id'].value = taskId
        investigateForm.submit()
    }
})
