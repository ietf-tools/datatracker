var filtered_event_list = []; // currently visible list
var display_events = []; // filtered events, processed for calendar display
var event_calendar; // handle on the calendar object
var current_tz = 'UTC';

// Test whether an event should be visible given a set of filter parameters
function calendar_event_visible(filter_params, event) {
    // Visible if filtering is disabled or event has no keywords
    if (!agenda_filter.filtering_is_enabled(filter_params) || !event.filter_keywords) {
        return true;
    }

    // Visible if shown and not hidden
    return (!agenda_filter.keyword_match(filter_params.hide, event.filter_keywords) &&
        agenda_filter.keyword_match(filter_params.show, event.filter_keywords));
}

/* Apply filter_params to the event list */
function filter_calendar_events(filter_params, event_list) {
    var filtered_output = [];
    for (var ii = 0; ii < event_list.length; ii++) {
        var this_event = event_list[ii];
        if (calendar_event_visible(filter_params, this_event)) {
            filtered_output.push(this_event);
        }
    }
    return filtered_output;
}

// format a moment in a tz
var moment_formats = { time: 'HH:mm', date: 'YYYY-MM-DD', datetime: 'YYYY-MM-DD HH:mm' };

function format_moment(t_moment, tz, fmt_type) {
    return t_moment.tz(tz)
        .format(moment_formats[fmt_type]);
}

function make_display_events(event_data, tz) {
    var calendarEl = document.getElementById('calendar');
    var glue = calendarEl.clientWidth > 720 ? ' ' : '\n';
    return $.map(event_data, function (src_event) {
        var title;
        // Render IETF meetings with meeting dates, sessions with actual times
        if (src_event.ietf_meeting_number) {
            title = 'IETF ' + src_event.ietf_meeting_number;
        } else {
            title = (format_moment(src_event.start_moment, tz, 'time') + '-' +
                format_moment(src_event.end_moment, tz, 'time') +
                glue + (src_event.group || 'Invalid event'));
        }
        return {
            title: title,
            start: format_moment(src_event.start_moment, tz, 'datetime'),
            end: format_moment(src_event.end_moment, tz, 'datetime'),
            url: src_event.url
        }; // all events have the URL
    });
}

// Initialize or update the calendar, updating the filtered event list and/or timezone
function update_calendar(tz, filter_params) {
    if (filter_params) {
        // Update event list if we were called with filter params
        filtered_event_list = filter_calendar_events(filter_params, all_event_list);
    }
    display_events = make_display_events(filtered_event_list, tz);

    if (event_calendar) {
        event_calendar.refetchEvents();
    } else {
        /* Initialize the calendar object.
         * The event source is a function that simply returns the current global list of
         * filtered events.
         */
        var calendarEl = document.getElementById('calendar');
        event_calendar = new FullCalendar(calendarEl, {
            plugins: [dayGridPlugin],
            initialView: 'dayGridMonth',
            displayEventTime: false,
            events: function (fInfo, success) { success(display_events); },
            eventDidMount: function (info) {
                $(info.el)
                    .tooltip({ title: info.event.title });
            },
            eventDisplay: 'block'
        });
        event_calendar.render();
    }
}

function update_meeting_display(filter_params) {
    var meeting_rows = $("#upcoming-meeting-table tr.entry");
    if (!agenda_filter.filtering_is_enabled(filter_params)) {
        meeting_rows.show();
        return;
    }

    // hide everything that has keywords
    meeting_rows.filter(function (index, row) {
            return !!$(row)
                .attr('data-filter-keywords');
        })
        .hide();

    $.each(filter_params['show'], function (i, v) {
        agenda_filter.rows_matching_filter_keyword(meeting_rows, v)
            .show();
    });
    $.each(filter_params['hide'], function (i, v) {
        agenda_filter.rows_matching_filter_keyword(meeting_rows, v)
            .hide();
    });
}

window.update_view = function (filter_params) {
    update_meeting_display(filter_params);
    update_calendar(current_tz, filter_params);
};

function format_session_time(session_elt, tz) {
    var start = moment.utc($(session_elt)
        .attr('data-start-utc'));
    var end = moment.utc($(session_elt)
        .attr('data-end-utc'));
    return format_moment(start, tz, 'datetime') + '-' + format_moment(end, tz, 'time');
}

function format_meeting_time(meeting_elt, tz) {
    var meeting_tz = $(meeting_elt)
        .attr('data-time-zone');
    var start = moment.tz($(meeting_elt)
            .attr('data-start-date'), meeting_tz)
        .startOf('day');
    var end = moment.tz($(meeting_elt)
            .attr('data-end-date'), meeting_tz)
        .endOf('day');
    return format_moment(start, tz, 'date') + ' to ' + format_moment(end, tz, 'date');
}

window.timezone_changed = function (newtz) {
    if (!newtz) {
        ietf_timezone.initialize('local');
        newtz = ietf_timezone.get_current_tz();
    }
    // update times for events in the table
    if (current_tz !== newtz) {
        current_tz = newtz;
        $('.session-time')
            .each(function () {
                $(this)
                    .html(format_session_time(this, newtz));
            });
        $('.meeting-time')
            .each(function () {
                $(this)
                    .html(format_meeting_time(this, newtz));
            });
    }

    update_calendar(newtz);
};