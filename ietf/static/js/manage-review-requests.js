/* global $ */
$(function () {
  'use strict'
  const form = $('form.review-requests')
  const saveButtons = form.find('[name=action][value^="save"]')

  function updateSaveButtons () {
    saveButtons.prop(
      'disabled',
      form.find('[name$="-action"][value][value!=""]').length === 0
    )
  }

  function setControlDisplay (row) {
    const action = row.find('[name$="-action"]').val()
    switch (action) {
      case 'assign':
        row.find('.reviewer-controls').show()
        row.find('.close-controls').hide()
        row.find('.assign-action,.close-action').hide()
        break

      case 'close':
        row.find('.reviewer-controls').hide()
        row.find('.close-controls').show()
        row.find('.assign-action,.close-action').hide()
        break

      default:
        row.find('.reviewer-controls,.close-controls').hide()
        row.find('.assign-action,.close-action').show()
    }

    updateSaveButtons()
  }

  form.find('.assign-action button')
    .on('click', function () {
      const row = $(this).closest('.review-request')
      const select = row.find('.reviewer-controls [name$="-reviewer"]')
      if (!select.val()) {
      // collect reviewers already assigned in this session
        const reviewerAssigned = {}
        select.find('option')
          .each(function () {
            if (this.value) {
              reviewerAssigned[this.value] = 0
            }
          })

        form.find('[name$="-action"][value="assign"]')
          .each(function () {
            const v = $(this)
              .closest('.review-request')
              .find('[name$="-reviewer"]')
              .val()
            if (v) {
              reviewerAssigned[v] += 1
            }
          })

        // by default, the select box contains a sorted list, so
        // we should be able to select the first, unless that
        // person has already been assigned to review in this
        // session
        let found = null
        const options = select.find('option').get()
        for (let round = 0; round < 100 && !found; ++round) {
          for (let i = 0; i < options.length && !found; ++i) {
            const v = options[i].value
            if (!v) {
              continue
            }

            if (reviewerAssigned[v] === round) {
              found = v
            }
          }
        }

        if (found) {
          select.val(found)
        }
      }

      row.find('[name$="-action"]').val('assign')
      setControlDisplay(row)
    })

  form.find('.reviewer-controls .undo')
    .on('click', function () {
      const row = $(this).closest('.review-request')
      row.find('[name$="-action"]').val('')
      row.find('[name$="-reviewer"]').val($(this).data('initial'))
      setControlDisplay(row)
    })

  form.find('.close-action button')
    .on('click', function () {
      const row = $(this).closest('.review-request')
      row.find('[name$="-action"]').val('close')
      setControlDisplay(row)
    })

  form.find('.close-controls .undo')
    .on('click', function () {
      const row = $(this).closest('.review-request')
      row.find('[name$="-action"]').val('')
      setControlDisplay(row)
    })

  form.find('.assign-action,.close-action')
    .each(function () {
      const row = $(this).closest('.review-request')
      setControlDisplay(row)
    })

  updateSaveButtons()
})
