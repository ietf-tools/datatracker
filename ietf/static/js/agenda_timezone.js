// Copyright The IETF Trust 2021, All Rights Reserved
/*
 Timezone support specific to the agenda page

 To properly handle timezones other than local, needs a method to retrieve
 the current timezone. Set this by passing a method taking no parameters and
 returning the current timezone to the set_current_tz_cb() method.
 This should be done before calling anything else in the file.
 */
(function() {
    'use strict';

    const local_timezone = moment.tz.guess();

    // get_current_tz_cb must be overwritten using set_current_tz_cb
    let get_current_tz_cb = function() {
        throw new Error('Tried to get current timezone before callback registered. Use set_current_tz_cb().');
    };

    // Initialize moments
    function initialize_moments() {
        const times = $('.time');
        $.each(times, function (i, item) {
            item.start_ts = moment.unix(this.getAttribute("data-start-time"))
                .utc();
            item.end_ts = moment.unix(this.getAttribute("data-end-time"))
                .utc();
            if (this.hasAttribute("data-weekday")) {
                item.format = 2;
            } else {
                item.format = 1;
            }
            if (this.hasAttribute("format")) {
                item.format = +this.getAttribute("format");
            }
        });
        const things_with_slots = $('[data-slot-start-ts]');
        $.each(things_with_slots, function (i, item) {
            item.slot_start_ts = moment.unix(this.getAttribute("data-slot-start-ts"))
                .utc();
            item.slot_end_ts = moment.unix(this.getAttribute("data-slot-end-ts"))
                .utc();
        });
    }

    function format_time(t, tz, fmt) {
        let out;
        const mtz = window.meeting_timezone || "UTC";
        switch (fmt) {
        case 0:
            out = t.tz(tz)
                .format('dddd, ') + '<span>' +
                t.tz(tz)
                    .format('MMMM Do YYYY, ') + '</span>' +
                t.tz(tz)
                    .format('HH:mm') + '<span>' +
                t.tz(tz)
                    .format(' Z z') + '</span>';
            break;
        case 1:
            // Note, this code does not work if the meeting crosses the
            // year boundary.
            out = t.tz(tz)
                .format("HH:mm");
            if (+t.tz(tz)
                .dayOfYear() < +t.tz(mtz)
                .dayOfYear()) {
                out = out + " (-1)";
            } else if (+t.tz(tz)
                .dayOfYear() > +t.tz(mtz)
                .dayOfYear()) {
                out = out + " (+1)";
            }
            break;
        case 2:
            out = t.tz(mtz)
                .format("dddd, ")
                .toUpperCase() +
                t.tz(tz)
                    .format("HH:mm");
            if (+t.tz(tz)
                .dayOfYear() < +t.tz(mtz)
                .dayOfYear()) {
                out = out + " (-1)";
            } else if (+t.tz(tz)
                .dayOfYear() > +t.tz(mtz)
                .dayOfYear()) {
                out = out + " (+1)";
            }
            break;
        case 3:
            out = t.utc()
                .format("YYYY-MM-DD");
            break;
        case 4:
            out = t.tz(tz)
                .format("YYYY-MM-DD HH:mm");
            break;
        case 5:
            out = t.tz(tz)
                .format("HH:mm");
            break;
        }
        return out;
    }

    // Format tooltip notice
    function format_tooltip_notice(start, end) {
        let notice = "";

        if (end.isBefore()) {
            notice = "Event ended " + end.fromNow();
        } else if (start.isAfter()) {
            notice = "Event will start " + start.fromNow();
        } else {
            notice = "Event started " + start.fromNow() + " and will end " +
                end.fromNow();
        }
        return '<span class="tooltipnotice">' + notice + '</span>';
    }

    // Format tooltip table
    function format_tooltip_table(start, end) {
        const current_timezone = get_current_tz_cb();
        let out = '<div class="text-start"><table class="table table-sm"><thead><tr><th scope="col"></th><th scope="col">Session start</th><th scope="col">Session end</th></tr></thead>';
        if (window.meeting_timezone !== "") {
            out += '<tr><th class="timehead">Meeting timezone</th><td>' +
                format_time(start, window.meeting_timezone, 0) + '</td><td>' +
                format_time(end, window.meeting_timezone, 0) + '</td></tr>';
        }
        out += '<tr><th class="timehead">Local timezone</th><td>' +
            format_time(start, local_timezone, 0) + '</td><td>' +
            format_time(end, local_timezone, 0) + '</td></tr>';
        if (current_timezone !== 'UTC') {
            out += '<tr><th class="timehead">Selected Timezone</th><td>' +
                format_time(start, current_timezone, 0) + '</td><td>' +
                format_time(end, current_timezone, 0) + '</td></tr>';
        }
        out += '<tr><th class="timehead">UTC</th><td>' +
            format_time(start, 'UTC', 0) + '</td><td>' +
            format_time(end, 'UTC', 0) + '</td></tr>';
        out += '</table>' + format_tooltip_notice(start, end) + '</div>';
        return out;
    }

    // Format tooltip for item
    function format_tooltip(start, end) {
        return '<div class="timetooltiptext">' +
            format_tooltip_table(start, end) +
            '</div>';
    }

    // Add tooltips
    function add_tooltips() {
        $('.time')
            .each(function () {
                const tooltip = $(format_tooltip(this.start_ts, this.end_ts));
                tooltip[0].start_ts = this.start_ts;
                tooltip[0].end_ts = this.end_ts;
                tooltip[0].ustart_ts = moment(this.start_ts)
                    .add(-2, 'hours');
                tooltip[0].uend_ts = moment(this.end_ts)
                    .add(2, 'hours');
                $(this)
                    .closest("th, td")
                    .attr("data-bs-toggle", "popover")
                    .attr("data-bs-content", $(tooltip)
                        .html())
                    .popover({
                        html: true,
                        sanitize: false,
                        trigger: "hover"
                    });
            });
    }

    // Update times on the agenda based on the selected timezone
    function update_times(newtz) {
        $('.current-tz')
            .html(newtz.replaceAll("_", " ").replaceAll("/", " / "));
        $('.time')
            .each(function () {
                if (this.format === 4) {
                    const tz = this.start_ts.tz(newtz).format(" z");
                    const start_doy = this.start_ts.tz(newtz).dayOfYear();
                    const end_doy = this.end_ts.tz(newtz).dayOfYear();
                    if (start_doy === end_doy) {
                        $(this)
                            .html(format_time(this.start_ts, newtz, this.format) +
                                '<span class="d-lg-none"><br></span>-' + format_time(this.end_ts, newtz, 5) + tz);
                    } else {
                        $(this)
                            .html(format_time(this.start_ts, newtz, this.format) +
                                '<span class="d-lg-none"><br></span>-' +
                                format_time(this.end_ts, newtz, this.format) + tz);
                    }
                } else {
                    $(this)
                        .html(format_time(this.start_ts, newtz, this.format) + '<span class="d-lg-none"><br></span>-' +
                            format_time(this.end_ts, newtz, this.format));
                }
            });
        update_tooltips_all();
        update_clock();
    }

    // Update hrefs in anchor tags with the "now-link" class. Mark the target with the "current-session" class.
    function update_now_link(agenda_rows, ongoing_rows, later_rows) {
        agenda_rows.removeClass('current-session');
        const links_to_update = $('a.now-link');
        if (ongoing_rows.length > 0) {
            // sessions are ongoing - find those with the latest start time and mark the first of them as "now"
            const last_start_time = ongoing_rows[ongoing_rows.length - 1].slot_start_ts;
            for (let ii=0; ii < ongoing_rows.length; ii++) {
                const dt = ongoing_rows[ii].slot_start_ts.diff(last_start_time, 'seconds');
                if (Math.abs(dt) < 1) {
                    $(ongoing_rows[ii]).addClass('current-session');
                    links_to_update.attr('href', '#' + ongoing_rows[ii].id);
                    break;
                }
            }
        } else if (later_rows.length > 0) {
            // There were no ongoing sessions, look for the next one to start and mark as current
            $(later_rows[0]).addClass('current-session');
            links_to_update.attr('href', '#' + later_rows[0].id);
        } else {
            // No sessions in the future - meeting has apparently ended
            links_to_update.attr('href', '#');
            links_to_update.addClass('disabled'); // mark link
        }
    }

    function update_ongoing_sessions() {
        const agenda_rows = $('[data-slot-start-ts]');
        const now_moment = moment();
        const ongoing_rows = agenda_rows.filter(function () {
            return now_moment.isBetween(this.slot_start_ts, this.slot_end_ts);
        });
        const later_rows = agenda_rows.filter(function() { return now_moment.isBefore(this.slot_start_ts); });
        // Highlight ongoing based on the current time
        agenda_rows.removeClass("table-warning");
        ongoing_rows.addClass("table-warning");
        update_now_link(agenda_rows, ongoing_rows, later_rows); // update any "now-link" anchors
    }

    // Update tooltips
    function update_tooltips() {
        const tooltips = $('.timetooltiptext');
        tooltips.filter(function () {
            return moment()
                .isBetween(this.ustart_ts, this.uend_ts);
        })
            .each(function () {
                $(this)
                    .html(format_tooltip_table(this.start_ts, this.end_ts));
            });
    }

    // Update all tooltips
    function update_tooltips_all() {
        const tooltips = $('.timetooltiptext');
        tooltips.each(function () {
            $(this)
                .html(format_tooltip_table(this.start_ts, this.end_ts));
        });
    }

    // Update clock
    function update_clock() {
        $('span.current-time')
            .html(format_time(moment(), get_current_tz_cb(), 0));
    }

    function urlParam(name) {
        const results = new RegExp('[\?&]' + name + '=([^&#]*)')
            .exec(window.location.href);
        if (results === null) {
            return null;
        } else {
            return results[1] || 0;
        }
    }

    function init_timers(speedup) {
        speedup = speedup || 1;
        const fast_timer = 60000 / (speedup > 600 ? 600 : speedup);
        update_clock();
        update_ongoing_sessions();
        setInterval(function () { update_clock(); }, fast_timer);
        setInterval(function () { update_ongoing_sessions(); }, fast_timer);
        setInterval(function () { update_tooltips(); }, fast_timer);
        setInterval(function () { update_tooltips_all(); }, 3600000 / speedup);
    }

    /***** make public interface available on window *****/
    window.initialize_moments = initialize_moments;
    window.add_tooltips = add_tooltips;
    window.update_times = update_times;
    window.urlParam = urlParam;
    window.init_timers = init_timers;

    // set method used to find current time zone
    window.set_current_tz_cb = function (fn) {
        get_current_tz_cb = fn;
    };
})();
