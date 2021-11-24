// Copyright The IETF Trust 2021, All Rights Reserved

/*
 Timezone support specific to the agenda page

 To properly handle timezones other than local, needs a method to retrieve
 the current timezone. Set this by passing a method taking no parameters and
 returning the current timezone to the set_current_tz_cb() method.
 This should be done before calling anything else in the file.
 */

var local_timezone = moment.tz.guess();

// get_current_tz_cb must be overwritten using set_current_tz_cb
function get_current_tz_cb() {
    throw new Error('Tried to get current timezone before callback registered. Use set_current_tz_cb().');
};

// Initialize moments
window.initialize_moments = function () {
    var times = $('div.time');
    $.each(times, function (i, item) {
        item.start_ts = moment.unix(this.getAttribute("data-start-time"))
            .utc();
        item.end_ts = moment.unix(this.getAttribute("data-end-time"))
            .utc();
        if (this.hasAttribute("weekday")) {
            item.format = 2;
        } else {
            item.format = 1;
        }
        if (this.hasAttribute("format")) {
            item.format = +this.getAttribute("format");
        }
    });
    times = $('[data-slot-start-ts]');
    $.each(times, function (i, item) {
        item.slot_start_ts = moment.unix(this.getAttribute("data-slot-start-ts"))
            .utc();
        item.slot_end_ts = moment.unix(this.getAttribute("data-slot-end-ts"))
            .utc();
    });
}

function format_time(t, tz, fmt) {
    var out;
    var mtz = window.meeting_timezone;
    if (mtz == "") {
        mtz = "UTC";
    }
    switch (fmt) {
        case 0:
            out = t.tz(tz)
                .format('dddd, ') + '<span class="">' +
                t.tz(tz)
                .format('MMMM Do YYYY, ') + '</span>' +
                t.tz(tz)
                .format('HH:mm') + '<span class="">' +
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
    var notice = "";

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
    var current_timezone = get_current_tz_cb();
    var out = '<div class="text-start"><table class="table text-light table-sm"><tr><th></th><th>Session start</th><th>Session end</th></tr>';
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
window.add_tooltips = function () {
    $('div.time')
        .each(function () {
            var tooltip = $(format_tooltip(this.start_ts, this.end_ts));
            tooltip[0].start_ts = this.start_ts;
            tooltip[0].end_ts = this.end_ts;
            tooltip[0].ustart_ts = moment(this.start_ts)
                .add(-2, 'hours');
            tooltip[0].uend_ts = moment(this.end_ts)
                .add(2, 'hours');
            $(this)
                .closest("th, td")
                .attr("data-bs-toggle", "tooltip")
                .attr("title", $(tooltip)
                    .html())
                .tooltip({
                    html: true,
                    sanitize: false
                });
        });
}

// Update times on the agenda based on the selected timezone
window.update_times = function (newtz) {
    $('span.current-tz')
        .html(newtz);
    $('div.time')
        .each(function () {
            if (this.format == 4) {
                var tz = this.start_ts.tz(newtz)
                    .format(" z");
                if (this.start_ts.tz(newtz)
                    .dayOfYear() ==
                    this.end_ts.tz(newtz)
                    .dayOfYear()) {
                    $(this)
                        .html(format_time(this.start_ts, newtz, this.format) +
                            '-' + format_time(this.end_ts, newtz, 5) + tz);
                } else {
                    $(this)
                        .html(format_time(this.start_ts, newtz, this.format) +
                            '-' +
                            format_time(this.end_ts, newtz, this.format) + tz);
                }
            } else {
                $(this)
                    .html(format_time(this.start_ts, newtz, this.format) + '-' +
                        format_time(this.end_ts, newtz, this.format));
            }
        });
    update_tooltips_all();
    update_clock();
};

// Highlight ongoing based on the current time
window.highlight_ongoing = function () {
    $("div#now")
        .remove("#now");
    $('.table-warning')
        .removeClass("table-warning");
    var agenda_rows = $('[data-slot-start-ts]');
    agenda_rows = agenda_rows.filter(function () {
        return moment()
            .isBetween(this.slot_start_ts, this.slot_end_ts);
    });
    agenda_rows.addClass("table-warning");
    agenda_rows.first()
        .children("th, td")
        .
    prepend($('<div id="now" class="anchor-target"></div>'));
}

// Update tooltips
window.update_tooltips = function () {
    var tooltips = $('.timetooltiptext');
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
window.update_tooltips_all = function () {
    var tooltips = $('.timetooltiptext');
    tooltips.each(function () {
        $(this)
            .html(format_tooltip_table(this.start_ts, this.end_ts));
    });
};

// Update clock
window.update_clock = function () {
    $('#current-time')
        .html(format_time(moment(), get_current_tz_cb(), 0));
};

$.urlParam = function (name) {
    var results = new RegExp('[\?&]' + name + '=([^&#]*)')
        .exec(window.location.href);
    if (results == null) {
        return null;
    } else {
        return results[1] || 0;
    }
};

window.init_timers = function () {
    var fast_timer = 60000 / (speedup > 600 ? 600 : speedup);
    update_clock();
    highlight_ongoing();
    setInterval(function () { update_clock(); }, fast_timer);
    setInterval(function () { highlight_ongoing(); }, fast_timer);
    setInterval(function () { update_tooltips(); }, fast_timer);
    setInterval(function () { update_tooltips_all(); }, 3600000 / speedup);
};

// set method used to find current time zone
window.set_current_tz_cb = function (fn) {
    get_current_tz_cb = fn;
};