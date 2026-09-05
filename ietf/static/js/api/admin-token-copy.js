// Copyright The IETF Trust 2026, All Rights Reserved
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.copy-token').forEach(function (widget) {
    const input = widget.querySelector('input')
    const button = widget.querySelector('button')
    const label = button.textContent

    button.addEventListener('click', function () {
      input.select()
      navigator.clipboard.writeText(input.value).then(function () {
        button.textContent = 'Copied'
        setTimeout(function () {
          button.textContent = label
        }, 3000)
      })
    })
  })
})
