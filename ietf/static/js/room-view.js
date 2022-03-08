var start_map = items.map(function (el, i) {
    return { room_index: el.room_index, start_time: el.delta_from_beginning, index: i };
});
start_map.sort(function (a, b) {
    if (a.room_index != b.room_index) {
        return (a.room_index - b.room_index);
    }
    return a.start_time - b.start_time;
});

var end_map = items.map(function (el, i) {
    return { room_index: el.room_index, end_time: el.delta_from_beginning + el.duration, index: i };
});
end_map.sort(function (a, b) {
    if (a.room_index != b.room_index) {
        return (a.room_index - b.room_index);
    }
    return a.end_time - b.end_time;
});

var si = 0;
var ei = 0;
var overlap = 0;
var max_lanes = 0;
var next_lane = [];

var start_overlap = si;
while (si < items.length) {
    var start_room_change = false;
    while (!start_room_change && si < items.length && start_map[si].start_time < end_map[ei].end_time) {
        overlap++;
        if (next_lane.length > 0) {
            items[start_map[si].index].lane = next_lane.shift();
        } else {
            items[start_map[si].index].lane = max_lanes;
            max_lanes++;
        }
        start_room_change = (si + 1 == items.length || start_map[si].room_index != start_map[si + 1].room_index);
        si++;
    }
    var end_room_change = false;
    while (ei < items.length && !end_room_change && (start_room_change || si == items.length || start_map[si].start_time >= end_map[ei].end_time)) {
        next_lane.push(items[end_map[ei].index].lane);
        overlap--;
        end_room_change = (ei + 1 == items.length || end_map[ei].room_index != end_map[ei + 1].room_index);
        ei++;
    }
    if (overlap == 0) {
        for (var i = start_overlap; i < si; i++) {
            items[start_map[i].index].lanes = max_lanes;
        }
        max_lanes = 0;
        next_lane = [];
        start_overlap = si;
    }
}

var fg = {
    app: "#008",
    art: "#808",
    gen: "#080",
    int: "#088",
    ops: "#800",
    rai: "#808",
    rtg: "#880",
    sec: "#488",
    tsv: "#484",
    irtf: "#448",
    break: "#000"
};

var bg = {
    app: "#eef",
    art: "#fef",
    gen: "#efe",
    int: "#eff",
    ops: "#fee",
    rai: "#fef",
    rtg: "#ffe",
    sec: "#dff",
    tsv: "#dfd",
    irtf: "#ddf",
    break: "#fff"
};

var divlist = [];

var lastfrag;
var lastheight;
var lastwidth;

var padding = 2;
var border = 1;

setInterval(animate, 50);

window.draw_calendar = function () {
    window.setTimeout(draw_calendar, 1000);

    var width = $('#mtgheader')
        .width();
    var offset = $('#mtgheader')
        .offset()
        .left;
    var height = document.body.clientHeight;

    if (lastheight == height &&
        lastwidth == width &&
        lastfrag == window.location.hash) {
        return;
    }

    var i;

    var day_start = 23 * 60 + 59;
    var day_end = 0;

    /* Find our boundaries */
    for (i = 0; i < items.length; i++) {
        {
            var start_time = parseInt(items[i].time.substr(0, 2), 10) * 60 +
                parseInt(items[i].time.substr(2, 2), 10);
            var end_time = start_time + (items[i].duration / 60);

            if (start_time < day_start) { day_start = start_time; }
            if (end_time > day_end) { day_end = end_time; }
        }
    }

    var timelabel_width = width * 0.020;
    var header_height = height * 0.05;
    var header_offset = $('#daytabs')
        .outerHeight(true) + $('#mtgheader')
        .outerHeight(true);

    var num_minutes = day_end - day_start;
    var minute_height = (height - header_height - header_offset) / num_minutes;

    var daydiv;
    for (i = 0; i < num_days; i++) {
        daydiv = document.getElementById("day" + i);
        while (daydiv.childNodes.length) { daydiv.removeChild(daydiv.childNodes[0]); }
    }

    var room_width = (width - timelabel_width) / (rooms_count ? rooms_count : 1);
    for (var day = 0; day < num_days; day++) {
        for (var ri = 0; ri < room_names.length; ri++) {
            var e = document.createElement("div");

            e.style.border = "solid";
            e.style.borderWidth = border + "px";

            e.style.background = "#2647f0";
            e.style.color = "#fff";
            e.style.borderColor = "#000 #fff";
            e.style.borderColor = "#2647f0 #2647f0 #000 #2647f0";

            e.style.display = "block";
            e.style.overflow = "hidden";
            e.style.position = "absolute";

            e.style.top = header_offset + "px";
            e.style.left = (offset + timelabel_width + ri * room_width) + "px";
            e.style.width = room_width + "px";
            e.style.height = header_height + "px";

            e.style.margin = 0 + "px";
            e.style.padding = padding + "px";
            e.style.fontFamily = "sans-serif";
            e.style.fontSize = (header_height * 0.25) + "px";

            e.style.textAlign = "center";

            var div = document.createElement("div");
            div.appendChild(document.createTextNode(room_names[ri]));
            if (room_functional_names[ri].length > 0) {
                div.appendChild(document.createElement("br"));
                div.appendChild(document.createTextNode(room_functional_names[ri]));
            }
            if (room_typelabels[ri].length > 0) {
                div.title = room_names[ri] + "\n" + room_functional_names[ri] + "\n" + room_typelabels[ri];
            }
            e.appendChild(div);
            document.getElementById("day" + day)
                .appendChild(e);

            //-----------------------------------------------------------------
            // Draw column border
            //-----------------------------------------------------------------
            e = document.createElement("div");

            e.style.border = "solid";
            e.style.borderWidth = border + "px";

            e.style.color = "#000";
            e.style.borderColor = "#fff #000";

            e.style.display = "block";
            e.style.overflow = "hidden";
            e.style.position = "absolute";

            e.style.top = (header_height + header_offset) + "px";
            e.style.left = (offset + timelabel_width + ri * room_width) + "px";
            e.style.width = room_width + "px";
            e.style.height = (height - header_height - header_offset) + "px";

            e.style.margin = 0 + "px";
            e.style.padding = padding + "px";

            document.getElementById("day" + day)
                .appendChild(e);

        }

        //-----------------------------------------------------------------
        // Draw hour lines
        //-----------------------------------------------------------------
        for (var time = day_start - (day_start % 60) + 60; time < day_end; time += 60) {
            e = document.createElement("div");
            e.style.borderTopStyle = "solid";
            e.style.boderTopWidth = "2px";
            e.style.borderColor = "#f8f8f8";
            e.style.overflow = "hidden";
            e.style.position = "absolute";
            e.style.top = (header_height + header_offset + (time - day_start) * minute_height) + "px";
            e.style.left = (offset + timelabel_width) + "px";
            e.style.width = (width - timelabel_width) + "px";
            e.style.height = 0 + "px";
            e.style.zIndex = "-1";
            e.style.margin = 0 + "px";
            e.style.padding = padding + "px";
            document.getElementById("day" + day)
                .appendChild(e);

            e = document.createElement("div");
            e.style.overflow = "hidden";
            e.style.position = "absolute";
            e.style.top = (header_height + header_offset - (header_height * 0.125) + (time - day_start) * minute_height) + "px";
            e.style.left = offset + "px";
            e.style.width = timelabel_width + "px";
            e.style.height = (header_height * 0.5) + "px";
            e.style.zIndex = "-1";
            e.style.margin = 0 + "px";
            e.style.padding = padding;
            e.style.fontFamily = "sans-serif";
            e.style.fontSize = (header_height * 0.25) + "px";
            e.style.textAlign = "right";
            e.style.color = "#e0e0e0";
            var label = time / 60 + "00";
            if (label.length < 4) {
                label = "0" + label;
            }
            e.appendChild(document.createTextNode(label));

            document.getElementById("day" + day)
                .appendChild(e);
        }

    }

    //-----------------------------------------------------------------
    // Draw a block for each meeting
    //-----------------------------------------------------------------
    var resize_func = function (div, t, l, w, h, to_fit) { return function () { resize(div, t, l, w, h, to_fit); }; };
    var maximize_func = function (e) { return function () { maximize(e); }; };

    for (i = 0; i < items.length; i++) {
        {
            start_time = parseInt(items[i].time.substr(0, 2), 10) * 60 +
                parseInt(items[i].time.substr(2, 2), 10);
            end_time = start_time + (items[i].duration / 60);

            var sess_width = room_width / items[i].lanes;
            var sess_height = ((end_time - start_time) * minute_height);
            var room_left = offset + timelabel_width + items[i].room_index * room_width;
            var sess_left = room_left + sess_width * items[i].lane;
            var sess_top = ((start_time - day_start) * minute_height) + header_height + header_offset;

            e = document.createElement("div");
            e.style.border = "solid";
            e.style.borderWidth = border + "px";

            if (fg[items[i].area]) {
                e.style.background = bg[items[i].area];
                e.style.color = fg[items[i].area];
                e.style.borderColor = fg[items[i].area];
            } else {
                e.style.background = "#e0e0e0";
                e.style.color = "#000000";
                e.style.borderColor = "#000000";
            }

            e.style.display = "block";
            e.style.overflow = "hidden";
            e.style.position = "absolute";
            e.style.top = sess_top + "px";
            e.style.left = sess_left + "px";
            e.style.width = sess_width + "px";
            e.style.height = sess_height + "px";
            e.style.margin = 0 + "px";
            e.style.padding = padding + "px";
            e.style.fontFamily = "sans-serif";
            e.style.fontSize = "8pt";
            if (items[i].from_base_schedule)
                e.style.opacity = 0.5;

            e.id = i;

            e.onmouseover = resize_func(e, sess_top, room_left,
                room_width,
                sess_height, true);

            e.onmouseout = resize_func(e, sess_top, sess_left, sess_width, sess_height, false);

            if (items[i].agenda) {
                e.onclick = maximize_func(e);
                e.style.cursor = "pointer";
            }

            div = document.createElement("div");
            div.appendChild(document.createTextNode(items[i].verbose_time));
            div.appendChild(document.createElement("br"));

            label = items[i].name;
            if (label.length == 0) { label = "Free Slot"; }
            if (items[i].wg && fg[items[i].area]) {
                label = label + " (" + items[i].wg + ")";
            }
            var bold = document.createElement("span");
            bold.appendChild(document.createTextNode(label));
            bold.style.fontWeight = "bold";
            div.appendChild(bold);

            e.appendChild(div);

            document.getElementById("day" + items[i].day)
                .appendChild(e);
        }
    }

    lastheight = height;
    lastwidth = width;
    lastfrag = window.location.hash;
};

function resize(div, t2, l2, w2, h2, to_fit) {
    // Move the element to the front
    var parent = div.parentElement;
    parent.removeChild(div);
    parent.appendChild(div);

    div.t2 = t2;
    div.l2 = l2;
    div.w2 = w2;
    div.h2 = h2;
    div.to_fit = to_fit;
    div.percent = 0;
    divlist.push(div);
}

function animate() {
    var offset = $('#mtgheader')
        .offset()
        .left;
    var i;
    for (i = divlist.length - 1; i >= 0; i--) {
        var div = divlist[i];
        if (div.percent < 100) {
            div.percent += 5;
            var t1 = parseFloat(div.style.top.replace("px", "")) + "px";
            var l1 = offset + parseFloat(div.style.left.replace("px", "")) + "px";
            var w1 = parseFloat(div.style.width.replace("px", "")) + "px";
            var h1 = parseFloat(div.style.height.replace("px", "")) + "px";

            div.style.top = wavg(t1, div.t2, div.percent) + "px" + "px";
            div.style.left = offset + wavg(l1, div.l2, div.percent) + "px" + "px";
            div.style.width = wavg(w1, div.w2, div.percent) + "px" + "px";
            div.style.height = wavg(h1, div.h2, div.percent) + "px" + "px";

            if (t1 == div.t2 && l1 == div.l2 &&
                w1 == div.w2 && h1 == div.h2) { div.percent = 100; }

        } else {
            if (div.to_fit) {
                var tmp = div.style.height;
                div.style.removeProperty("height");
                if (div.h2 < div.clientHeight) {
                    div.h2 = div.clientHeight;
                    div.percent = 0;
                } else {
                    divlist.remove(i);
                    if (div.callback) {
                        tmp = div.callback;
                        div.callback = undefined;
                        tmp();
                    }
                }
                div.style.height = tmp + "px";
            } else {
                divlist.remove(i);
                if (div.callback) {
                    tmp = div.callback;
                    div.callback = undefined;
                    tmp();
                }
            }
        }
    }

}

function finish_maximize(e) {
    if (!items[e.id].agenda) {
        return;
    }

    e.insertBefore(document.createElement("br"), e.firstChild);
    var offset = $('#mtgheader')
        .offset()
        .left;

    var minimize_func = function (e) { return function () { minimize(e); }; };
    var i = document.createElement("i");
    i.classList.add('bi', 'bi-x-lg');
    i.style.cssFloat = "right";
    i.onclick = minimize_func(e);
    i.style.cursor = "pointer";
    e.insertBefore(i, e.firstChild);

    var h = document.createElement("span");
    h.appendChild(document.createTextNode(items[e.id].dayname));
    h.style.fontWeight = "bold";
    e.insertBefore(h, e.firstChild);
    e.style.fontSize = "10pt";

    var tmp = e.style.height;
    e.style.removeProperty("height");
    var used_height = e.clientHeight;
    e.style.height = tmp + "px";

    var frame = document.createElement("iframe");
    frame.setAttribute("src", items[e.id].agenda);

    frame.style.position = "absolute";
    frame.style.left = (offset + 8) + "px";
    frame.style.width = (e.clientWidth - 16) + "px";
    frame.style.top = (used_height + 8) + "px";
    frame.style.height = (e.clientHeight - used_height - 16) + "px";

    frame.style.background = "#fff";
    frame.style.overflow = "auto";
    frame.id = "agenda";

    frame.style.border = e.style.border;
    frame.style.borderWidth = border + "px";
    frame.style.padding = padding + "px";
    frame.style.borderColor = e.style.borderColor;

    e.appendChild(frame);
}

function finish_minimize(e) {
    e.onmouseover = e.oldmouseover;
    e.onmouseout = e.oldmouseout;
    e.oldmouseover = undefined;
    e.oldmouseout = undefined;
    e.style.cursor = "pointer";
}

function maximize(e) {
    if (e.onmouseover) {
        e.oldmouseover = e.onmouseover;
        e.oldmouseout = e.onmouseout;
        e.onmouseover = undefined;
        e.onmouseout = undefined;
        e.style.cursor = "auto";

        var callback_func = function (e) { return function () { finish_maximize(e); }; };
        e.callback = callback_func(e);

        resize(e, 0, 0,
            document.body.clientWidth,
            document.body.clientHeight);
    }
}

function minimize(e) {
    var agenda = document.getElementById("agenda");
    if (agenda) {
        e.removeChild(agenda);
    }

    var callback_func = function (e) { return function () { finish_minimize(e); }; };
    e.callback = callback_func(e);
    e.oldmouseout();

    e.removeChild(e.firstChild);
    e.removeChild(e.firstChild);
    e.removeChild(e.firstChild);
    e.style.fontSize = "8pt";
}

function wavg(x1, x2, percent) {
    if (percent == 100) { return x2; }
    var res = x2 * (percent / 100) + x1 * ((100 - percent) / 100);
    return res;
}

// Array Remove - By John Resig (MIT Licensed)
Array.prototype.remove = function (from, to) {
    var rest = this.slice((to || from) + 1 || this.length);
    this.length = from < 0 ? this.length + from : from;
    return this.push.apply(this, rest);
};