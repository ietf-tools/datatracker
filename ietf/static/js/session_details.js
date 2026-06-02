// Copyright The IETF Trust 2026, All Rights Reserved
// Relies on other scripts being loaded, see usage in session_details.html
document.addEventListener('DOMContentLoaded', () => {
    // Init with best guess at local timezone.
    ietf_timezone.set_tz_change_callback(timezone_changed) // cb is in upcoming.js
    ietf_timezone.initialize('local')

    // Set up sortable elements if the user can manage materials
    if (document.getElementById('can-manage-materials-flag')) {
        const sortables = []
        const options = {
            group: 'slides',
            animation: 150,
            handle: '.drag-handle',
            onAdd: function (event) {onAdd(event)},
            onRemove: function (event) {onRemove(event)},
            onEnd: function (event) {onEnd(event)}
        }

        function onAdd (event) {
            const old_session = event.from.getAttribute('data-session')
            const new_session = event.to.getAttribute('data-session')
            $.post(event.to.getAttribute('data-add-to-session'), {
                'order': event.newIndex + 1,
                'name': event.item.getAttribute('name')
            })
            $(event.item).find('td:eq(1)').find('a').each(function () {
                $(this).attr('href', $(this).attr('href').replace(old_session, new_session))
            })
        }

        function onRemove (event) {
            const old_session = event.from.getAttribute('data-session')
            $.post(event.from.getAttribute('data-remove-from-session'), {
                'oldIndex': event.oldIndex + 1,
                'name': event.item.getAttribute('name')
            })
        }

        function onEnd (event) {
            if (event.to == event.from) {
                $.post(event.from.getAttribute('data-reorder-in-session'), {
                    'oldIndex': event.oldIndex + 1,
                    'newIndex': event.newIndex + 1
                })
            }
        }

        for (const elt of document.querySelectorAll('.slides tbody')) {
            sortables.push(Sortable.create(elt, options))
        }
    }
})
