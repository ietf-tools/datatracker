// Copyright The IETF Trust 2021, All Rights Reserved

/**
 * Agenda personalization JS methods
 *
 * Requires agenda_timezone.js and timezone.js be included.
 */
const agenda_personalize = (
  function () {
    'use strict';

    let meeting_timezone = document.getElementById('initial-data').dataset.timezone;
    let selection_inputs;

    /**
     * Update the checkbox state to match the filter parameters
     */
    function updateAgendaCheckboxes(filter_params) {
      selection_inputs.forEach((inp) => {
        const item_keywords = inp.dataset.filterKeywords.toLowerCase().split(',');
        if (
          agenda_filter.keyword_match(item_keywords, filter_params.show)
          && !agenda_filter.keyword_match(item_keywords, filter_params.hide)
        ) {
          inp.checked = true;
        } else {
          inp.checked = false;
        }
      });
    }

    function handleFilterParamUpdate(filter_params) {
      updateAgendaCheckboxes(filter_params);
    }

    function handleTableClick(event) {
      if (event.target.name === 'selected-sessions') {
        // hide the tooltip after clicking on a checkbox
        const jqElt = jQuery(event.target);
        if (jqElt.tooltip) {
          jqElt.tooltip('hide');
        }
      }
    }

    window.addEventListener('load', function () {
        // Methods/variables here that are not in ietf_timezone or agenda_filter are from agenda_timezone.js

        // First, initialize_moments(). This must be done before calling any of the update methods.
        // It does not need timezone info, so safe to call before initializing ietf_timezone.
        initialize_moments();  // fills in moments in the agenda data

        // Now set up callbacks related to ietf_timezone. This must happen before calling initialize().
        // In particular, set_current_tz_cb() must be called before the update methods are called.
        set_current_tz_cb(ietf_timezone.get_current_tz);  // give agenda_timezone access to this method
        ietf_timezone.set_tz_change_callback(function (newtz) {
            update_times(newtz);
          }
        );

        // With callbacks in place, call ietf_timezone.initialize(). This will call the tz_change callback
        // after setting things up.
        ietf_timezone.initialize(meeting_timezone);

        // Now make other setup calls from agenda_timezone.js
        add_tooltips();
        init_timers();

        selection_inputs = document.getElementsByName('selected-sessions');

        agenda_filter.set_update_callback(handleFilterParamUpdate);
        agenda_filter.enable();

        document.getElementById('agenda-table')
        .addEventListener('click', handleTableClick);
      }
    );

    // export public interface
    return { meeting_timezone };
  }
)();