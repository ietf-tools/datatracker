const style = getComputedStyle(document.body);
const font_size = parseFloat(style.fontSize);
const line_height = font_size + 2;
const font_family = style.getPropertyValue("--bs-body-font-family");
const font = `${font_size}px ${font_family}`;

const link_color = {
    refinfo: style.getPropertyValue("--bs-success"),
    refnorm: style.getPropertyValue("--bs-primary"),
    replaces: style.getPropertyValue("--bs-warning"),
    refunk: style.getPropertyValue("--bs-info"),
    downref: style.getPropertyValue("--bs-danger")
};

const ref_type = {
    refinfo: "has an Informative reference to",
    refnorm: "has a Normative reference to",
    replaces: "replaces",
    refunk: "has an Unknown type of reference to",
    downref: "has a downward reference (DOWNREF) to"
};

// code partially adapted from
// https://observablehq.com/@mbostock/fit-text-to-circle

function lines(text) {
    let line;
    let line_width_0 = Infinity;
    const lines = [];
    var words = text.trim()
        .split(/-/g)
        .map((x, i, a) => i < a.length - 1 ? x + "-" : x);
    if (words.length == 1) {
        words = text.trim()
            .split(/rfc/g)
            .map((x, i, a) => i < a.length - 1 ? x + "RFC" : x);
    }
    const target_width = Math.sqrt(measure_width(text.trim()) *
        line_height);
    for (let i = 0, n = words.length; i < n; ++i) {
        let line_text = (line ? line.text : "") + words[i];
        let line_width = measure_width(line_text);
        if ((line_width_0 + line_width) / 2 < target_width) {
            line.width = line_width_0 = line_width;
            line.text = line_text;
        } else {
            line_width_0 = measure_width(words[i]);
            line = { width: line_width_0, text: words[i] };
            lines.push(line);
        }
    }
    return lines;
}

function measure_width(text) {
    const context = document.createElement("canvas")
        .getContext("2d");
    context.font = font;
    return context.measureText(text)
        .width;
}

function text_radius(lines) {
    let radius = 0;
    for (let i = 0, n = lines.length; i < n; ++i) {
        const dy = (Math.abs(i - n / 2) + 0.5) * line_height;
        const dx = lines[i].width / 2;
        radius = Math.max(radius, Math.sqrt(dx ** 2 + dy ** 2));
    }
    return radius;
}

// Fill modal with content from link href
$("#deps-modal")
    .on("show.bs.modal", function (e) {
        $(e.relatedTarget)
            .one("focus", function () {
                $(this)
                    .trigger("blur");
            });
        const link = $(e.relatedTarget)
            .data("href");
        const group = $(e.relatedTarget)
            .data("group");
        const target = $(this)
            .find(".modal-body");

        target.html(
            `
            <div class="d-flex justify-content-center">
                <div class="spinner-border m-5" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `
        );

        if (link && target) {
            d3.json(link)
                .then((data) => {
                    // console.log(data);
                    target.html('<svg class="w-100 h-100"></svg>');
                    const width = 1000;
                    const height = 1000;

                    const zoom = d3.zoom()
                        .scaleExtent([1 / 8, 8])
                        .on("zoom", zoomed);

                    const svg = d3.select(".modal-body svg")
                        .style("font", font)
                        .attr("text-anchor", "middle")
                        .attr("dominant-baseline", "central")
                        .attr("viewBox",
                            [-width / 2, -height / 2, width, height])
                        .call(zoom);

                    svg.append("defs")
                        .selectAll("marker")
                        .data(new Set(data.links.map(d => d.rel)))
                        .join("marker")
                        .attr("id", d => `marker-${d}`)
                        .attr("viewBox", "0 -5 10 10")
                        .attr("refX", 9)
                        .attr("markerWidth", 4)
                        .attr("markerHeight", 4)
                        .attr("stroke-width", 0)
                        .attr("orient", "auto")
                        .attr("fill", d => link_color[d])
                        .append("path")
                        .attr("d", "M0,-5L10,0L0,5");

                    const link = svg.append("g")
                        .attr("fill", "none")
                        .attr("stroke-width", 5)
                        .selectAll("path")
                        .data(data.links)
                        .join("path")
                        .attr("title", d =>
                            `${d.source} ${ref_type[d.rel]} ${d.target}`
                        )
                        .attr("marker-end", d =>
                            `url(#marker-${d.rel})`)
                        .attr("stroke", d => link_color[d.rel])
                        .attr("class", d => d.rel);

                    const node = svg.append("g")
                        .selectAll("g")
                        .data(data.nodes)
                        .join("g");

                    var max_r = 0;
                    const a = node.append("a")
                        .attr("href", d => d.url)
                        .attr("title", d => {
                            var type = ["replaced", "dead",
                                    "expired"
                                ].filter(x => d[x])
                                .join(" ");
                            if (type) {
                                type += " ";
                            }
                            if (d.level) {
                                type += `${d.level} `
                            }
                            if (d.group) {
                                type +=
                                    `group document in ${d.group.toUpperCase()}`;
                            } else {
                                type += "individual document";
                            }
                            const name = d.id.startsWith("rfc") ?
                                d
                                .id.toUpperCase() : d.id;
                            return `${name} is a${"aeiou".includes(type[0].toLowerCase()) ? "n" : ""} ${type}`
                        });

                    a
                        .append("text")
                        .attr("fill", "black")
                        .each(d => {
                            d.lines = lines(d.id);
                            d.r = text_radius(d.lines);
                            max_r = Math.max(d.r, max_r);
                        })
                        .selectAll("tspan")
                        .data(d => d.lines)
                        .join("tspan")
                        .attr("x", 0)
                        .attr("y", (d, i, x) => ((i - x.length / 2) +
                            0.5) * line_height)
                        .text(d => d.text);

                    a
                        .append("circle")
                        .attr("r", d => d.r)
                        .attr("stroke", "black")
                        .lower()
                        .attr("fill", d => {
                            if (d.replaced) {
                                return style.getPropertyValue(
                                    "--bs-teal");
                            }
                            if (d.dead) {
                                return style.getPropertyValue(
                                    "--bs-danger");
                            }
                            if (d.expired) {
                                return style.getPropertyValue(
                                    "--bs-gray-300");
                            }
                            if (d.group == group) {
                                return style.getPropertyValue(
                                    "--bs-warning");
                            }
                            return "white";
                        })
                        .attr("stroke-width", d => {
                            if (!d.group) { return 1; }
                            return 4; // adopted in this or other group
                        })
                        .attr("stroke-dasharray", d => {
                            if (d.group) { return 0; }
                            return 4;
                        });

                    function ticked() {
                        // don't animate each tick
                        for (let i = 0; i < 3; i++) {
                            simulation.tick();
                        }

                        // code for straight links:
                        // link.attr("d", function (d) {
                        //     const dx = d.target.x - d.source.x;
                        //     const dy = d.target.y - d.source.y;

                        //     const path_len = Math.sqrt((dx * dx) +
                        //         (dy * dy));

                        //     const offx = (dx * d.target.r) /
                        //         path_len;
                        //     const offy = (dy * d.target.r) /
                        //         path_len;
                        //     return `
                        //         M${d.source.x},${d.source.y}
                        //         L${d.target.x - offx},${d.target.y - offy}
                        //     `;
                        // });

                        // code for arced links:
                        link.attr("d", d => {
                            const r = Math.hypot(d.target.x -
                                d
                                .source.x, d
                                .target.y - d.source.y);
                            return `
                              M${d.source.x},${d.source.y}
                              A${r},${r} 0 0,1 ${d.target.x},${d.target.y}
                          `;
                        });
                        // TODO: figure out how to combine this with above
                        link.attr("d", function (d) {
                            const pl = this.getTotalLength();
                            const r = (d.target.r);
                            const m = this.getPointAtLength(
                                pl -
                                r);
                            const dx = m.x - d.source.x;
                            const dy = m.y - d.source.y;
                            const dr = Math.sqrt(dx * dx +
                                dy *
                                dy);
                            return `
                              M${d.source.x},${d.source.y}
                              A${dr},${dr} 0 0,1 ${m.x},${m.y}
                          `;
                        });

                        node.selectAll("circle, text")
                            .attr("transform", d =>
                                `translate(${d.x}, ${d.y})`)

                        // auto pan and zoom during simulation
                        const bbox = svg.node()
                            .getBBox();
                        const max_stroke = 4;
                        svg.attr("viewBox",
                            [bbox.x - max_stroke,
                                bbox.y - max_stroke,
                                bbox.width + 2 * max_stroke,
                                bbox.height + 2 * max_stroke
                            ]
                        );
                    }

                    function zoomed({ transform }) {
                        link.attr("transform", transform);
                        node.attr("transform", transform);
                    }

                    $('svg [title][title!=""]')
                        .tooltip();

                    const simulation = d3
                        .forceSimulation()
                        .nodes(data.nodes)
                        .force("link", d3.forceLink(data.links)
                            .id(d => d.id)
                            .distance(0)
                            // .strength(1)
                        )
                        .force("charge", d3.forceManyBody()
                            .strength(-5 * max_r))
                        .force("collision", d3.forceCollide(1.25 *
                            max_r))
                        .force("x", d3.forceX())
                        .force("y", d3.forceY())
                        .on("tick", ticked)
                        .on("end", function () {
                            $("#download-svg")
                                .removeClass("disabled")
                                .html(
                                    '<i class="bi bi-download"></i> Download'
                                );
                        });
                });
        }
    });

$("#download-svg")
    .on("click", function () {
        const html = $(".modal-body svg")
            .attr("xmlns", "http://www.w3.org/2000/svg")
            .attr("version", "1.1")
            .parent()
            .html();

        const group = $(this)
            .data("group");

        $(this)
            .attr("download", `${group}.svg`)
            .attr("href", "data:image/svg+xml;base64,\n" + btoa(unescape(
                encodeURIComponent(html))))
    });
