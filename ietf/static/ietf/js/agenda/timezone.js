// Callback for timezone change - called after current_timezone is updated
var timezone_change_callback;

// Initialize moments
function initialize_moments() {
    var times=$('span.time')
    $.each(times, function(i, item) {
	item.start_ts = moment.unix(this.getAttribute("data-start-time")).utc();
	item.end_ts = moment.unix(this.getAttribute("data-end-time")).utc();
	if (this.hasAttribute("weekday")) {
            item.format=2;
	} else {
            item.format=1;
	}
	if (this.hasAttribute("format")) {
	    item.format = +this.getAttribute("format");
	}
    });
    var times=$('[data-slot-start-ts]')
    $.each(times, function(i, item) {
	item.slot_start_ts = moment.unix(this.getAttribute("data-slot-start-ts")).utc();
	item.slot_end_ts = moment.unix(this.getAttribute("data-slot-end-ts")).utc();
    });
}

// Initialize timezone system
function timezone_init(current) {
    var tz_names = moment.tz.names();
    var select = $('#timezone_select');
    
    select.empty();
    $.each(tz_names, function(i, item) {
	if (current === item) {
            select.append($('<option/>', {
		selected: "selected", html: item, value: item }));
	} else {
            select.append($('<option/>', {
		html: item, value: item }));
	}
    });
    initialize_moments();
    select.change(function () {
	update_times(this.value);
    });
    update_times(current);
    add_tooltips();
}

// Select which timezone is used, 0 = meeting, 1 = browser local, 2 = UTC
function use_timezone (val) {
    switch (val) {
    case 0:
	tz = meeting_timezone;
	break;
    case 1:
	tz = local_timezone;
	break;       
    default:
	tz = 'UTC';
	break;
    }
    $('#timezone_select').val(tz);
    update_times(tz);
}

// Format time for item for timezone. Depending on the fmt
// use different formats.
// Formats: 0 = long format "Saturday, October 24th 2020, 13:52 +00:00 UTC"
//          1 = Short format "13:52", "13:52 (-1)", or "13:52 (+1)"
//          2 = Short format with weekday, "Friday, 13:52 (-1)"
//          3 = Date only "2020-10-24"
//          4 = Date and time "2020-10-24 13:52"
//          5 = Time only "13:52".

function format_time(t, tz, fmt) {
    var out;
    var mtz = meeting_timezone;
    if (mtz == "") {
	mtz = "UTC";
    }
    
    switch (fmt) {
    case 0:
	out = t.tz(tz).format('dddd, ') + '<span class="hidden-xs">' +
	    t.tz(tz).format('MMMM Do YYYY, ') + '</span>' +
	    t.tz(tz).format('HH:mm') + '<span class="hidden-xs">' +
	    t.tz(tz).format(' Z z') + '</span>';
	break;
    case 1:
	// Note, this code does not work if the meeting crosses the
	// year boundary.
	out = t.tz(tz).format("HH:mm");
	if (+t.tz(tz).dayOfYear() < +t.tz(mtz).dayOfYear()) {
            out = out + " (-1)";
	} else if (+t.tz(tz).dayOfYear() > +t.tz(mtz).dayOfYear()) {
            out = out + " (+1)";
	}
	break;
    case 2:
	out = t.tz(mtz).format("dddd, ").toUpperCase() +
            t.tz(tz).format("HH:mm");
	if (+t.tz(tz).dayOfYear() < +t.tz(mtz).dayOfYear()) {
            out = out + " (-1)";
	} else if (+t.tz(tz).dayOfYear() > +t.tz(mtz).dayOfYear()) {
            out = out + " (+1)";
	}
	break;
    case 3:
	out = t.utc().format("YYYY-MM-DD");
	break;
    case 4:
	out = t.tz(tz).format("YYYY-MM-DD HH:mm");
	break;
    case 5:
	out = t.tz(tz).format("HH:mm");
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
    var out = '<table><tr><th>Timezone</th><th>Start</th><th>End</th></tr>';
    if (meeting_timezone != "") {
	out += '<tr><td class="timehead">Meeting timezone:</td><td>' + 
	    format_time(start, meeting_timezone, 0) + '</td><td>' +
	    format_time(end, meeting_timezone, 0) + '</td></tr>';
    }
    out += '<tr><td class="timehead">Local timezone:</td><td>' + 
	format_time(start, local_timezone, 0) + '</td><td>' +
	format_time(end, local_timezone, 0) + '</td></tr>';
    if (current_timezone != 'UTC') {
	out += '<tr><td class="timehead">Selected Timezone:</td><td>' + 
	    format_time(start, current_timezone, 0) + '</td><td>' +
	    format_time(end, current_timezone, 0) + '</td></tr>';
    }
    out += '<tr><td class="timehead">UTC:</td><td>' + 
	format_time(start, 'UTC', 0) + '</td><td>' +
	format_time(end, 'UTC', 0) + '</td></tr>';
    out += '</table>' + format_tooltip_notice(start, end);
    return out;
}

// Format tooltip for item
function format_tooltip(start, end) {
    return '<span class="timetooltiptext">' +
	format_tooltip_table(start, end) +
	'</span>';
}

// Add tooltips
function add_tooltips() {
    $('span.time').each(function () {
	var tooltip = $(format_tooltip(this.start_ts, this.end_ts));
	tooltip[0].start_ts = this.start_ts;
	tooltip[0].end_ts = this.end_ts;
	tooltip[0].ustart_ts = moment(this.start_ts).add(-2, 'hours');
	tooltip[0].uend_ts = moment(this.end_ts).add(2, 'hours');
	$(this).parent().append(tooltip);
    });
}

// Update times on the agenda based on the selected timezone
function update_times(newtz) {
    current_timezone = newtz;
    $('span.current-tz').html(newtz);
    $('span.time').each(function () {
	if (this.format == 4) {
	    var tz = this.start_ts.tz(newtz).format(" z");
	    if (this.start_ts.tz(newtz).dayOfYear() ==
		this.end_ts.tz(newtz).dayOfYear()) {
		$(this).html(format_time(this.start_ts, newtz, this.format) +
			     '-' + format_time(this.end_ts, newtz, 5) + tz);
	    } else {
		$(this).html(format_time(this.start_ts, newtz, this.format) +
			     '-' +
			     format_time(this.end_ts, newtz, this.format) + tz);
	    }
	} else {
	    $(this).html(format_time(this.start_ts, newtz, this.format) + '-' +
			 format_time(this.end_ts, newtz, this.format));
	}
    });
    update_tooltips_all();
    update_clock();
    if (timezone_change_callback) {
        timezone_change_callback(newtz);
    }
}

// Highlight ongoing based on the current time
function highlight_ongoing() {
    $("div#now").remove("#now");
    $('.ongoing').removeClass("ongoing");
    var agenda_rows=$('[data-slot-start-ts]')
    agenda_rows = agenda_rows.filter(function() {
        return moment().isBetween(this.slot_start_ts, this.slot_end_ts);
    });
    agenda_rows.addClass("ongoing");
    agenda_rows.first().children("th, td").
	prepend($('<div id="now" class="anchor-target"></div>'));
}

// Update tooltips
function update_tooltips() {
    var tooltips=$('.timetooltiptext');
    tooltips.filter(function() {
	return moment().isBetween(this.ustart_ts, this.uend_ts);
    }).each(function () {
	$(this).html(format_tooltip_table(this.start_ts, this.end_ts));
    });
}

// Update all tooltips
function update_tooltips_all() {
    var tooltips=$('.timetooltiptext');
    tooltips.each(function () {
	$(this).html(format_tooltip_table(this.start_ts, this.end_ts));
    });
}

// Update clock
function update_clock() {
    $('#current-time').html(format_time(moment(), current_timezone, 0));
}

$.urlParam = function(name) {
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results == null) {
	return null;
    } else {
	return results[1] || 0;
    }
}

function init_timers() {
    var fast_timer = 60000 / (speedup > 600 ? 600 : speedup);
    update_clock();
    highlight_ongoing();
    setInterval(function() { update_clock(); }, fast_timer);
    setInterval(function() { highlight_ongoing(); }, fast_timer);
    setInterval(function() { update_tooltips(); }, fast_timer);
    setInterval(function() { update_tooltips_all(); }, 3600000 / speedup);
}

// Register a callback for timezone change
function set_tz_change_callback(cb) {
    timezone_change_callback = cb;
}