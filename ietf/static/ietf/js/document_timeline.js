"use strict";

var data;
var x_scale;
var bar_y;
var bar_height;
var y_label_width;
var x_axis;
var width;

function offset(d, i) {
    // increase the y offset if the document name changed in this revision
    if (i > 0 && data[i - 1].name !== d.name || d.rev.match("^rfc\d+$"))
        bar_y += bar_height;
    return "translate(" + x_scale(d.published) + ", " + bar_y + ")";
}


function bar_width(d, i) {
    if (i < data.length - 1)
        return x_scale(data[i + 1].published) - x_scale(d.published);
}


function scale_x() {
    width = $("#timeline").width();

    // scale data to width of container minus y label width
    x_scale = d3.time.scale().domain([
        d3.min(data, function(d) { return d.published; }),
        d3.max(data, function(d) { return d.published; })
    ]).range([y_label_width, width]);

    x_axis = d3.svg.axis()
        .scale(x_scale)
        // don't add a tick for the pseudo entry
        .tickValues(data.slice(0, -1).map(function(d) { return d.published; }))
        .tickFormat(d3.time.format("%b %Y"))
        .orient("bottom");
}


function update_x_axis() {
    d3.select("#timeline svg .x.axis").call(x_axis)
        .selectAll("text")
        .style("text-anchor", "end")
        .attr("transform", "translate(-14, 2) rotate(-60)");
}


function update_timeline() {
    bar_y = 0;
    scale_x();
    var chart = d3.select("#timeline svg").attr("width", width);
    var bar = chart.selectAll("g").data(data);
    bar.attr("transform", offset).select("rect").attr("width", bar_width);
    update_x_axis();
}


function draw_timeline() {
    bar_height = parseFloat($("body").css("line-height"));

    var div = $("#timeline");
    if (div.is(":empty"))
        div.append("<svg></svg>");
    var chart = d3.select("#timeline svg").attr("width", width);

    var gradient = chart.append("defs")
        .append("linearGradient")
            .attr("id", "gradient");
    gradient.append("stop")
        .attr({
            class: "gradient left",
            offset: 0
        });
    gradient.append("stop")
        .attr({
            class: "gradient right",
            offset: 1
        });

    var y_labels = data
        .map(function(elem) { return elem.name; })
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

    // enter
    var bar = chart.selectAll("g").data(data);
    var g = bar.enter()
        .append("g")
            .attr({
                class: "bar",
                transform: offset
            });
    g.append("rect")
        .attr({
            height: bar_height,
            width: bar_width
        });
    g.append("text")
        .attr({
            x: 3,
            y: bar_height/2
        })
        .text(function(d) { return d.rev; });

    // since the gradient is defined inside the SVG, we need to set the CSS
    // style here, so the relative URL works
    $("#timeline .bar:nth-last-child(2) rect").css("fill", "url(#gradient)");

    var y_scale = d3.scale.ordinal()
        .domain(y_labels)
        .rangePoints([0, bar_y]);

    var y_axis = d3.svg.axis()
        .scale(y_scale)
        .tickValues(y_labels)
        .orient("left");

    chart.append("g").attr({
        class: "x axis",
        transform: "translate(0, " + bar_y + ")"
    });
    update_x_axis();

    chart.append("g")
        .attr({
            class: "y axis",
            transform: "translate(10, " + bar_height/2 + ")"
        })
        .call(y_axis)
        .selectAll("text")
        .style("text-anchor", "start");

    // set height of timeline
    var x_label_height;
    d3.select(".x.axis").each(function() {
        x_label_height = this.getBBox().height;
    });
    chart.attr("height", bar_y + x_label_height);
}


d3.json("doc.json", function(error, json) {
    if (error) return;
    data = json["rev_history"];

    if (data.length) {
        // make js dates out of publication dates
        data.forEach(function(d) { d.published = new Date(d.published); });

        // add pseudo entry 185 days after last rev (when the ID will expire)
        var pseudo = new Date(data[data.length - 1].published.getTime() +
                              1000*60*60*24*185);
        data.push({ name: "", rev: "", published: pseudo});
        draw_timeline();
    }
});


$(window).on({
    resize: function() {
        update_timeline();
    }
});
