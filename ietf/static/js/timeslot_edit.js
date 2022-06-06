// create a namespace for local JS
timeslotEdit = (function () {
    let deleteModal;
    let timeslotTableBody = document.querySelector('#timeslot-table tbody');

    function initializeDeleteModal() {
        deleteModal = jQuery('#delete-modal');
        deleteModal.eltsToDelete = null; // PK of TimeSlot that modal 'Delete' button should delete
        let spans = deleteModal.find('span');
        deleteModal.elts = {
            unofficialUseWarning: deleteModal.find('.unofficial-use-warning'),
            officialUseWarning: deleteModal.find('.official-use-warning'),
            timeslotNameSpans: spans.filter('.ts-name'),
            timeslotDateSpans: spans.filter('.ts-date'),
            timeslotTimeSpans: spans.filter('.ts-time'),
            timeslotLocSpans: spans.filter('.ts-location'),
            timeslotCountSpans: spans.filter('.ts-count'),
            pluralSpans: spans.filter('.ts-plural'),
            singularSpans: spans.filter('.ts-singular')
        };

        document.getElementById('confirm-delete-button')
            .addEventListener(
                'click',
                () => timeslotEdit.handleDeleteButtonClick()
            );

        function uniqueArray(a) {
            let s = new Set();
            a.forEach(item => s.add(item));
            return Array.from(s);
        }
        deleteModal.openModal = function (eltsToDelete) {
            let eltArray = Array.from(eltsToDelete); // make sure this is an array

            if (eltArray.length > 1) {
                deleteModal.elts.pluralSpans.show();
                deleteModal.elts.singularSpans.hide();
            } else {
                deleteModal.elts.pluralSpans.hide();
                deleteModal.elts.singularSpans.show();
            }
            deleteModal.elts.timeslotCountSpans.text(String(eltArray.length));

            let names = uniqueArray(eltArray.map(elt => elt.dataset.timeslotName));
            if (names.length === 1) {
                names = names[0];
            } else {
                names.sort();
                names = names.join(', ');
            }
            deleteModal.elts.timeslotNameSpans.text(names);

            let dates = uniqueArray(eltArray.map(elt => elt.dataset.timeslotDate));
            if (dates.length === 1) {
                dates = dates[0];
            } else {
                dates = 'Multiple';
            }
            deleteModal.elts.timeslotDateSpans.text(dates);

            let times = uniqueArray(eltArray.map(elt => elt.dataset.timeslotTime));
            if (times.length === 1) {
                times = times[0];
            } else {
                times = 'Multiple';
            }
            deleteModal.elts.timeslotTimeSpans.text(times);

            let locs = uniqueArray(eltArray.map(elt => elt.dataset.timeslotLocation));
            if (locs.length === 1) {
                locs = locs[0];
            } else {
                locs = 'Multiple';
            }
            deleteModal.elts.timeslotLocSpans.text(locs);

            // Check whether any of the elts are used in official / unofficial schedules
            let unofficialUse = eltArray.some(elt => elt.dataset.unofficialUse === 'true');
            let officialUse = eltArray.some(elt => elt.dataset.officialUse === 'true');
            deleteModal.elts.unofficialUseWarning.hide();
            deleteModal.elts.officialUseWarning.hide();
            if (officialUse) {
                deleteModal.elts.officialUseWarning.show();
            } else if (unofficialUse) {
                deleteModal.elts.unofficialUseWarning.show();
            }

            deleteModal.eltsToDelete = eltsToDelete;
            deleteModal.modal('show');
        };

        /**
         * Handle deleting a single timeslot
         *
         * clicked arg is the clicked element, which must be a child of the timeslot element
         */
        function deleteSingleTimeSlot(clicked) {
            deleteModal.openModal([clicked.closest('.timeslot')]);
        }

        /**
         * Handle deleting an entire day worth of timeslots
         *
         * clicked arg is the clicked element, which must be a child of the day header element
         */
        function deleteDay(clicked) {
            // Find all timeslots for this day
            let dateId = clicked.dataset.dateId;
            let timeslots = timeslotTableBody.querySelectorAll(
                ':scope .timeslot[data-date-id="' + dateId + '"]' // :scope prevents picking up results outside table body
            );
            if (timeslots.length > 0) {
                deleteModal.openModal(timeslots);
            }
        }

        /**
         * Handle deleting an entire column worth of timeslots
         *
         * clicked arg is the clicked element, which must be a child of the column header element
         */
        function deleteColumn(clicked) {
            let colId = clicked.dataset.colId;
            let timeslots = timeslotTableBody.querySelectorAll(
                ':scope .timeslot[data-col-id="' + colId + '"]' // :scope prevents picking up results outside table body
            );
            if (timeslots.length > 0) {
                deleteModal.openModal(timeslots);
            }
        }

        /**
         * Event handler for clicks on the timeslot table
         *
         * Handles clicks on all the delete buttons to avoid large numbers of event handlers.
         */
        document.getElementById('timeslot-table')
            .addEventListener('click', function (event) {
                let clicked = event.target; // find out what was clicked
                if (clicked.dataset.deleteScope) {
                    switch (clicked.dataset.deleteScope) {
                    case 'timeslot':
                        deleteSingleTimeSlot(clicked);
                        break;

                    case 'column':
                        deleteColumn(clicked);
                        break;

                    case 'day':
                        deleteDay(clicked);
                        break;

                    default:
                        throw new Error('Unexpected deleteScope "' + clicked.dataset.deleteScope + '"');
                    }
                }
            });
    }

    // Update timeslot classes when DOM changes
    function tstableObserveCallback(mutationList) {
        mutationList.forEach(mutation => {
            if (mutation.type === 'childList' && mutation.target.classList.contains('tscell')) {
                const tscell = mutation.target;
                // mark collisions
                if (tscell.getElementsByClassName('timeslot')
                    .length > 1) {
                    tscell.classList.add('timeslot-collision');
                } else {
                    tscell.classList.remove('timeslot-collision');
                }

                // remove timeslot type classes for any removed timeslots
                mutation.removedNodes.forEach(node => {
                    if (node.classList.contains('timeslot') && node.dataset.timeslotType) {
                        tscell.classList.remove('tstype_' + node.dataset.timeslotType);
                    }
                });

                // now add timeslot type classes for any remaining timeslots
                Array.from(tscell.getElementsByClassName('timeslot'))
                    .forEach(elt => {
                        if (elt.dataset.timeslotType) {
                            tscell.classList.add('tstype_' + elt.dataset.timeslotType);
                        }
                    });
            }
        });
    }

    function initializeTsTableObserver() {
        const observer = new MutationObserver(tstableObserveCallback);
        observer.observe(timeslotTableBody, { childList: true, subtree: true });
    }

    window.addEventListener('load', function () {
        initializeTsTableObserver();
        initializeDeleteModal();
    });

    // function removeTimeslotElement(elt) {
    //     if (elt.parentNode) {
    //         elt.parentNode.removeChild(elt);
    //     }
    // }

    function handleDeleteButtonClick() {
        if (!deleteModal || !deleteModal.eltsToDelete) {
            return; // do nothing if not yet initialized
        }

        let timeslotElts = Array.from(deleteModal.eltsToDelete); // make own copy as Array so we have .map()
        ajaxDeleteTimeSlot(timeslotElts.map(elt => elt.dataset.timeslotPk))
            .fail(function (jqXHR) {
                displayError('Error deleting timeslot: ' + jqXHR.responseText);
            })
            .done(function () {
                timeslotElts.forEach(
                    tse => {
                        tse.closest('td.tscell')
                            .querySelector('.new-timeslot-link')
                            .classList.remove('hidden');
                        tse.parentNode.removeChild(tse);
                    }
                );
            })
            .always(function () { deleteModal.modal('hide'); });
    }

    /**
     * Make an AJAX request to delete a TimeSlot
     *
     * @param pkArray array of PKs of timeslots to delete
     * @returns jqXHR object corresponding to jQuery ajax request
     */
    function ajaxDeleteTimeSlot(pkArray) {
        return jQuery.ajax({
            method: 'post',
            timeout: 5 * 1000,
            data: {
                action: 'delete',
                slot_id: pkArray.join(',')
            }
        });
    }

    function displayError(msg) {
        window.alert(msg);
    }

    // export callable methods
    return {
        handleDeleteButtonClick: handleDeleteButtonClick,
    };
})();