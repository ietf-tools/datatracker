// Copyright The IETF Trust 2021, All Rights Reserved
/* global moment */
/*
 Timezone selection handling. Relies on the moment.js library.

 To use, create one (or more) select inputs with class "tz-select". When the initialize()
 method is called, the options in the select will be replaced with the recognized time zone
 names. Time zone can be changed via the select input or by calling the use() method with
 the name of a time zone (or 'local' to guess the user's local timezone).
 */
(function () {
    'use strict';

    // Callback for timezone change - called after current_timezone is updated
    let timezone_change_callback;
    let current_timezone;
    let tz_radios;
    let tz_selects;

    // Select timezone to use. Arg is name of a timezone or 'local' to guess local tz.
    function use_timezone(newtz) {
        if (current_timezone !== newtz) {
            current_timezone = newtz;
            // Update values of tz-select inputs but do not trigger change event
            $('select.tz-select')
                .val(newtz);
            if (timezone_change_callback) {
                timezone_change_callback(newtz);
            }
            tz_radios.filter(`[value="${newtz}"]`).prop('checked', true);
            tz_radios.filter(`[value!="${newtz}"]`).prop('checked', false);
            tz_selects.val(newtz);
            tz_selects.trigger('change.select2'); // notify only select2 of change to avoid change event storm
        }
    }

    function handle_change_event(evt) {
        const newtz = evt.target.value;
        use_timezone(newtz); // use the requested timezone
    }

    /* Initialize timezone system
     *
     * This will set the timezone to the value of 'current'. Set up the tz_change callback
     * before initializing.
     */
    function timezone_init(current) {
        var tz_names = moment.tz.names();
        if (current === 'local') {
            current = moment.tz.guess();
        }
        tz_selects = $('select.tz-select');
        tz_selects.empty();
        $.each(tz_names, function (i, item) {
            tz_selects.append($('<option/>', {
                selected: current === item,
                html: item,
                value: item
            }));
        });
        tz_radios = $('input.tz-select[type="radio"]');
        tz_radios.filter('[value="local"]').prop('value', moment.tz.guess());
        tz_radios.on('change', handle_change_event);
        tz_selects.on('change', handle_change_event);
        /* When navigating back/forward, the browser may change the select input's
         * value after the window load event. It does not fire the change event on
         * the input when it does this. The pageshow event occurs after such an update,
         * so trigger the change event ourselves to be sure the UI stays consistent
         * with the timezone select input. */
        window.addEventListener('pageshow', function () { tz_selects.trigger("change"); });
        use_timezone(current);
    }

    // Expose public interface
    window.ietf_timezone = {
        get_current_tz: function () { return current_timezone; },
        initialize: timezone_init,
        set_tz_change_callback: function (cb) { timezone_change_callback = cb; },
        use: use_timezone
    };
})();