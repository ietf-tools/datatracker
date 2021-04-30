// Copyright The IETF Trust 2021, All Rights Reserved

/*
 Timezone selection handling. Relies on the moment.js library.

 To use, create one (or more) select inputs with class "tz-select". When the initialize()
 method is called, the options in the select will be replaced with the recognized time zone
 names. Time zone can be changed via the select input or by calling the use() method with
 the name of a time zone (or 'local' to guess the user's local timezone).
 */
var ietf_timezone; // public interface

(function () {
    'use strict';
    // Callback for timezone change - called after current_timezone is updated
    var timezone_change_callback;
    var current_timezone;

    // Select timezone to use. Arg is name of a timezone or 'local' to guess local tz.
    function use_timezone (newtz) {
        // Guess local timezone if necessary
        if (newtz.toLowerCase() === 'local') {
            newtz = moment.tz.guess()
        }

        if (current_timezone !== newtz) {
            current_timezone = newtz
            // Update values of tz-select inputs but do not trigger change event
            $('select.tz-select').val(newtz)
            if (timezone_change_callback) {
                timezone_change_callback(newtz)
            }
        }
    }

    /* Initialize timezone system
     *
     * This will set the timezone to the value of 'current'. Set up the tz_change callback
     * before initializing.
     */
    function timezone_init (current) {
        var tz_names = moment.tz.names()
        var select = $('select.tz-select')

        select.empty()
        $.each(tz_names, function (i, item) {
            if (current === item) {
                select.append($('<option/>', {
                    selected: 'selected', html: item, value: item
                }))
            } else {
                select.append($('<option/>', {
                    html: item, value: item
                }))
            }
        })
        select.change(function () {use_timezone(this.value)});
        /* When navigating back/forward, the browser may change the select input's
         * value after the window load event. It does not fire the change event on
         * the input when it does this. The pageshow event occurs after such an update,
         * so trigger the change event ourselves to be sure the UI stays consistent
         * with the timezone select input. */
        window.addEventListener('pageshow', function(){select.change()})
        use_timezone(current);
    }

    // Expose public interface
    ietf_timezone = {
        get_current_tz: function() {return current_timezone},
        initialize: timezone_init,
        set_tz_change_callback: function(cb) {timezone_change_callback=cb},
        use: use_timezone
    }
})();