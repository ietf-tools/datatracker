// Toggle between the file upload and text entry fields according to the selected submission method
document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form.my-3')
    if (!form) {
        return
    }

    const fieldsByMethod = {
        upload: form.querySelector('[name="file"]'),
        enter: form.querySelector('[name="content"]')
    }
    const radios = form.querySelectorAll('[name="submission_method"]')

    function update () {
        const checked = form.querySelector('[name="submission_method"]:checked')
        const method = checked ? checked.value : null
        for (const [key, field] of Object.entries(fieldsByMethod)) {
            if (field) {
                field.parentElement.style.display = key === method ? '' : 'none'
            }
        }
    }

    radios.forEach((radio) => radio.addEventListener('change', update))
    update()
})
