// Copyright The IETF Trust 2021, All Rights Reserved

/**
 * Agenda personalization JS methods
 *
 * Requires agenda_timezone.js and timezone.js be included.
 */
'use strict';

/**
 * Update the checkbox state to match the filter parameters
 */
function updateAgendaCheckboxes(filter_params) {
    var selection_inputs = document.getElementsByName('selected-sessions');
    selection_inputs.forEach((inp) => {
        const item_keywords = inp.dataset.filterKeywords.toLowerCase()
            .split(',');
        if (
            agenda_filter.keyword_match(item_keywords, filter_params.show) &&
            !agenda_filter.keyword_match(item_keywords, filter_params.hide)
        ) {
            inp.checked = true;
        } else {
            inp.checked = false;
        }
    });
}

window.handleFilterParamUpdate = function (filter_params) {
    updateAgendaCheckboxes(filter_params);
};

window.handleTableClick = function (event) {
    if (event.target.name === 'selected-sessions') {
        // hide the tooltip after clicking on a checkbox
        const jqElt = jQuery(event.target);
        if (jqElt.tooltip) {
            jqElt.tooltip('hide');
        }
    }
};