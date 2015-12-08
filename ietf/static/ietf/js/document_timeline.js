var data;

d3.json("doc.json", function(error, json) {
  if (error) return console.warn(error);
  data = json["rev_history"];

  // make js dates out of publication dates
  data.forEach(function(el) { el.published = new Date(el.published); });

  // add pseudo entry for beginning of year of first publication
  var year = data[0].published.getFullYear();
  data.unshift({ name:'', rev: '', published: new Date(year, 0, 0)});

  // add pseudo entry at end of year of last revision
  year = data[data.length - 1].published.getFullYear();
  data.push({ name:'', rev: '', published: new Date(year + 1, 0, 0)});

  draw_timeline();
});


var xscale;
var y;
var bar_height;


function offset(d, i) {
  if (i > 1 && data[i - 1].name !== d.name || d.rev.match("rfc"))
    y += bar_height;
  return "translate(" + xscale(d.published) + ", " + y + ")";
}


function bar_width(d, i) {
  if (i > 0 && i < data.length - 1)
    return xscale(data[i + 1].published) - xscale(d.published);
}


function draw_timeline() {
  var w = $("#timeline").width();
  // bar_height = parseFloat($("body").css('line-height'));
  bar_height = 30;

  xscale = d3.time.scale().domain([
    d3.min(data, function(d) { return d.published; }),
    d3.max(data, function(d) { return d.published; })
  ]).range([0, w]);

  y = 0;
  var chart = d3.select("#timeline svg").attr("width", w);
  var bar = chart.selectAll("g").data(data);

  // update
  bar
    .attr("transform", offset)
    .select("rect")
      .attr("width", bar_width);

  // enter
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

  // exit
  bar.exit().remove();

  var xaxis = d3.svg.axis()
    .scale(xscale)
    .tickValues(data.slice(1, -1).map(function(d) { return d.published; }))
    .tickFormat(d3.time.format("%b %Y"))
    .orient("bottom");

  var ids = data
    .map(function(elem) { return elem.name; })
    .filter(function(val, i, self) { return self.indexOf(val) === i; });
  ids.shift(); // first one is pseudo entry (last one, too, but filtered above)
  console.log(ids);

  var yaxis = d3.svg.axis()
    .scale(d3.scale.ordinal().domain(ids).rangePoints([0, y - bar_height]))
   .tickValues(ids)
   .orient("left");

  chart.append("g")
    .attr({
      class: "x axis",
      transform: "translate(0, " + y + ")"
    })
    .call(xaxis)
    .selectAll("text")
    .style("text-anchor", "end")
    .attr("transform", "translate(-18, 8) rotate(-90)");

  chart.append("g")
    .attr({
      class: "y axis",
      transform: "translate(10, " + bar_height/2 + ")"
    })
    .call(yaxis)
    .selectAll("text")
    .style("text-anchor", "start");

  chart.attr('height', y);
}


$(window).on({
    resize: function (event) {
      draw_timeline();
    }
});
