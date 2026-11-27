"use strict";

var data;
var x_scale;
var bar_height;
var y_label_width;
var y_labels;
var x_axis;
var width;
var now;

// Layout constants (px)
var min_bar_width = 24; // WCAG 2.5.8 minimum target size
var label_padding = 6; // space around a revision label inside its bar
var lane_gap = 2; // vertical gap between lanes within a document's row
var row_gap = 6; // vertical gap between documents' rows

// Layout state, recomputed by layout()
var label_w = {}; // measured width of each revision label
var row_y = {}; // top of each document's row
var row_h = {}; // height of each document's row
var total_height; // height of all rows

function expiration_date(d) {
    return new Date(d.published.getTime() + 1000 * 60 * 60 * 24 * 185);
}

function offset(d) {
    return "translate(" + x_scale(d.published) + ", " +
        (row_y[d.name] + d.lane * (bar_height + lane_gap)) + ")";
}

// The width a bar has if it is strictly proportional to time.
function bar_width(d, i) {
    // check for next rev of this name, or published RFC
    for (i++; i < data.length; i++) {
        if (data[i].name === d.name || data[i].name.match(/^rfc/)) { break; }
    }

    var w;
    if (d.name.match(/^draft-/)) {
        // don't extend the bar past the expiration date of the document
        w = i === data.length ? expiration_date(d) : data[i].published;
        w = w > expiration_date(d) ? expiration_date(d) : w;
    } else {
        // documents other than drafts don't expire after 185 days
        w = i === data.length ? new Date() : data[i].published;
    }
    return x_scale(w) - x_scale(d.published);
}

// Measure the rendered width of each revision label, using the same styling as
// the labels inside the bars.
function measure_labels(chart) {
    var g = chart.append("g")
        .attr("class", "bar");
    data.forEach(function (d) {
        if (label_w[d.rev] === undefined) {
            g.append("text")
                .text(d.rev)
                .each(function () {
                    label_w[d.rev] = this.getBBox()
                        .width;
                })
                .remove();
        }
    });
    g.remove();
}

function scale_x(right) {
    var domain_end = d3.max(data, function (d) { return d.published; });
    now = Date.now();

    // documents that don't expire (e.g., RFCs) have a bar that runs up to now
    var last = data[data.length - 2];
    if (last && !last.name.match(/^draft-/) && domain_end < now) {
        domain_end = new Date(now);
    }

    // scale data to width of container minus y label width
    x_scale = d3.scaleTime()
        .domain([
            d3.min(data, function (d) { return d.published; }),
            domain_end
        ])
        .range([y_label_width, right]);

    // if the end of the timeline is past the current date, show it
    var tv = data.slice(0, -1);
    if (tv[tv.length - 1].published > now) { tv.push(new Date(now)); }

    // x label format
    var format = d3.timeFormat("%b %Y");

    // resort data by publication time to suppress some ticks if they are closer
    // than 12px and have a different label from the one before; and don't add a
    // tick for the final pseudo entry
    tv = tv.sort(function (a, b) { return a.published - b.published; })
        .map(function (d, i, arr) {
            if (i === 0 ||
                x_scale(d.published) > x_scale(arr[i - 1].published) + 12 &&
                format(d.published) !== format(arr[i - 1].published)) {
                return d.published;
            }
        })
        .filter(function (d) { return d !== undefined; });

    x_axis = d3.axisBottom(x_scale)
        .tickValues(tv)
        .tickFormat(function (d) {
            if (d.getTime() < now) { return format(d); }
            return "Now";
        });
}

// Give each bar a width that fits its label and is a usable click target, then
// pack the bars of each document into lanes so that bars made wider than their
// time span don't overlap their neighbours. Returns the rightmost edge used.
function layout() {
    var items = data.slice(0, -1);
    var right = 0;
    var y = 0;

    items.forEach(function (d, i) {
        d.w = Math.max(bar_width(d, i), label_w[d.rev] + label_padding,
            min_bar_width);
        right = Math.max(right, x_scale(d.published) + d.w);
    });

    row_y = {};
    row_h = {};
    y_labels.forEach(function (name) {
        var lane_end = [];
        items
            .filter(function (d) { return d.name === name; })
            .sort(function (a, b) { return a.published - b.published; })
            .forEach(function (d) {
                var x0 = x_scale(d.published);
                // first lane in which this bar doesn't overlap the previous
                // one (a small tolerance lets exactly adjacent bars share one)
                var lane = lane_end.findIndex(function (end) {
                    return x0 + 0.5 >= end;
                });
                if (lane < 0) { lane = lane_end.length; }
                lane_end[lane] = x0 + d.w;
                d.lane = lane;
            });
        var lanes = Math.max(1, lane_end.length);
        row_y[name] = y;
        row_h[name] = lanes * bar_height + (lanes - 1) * lane_gap;
        y += row_h[name] + row_gap;
    });
    total_height = Math.max(0, y - row_gap);
    return right;
}

function update_x_axis() {
    d3.select("#doc-timeline svg .x.axis")
        .call(x_axis)
        .selectAll("text")
        .style("text-anchor", "end")
        .attr("transform", "translate(-14, 2) rotate(-60)");
}

function update_timeline() {
    var chart = d3.select("#doc-timeline svg")
        .attr("width", width);

    scale_x(width);
    var right = layout();
    var limit = width;
    for (var tries = 0; right > width && tries < 5; tries++) {
        // bars at the end are wider than the room left; squeeze the scale
        limit -= right - width + 0.5;
        scale_x(limit);
        right = layout();
    }

    chart.selectAll("g.bar")
        .data(data.slice(0, -1))
        .attr("transform", offset)
        .select("rect")
        .attr("width", function (d) { return d.w; });

    // vertical line from each date on the x axis
    chart.select(".date-lines")
        .selectAll("line")
        .data(x_axis.tickValues(), function (d) { return d.getTime(); })
        .join("line")
        .attr("y1", 0)
        .attr("y2", total_height)
        .attr("x1", function (d) { return x_scale(d); })
        .attr("x2", function (d) { return x_scale(d); });

    // border centered in the gap above each row except the first
    chart.selectAll(".row-borders line")
        .attr("x1", 0)
        .attr("x2", width)
        .attr("y1", function (name) { return row_y[name] - row_gap / 2; })
        .attr("y2", function (name) { return row_y[name] - row_gap / 2; });

    chart.select(".x.axis")
        .attr("transform", "translate(0, " + total_height + ")");
    update_x_axis();

    chart.selectAll(".y.axis text")
        .attr("y", function (name) { return row_y[name] + row_h[name] / 2; });

    // set height of timeline
    var x_label_height = 0;
    chart.select(".x.axis")
        .each(function () {
            x_label_height = this.getBBox()
                .height;
        });
    chart.attr("height", total_height + x_label_height);
}

function draw_timeline() {
    bar_height = parseFloat($("body")
        .css("line-height"));

    var div = $("#doc-timeline");
    div.addClass("my-3");
    if (div.is(":empty")) {
        div.append("<svg></svg>");
    }
    var chart = d3.select("#doc-timeline svg")
        .attr("width", width);

    var defs = chart.append("defs");
    var fade = defs.append("linearGradient")
        .attr("id", "maskGradient");
    fade.append("stop")
        .attr("offset", 0.9)
        .attr("stop-color", "white")
        .attr("stop-opacity", 1);
    fade.append("stop")
        .attr("offset", 1)
        .attr("stop-color", "white")
        .attr("stop-opacity", 0);

    var mask = defs.append("mask")
        .attr("id", "fade")
        .attr("maskContentUnits", "objectBoundingBox");
    mask.append("rect")
        .attr("height", 1)
        .attr("width", 1)
        .attr("fill", "url(#maskGradient)");

    // document names, in order of first appearance (excluding the pseudo entry)
    y_labels = data
        .slice(0, -1)
        .map(function (d) { return d.name; })
        .filter(function (val, i, self) { return self.indexOf(val) === i; });

    // calculate the width of the widest y axis label by drawing them off-screen
    // and measuring the bounding boxes
    y_label_width = 10 + d3.max(y_labels, function (l) {
        var lw;
        var text = chart.append("text");
        text
            .attr("class", "y axis")
            .attr("transform", "translate(0, " + -bar_height + ")");
        text
            .text(l)
            .each(function () {
                lw = this.getBBox()
                    .width;
            })
            .remove()
            .remove();
        return lw;
    });

    measure_labels(chart);

    // re-order data by document name, for CSS background color alternation
    var ndata = [];
    y_labels.forEach(function (l) {
        ndata = ndata.concat(data.filter(function (d) {
            return d.name ===
                l;
        }));
    });
    // keep the pseudo entry last
    data = ndata.concat(data.slice(-1));

    // compute the layout so the bars can be positioned when entered
    scale_x(width);
    layout();

    // enter data (skip the last pseudo entry)
    var bar = chart.selectAll("g.bar")
        .data(data.slice(0, -1));
    var g = bar.enter()
        .append("g");
    g.attr("class", "bar")
        .attr("transform", offset);
    var a = g.append("a");
    a.attr("xlink:href", function (d) { return d.url; });
    a.append("title")
        .text(function (d) {
            return d.name + "-" + d.rev + ", " +
                d3.timeFormat("%Y-%m-%d")(d.published);
        });
    a.append("rect")
        .attr("height", bar_height)
        .attr("width", function (d) { return d.w; })
        .attr("class", "btn")
        .attr("type", "button")
        .attr("mask", function (d, i) {
            // apply gradient if the document is a draft and expired
            if (d.name.match(/^draft-/) &&
                bar_width(d, i) >= x_scale(expiration_date(d)) -
                x_scale(d.published)) {
                return "url(#fade)";
            }
        });

    var text = g.append("text");
    text.attr("x", 3)
        .attr("y", bar_height / 2);
    text.text(function (d) { return d.rev; });

    // faint vertical lines at each date (on top of the bars, so keep them
    // subtle and let clicks pass through)
    chart.append("g")
        .attr("class", "date-lines")
        .style("pointer-events", "none")
        .style("stroke", "var(--bs-body-color)")
        .style("stroke-opacity", 0.25)
        .style("stroke-dasharray", "2 2");

    // borders between rows (appended after the bars so as not to disturb the
    // :nth-child coloring of the bars)
    chart.append("g")
        .attr("class", "row-borders")
        .selectAll("line")
        .data(y_labels.slice(1))
        .enter()
        .append("line")
        .style("stroke", "var(--bs-border-color)")
        .style("stroke-width", 1);

    chart.append("g")
        .attr("class", "x axis");

    // one label per document, centered on its row
    chart.append("g")
        .attr("class", "y axis")
        .selectAll("text")
        .data(y_labels)
        .enter()
        .append("text")
        .attr("x", 1)
        .attr("dy", "0.32em")
        .text(function (name) { return name; });

    update_timeline();
}

d3.json("doc.json")
    .then(function (json) {
        data = json.rev_history;

        if (data.length) {
            // make js dates out of publication dates
            data.forEach(function (d) { d.published = new Date(d.published); });

            // add pseudo entry when the ID will expire
            data.push({
                name: "",
                rev: "",
                published: expiration_date(data[data.length - 1])
            });

            width = $("#doc-timeline")
                .width();
            draw_timeline();
        }
    });

$(window)
    .on({
        resize: function () {
            if (!data) { return; }
            var g = $("#doc-timeline svg");
            g.remove();
            width = $("#doc-timeline")
                .width();
            $("#doc-timeline")
                .append(g);
            update_timeline();
        }
    });
