"use strict";

var data;
var x_scale;
var bar_y;
var bar_height;
var y_label_width;
var x_axis;
var width;
var now;

function expiration_date(d) {
    return new Date(d.published.getTime() + 1000 * 60 * 60 * 24 * 185);
}


function max(arr) {
    return Math.max.apply(null, Object.keys(arr).map(function(e) {
        return arr[e];
    }));
}


function offset(d) {
    if (bar_y[d.name] === undefined) {
        var m = Object.keys(bar_y).length === 0 ? -bar_height : max(bar_y);
        bar_y[d.name] = m + bar_height;
    }
    return "translate(" + x_scale(d.published) + ", " + bar_y[d.name] + ")";
}


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


function scale_x() {
    width = $("#timeline").width();

    // scale data to width of container minus y label width
    x_scale = d3.time.scale().domain([
        d3.min(data, function(d) { return d.published; }),
        d3.max(data, function(d) { return d.published; })
    ]).range([y_label_width, width]);


    // if the end of the timeline is past the current date, show it
    var tv = data.slice(0, -1);
    now = Date.now();
    if (tv[tv.length - 1].published > now) { tv.push(new Date(now)); }

    // x label format
    var format = d3.time.format("%b %Y");

    // resort data by publication time to suppress some ticks if they are closer
    // than 12px and have a different label from the one before; and don't add a
    // tick for the final pseudo entry
    tv = tv.sort(function(a, b) { return a.published - b.published; })
        .map(function(d, i, arr) {
            if (i === 0 ||
                x_scale(d.published) > x_scale(arr[i - 1].published) + 12 &&
                format(d.published) !== format(arr[i - 1].published)) {
                return d.published;
            }
        }).filter(function(d) { return d !== undefined; });

    x_axis = d3.svg.axis()
        .scale(x_scale)
        .tickValues(tv)
        .tickFormat(function(d) {
            if (d.getTime() < now) { return format(d); }
            return "Now";
        })
        .orient("bottom");
}


function update_x_axis() {
    d3.select("#timeline svg .x.axis").call(x_axis)
        .selectAll("text")
        .style("text-anchor", "end")
        .attr("transform", "translate(-14, 2) rotate(-60)");
}


function update_timeline() {
    bar_y = {};
    scale_x();
    var chart = d3.select("#timeline svg").attr("width", width);
    // enter data (skip the last pseudo entry)
    var bar = chart.selectAll("g").data(data.slice(0, -1));
    bar.attr("transform", offset).select("rect").attr("width", bar_width);
    update_x_axis();
}


function draw_timeline() {
    bar_height = parseFloat($("body").css("line-height"));

    var div = $("#timeline");
    if (div.is(":empty")) {
        div.append("<svg xmlns:xlink='http://www.w3.org/1999/xlink'></svg>");
    }
    var chart = d3.select("#timeline svg").attr("width", width);

    var defs = chart.append("defs");
    var fade = defs.append("linearGradient")
        .attr("id", "maskGradient");
    fade.append("stop")
        .attr({
            offset: 0.9,
            "stop-color": "white",
            "stop-opacity": 1
        });
    fade.append("stop")
        .attr({
            offset: 1,
            "stop-color": "white",
            "stop-opacity": 0
        });

    defs.append("mask")
        .attr({
            id: "fade",
            maskContentUnits: "objectBoundingBox"
        })
        .append("rect")
            .attr({
                height: 1,
                width: 1,
                fill: "url(#maskGradient)"
            });

    var y_labels = data
        .map(function(d) { return d.name; })
        .filter(function(val, i, self) { return self.indexOf(val) === i; });

    // calculate the width of the widest y axis label by drawing them off-screen
    // and measuring the bounding boxes
    y_label_width = 10 + d3.max(y_labels, function(l) {
        var lw;
        chart.append("text")
            .attr({
                class: "y axis",
                transform: "translate(0, " + -bar_height + ")"
            })
            .text(l)
            .each(function() {
                lw = this.getBBox().width;
            })
            .remove().remove();
        return lw;
    });

    // update
    update_timeline();

    // re-order data by document name, for CSS background color alternation
    var ndata = [];
    y_labels.forEach(function(l) {
        ndata = ndata.concat(data.filter(function(d) { return d.name === l; }));
    });
    data = ndata;

    // enter data (skip the last pseudo entry)
    var bar = chart.selectAll("g").data(data.slice(0, -1));
    var g = bar.enter()
        .append("g")
            .attr({
                class: "bar",
                transform: offset
            });
    g.append("a")
        .attr("xlink:href", function(d) { return d.url; })
        .append("rect")
            .attr({
                height: bar_height,
                width: bar_width,
                mask: function(d, i) {
                    // apply gradient if the document is a draft and expired
                    if (d.name.match(/^draft-/) &&
                        bar_width(d, i) >= x_scale(expiration_date(d)) -
                                           x_scale(d.published)) {
                        return "url(#fade)";
                    }
                }
            });

    g.append("text")
        .attr({
            x: 3,
            y: bar_height / 2
        })
        .text(function(d) { return d.rev; });

    var y_scale = d3.scale.ordinal()
        .domain(y_labels)
        .rangePoints([0, max(bar_y) + bar_height]);

    var y_axis = d3.svg.axis()
        .scale(y_scale)
        .tickValues(y_labels)
        .orient("left");

    chart.append("g").attr({
        class: "x axis",
        transform: "translate(0, " + (max(bar_y) + bar_height) + ")"
    });
    update_x_axis();

    chart.append("g")
        .attr({
            class: "y axis",
            transform: "translate(10, " + bar_height / 2 + ")"
        })
        .call(y_axis)
        .selectAll("text")
        .style("text-anchor", "start");

    // set height of timeline
    var x_label_height;
    d3.select(".x.axis").each(function() {
        x_label_height = this.getBBox().height;
    });
    chart.attr("height", max(bar_y) + bar_height + x_label_height);
}


d3.json("doc.json", function(error, json) {
    if (error) { return; }
    data = json.rev_history;

    if (data.length) {
        // make js dates out of publication dates
        data.forEach(function(d) { d.published = new Date(d.published); });

        // add pseudo entry when the ID will expire
        data.push({
            name: "",
            rev: "",
            published: expiration_date(data[data.length - 1])
        });
        draw_timeline();
    }
});


$(window).on({
    resize: function() {
        update_timeline();
    }
});
