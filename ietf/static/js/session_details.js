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
            // Only the slide rows are draggable. This keeps the drop placeholder below out of
            // the way and makes oldDraggableIndex/newDraggableIndex count slide rows only.
            draggable: '.draggable',
            onAdd: function (event) {onAdd(event)},
            onRemove: function (event) {onRemove(event)},
            onEnd: function (event) {onEnd(event)}
        }

        // A session with no slides renders an empty tbody, which has no height and so cannot
        // be dropped on. Give such a tbody a placeholder row to serve as the drop target.
        function make_placeholder (tbody) {
            const row = document.createElement('tr')
            row.classList.add('slides-drop-placeholder')
            const cell = document.createElement('td')
            cell.colSpan = 2
            cell.classList.add('text-body-secondary', 'fst-italic')
            cell.textContent = is_frozen(tbody) ? 'No slides.' : 'No slides. Drag a slide deck here to add it to this session.'
            row.appendChild(cell)
            return row
        }

        // A cancelled or rescheduled session will not happen: decks may be dragged out of it, never into it
        function is_frozen (tbody) {
            return tbody.getAttribute('data-frozen') === 'true'
        }

        function update_placeholder (tbody) {
            const placeholder = tbody.querySelector(':scope > .slides-drop-placeholder')
            if (tbody.querySelector(':scope > .draggable')) {
                if (placeholder) placeholder.remove()
            } else if (!placeholder) {
                tbody.appendChild(make_placeholder(tbody))
            }
        }

        function onAdd (event) {
            const old_session = event.from.getAttribute('data-session')
            const new_session = event.to.getAttribute('data-session')
            $.post(event.to.getAttribute('data-add-to-session'), {
                'order': event.newDraggableIndex + 1,
                'name': event.item.getAttribute('data-name')
            })
            $(event.item).find('td:eq(1)').find('a').each(function () {
                $(this).attr('href', $(this).attr('href').replace(old_session, new_session))
            })
        }

        function onRemove (event) {
            $.post(event.from.getAttribute('data-remove-from-session'), {
                'oldIndex': event.oldDraggableIndex + 1,
                'name': event.item.getAttribute('data-name')
            })
        }

        function onEnd (event) {
            // A drop that was refused snaps the row back where it was; nothing to tell the server
            if (event.to == event.from && !is_frozen(event.from) && event.oldDraggableIndex !== event.newDraggableIndex) {
                $.post(event.from.getAttribute('data-reorder-in-session'), {
                    'oldIndex': event.oldDraggableIndex + 1,
                    'newIndex': event.newDraggableIndex + 1
                })
            }
            // The drop is complete, so both tables now need the right placeholder state.
            update_placeholder(event.from)
            update_placeholder(event.to)
        }

        for (const elt of document.querySelectorAll('.slides tbody')) {
            update_placeholder(elt)
            const frozen = is_frozen(elt)
            sortables.push(Sortable.create(elt, {
                ...options,
                group: { name: 'slides', pull: true, put: !frozen },
                sort: !frozen,
            }))
        }
    }
})
