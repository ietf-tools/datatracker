const style = getComputedStyle(document.body);
const font_size = parseFloat(style.fontSize);
const line_height = font_size + 2;
const font_family = style.getPropertyValue("--bs-body-font-family");
const font = `${font_size}px ${font_family}`;

const green = style.getPropertyValue("--bs-green");
const blue = style.getPropertyValue("--bs-blue");
const orange = style.getPropertyValue("--bs-orange");
const cyan = style.getPropertyValue("--bs-cyan");
const yellow = style.getPropertyValue("--bs-yellow");
const red = style.getPropertyValue("--bs-red");
const teal = style.getPropertyValue("--bs-teal");
const white = style.getPropertyValue("--bs-white");
const black = style.getPropertyValue("--bs-dark");
const gray400 = style.getPropertyValue("--bs-gray-400");

const link_color = {
    refinfo: green,
    refnorm: blue,
    replaces: orange,
    refunk: cyan,
    refold: yellow,
    downref: red
};

const ref_type = {
    refinfo: "has an Informative reference to",
    refnorm: "has a Normative reference to",
    replaces: "replaces",
    refunk: "has an Unknown type of reference to",
    refold: "has an Undefined type of reference to",
    downref: "has a Downward reference (DOWNREF) to"
};

// code partially adapted from
// https://observablehq.com/@mbostock/fit-text-to-circle

function lines(text) {
    let line;
    let line_width_0 = Infinity;
    const lines = [];
    let sep = "-";
    let words = text.trim()
        .split(/-/g);
    if (words.length == 1) {
        words = text.trim()
            .split(/\s/g);
        sep = " ";
    }
    words = words.map((x, i, a) => i < a.length - 1 ? x + sep : x);
    if (words.length == 1) {
        words = text.trim()
            .split(/rfc/g)
            .map((x, i, a) => i < a.length - 1 ? x + "RFC" : x);
    }
    const target_width = Math.sqrt(measure_width(text.trim()) * line_height);
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

function stroke(d) {
    if (d.level == "Informational" ||
        d.level == "Experimental" || d.level == "") {
        return 1;
    }
    if (d.level == "Proposed Standard") {
        return 4;
    }
    if (d.level == "Best Current Practice") {
        return 8;
    }
    // all others (draft/full standards)
    return 10;
}

function draw_graph(data, group) {
    // console.log(data);
    // let el = $.parseHTML('<svg class="w-100 h-100"></svg>');

    const zoom = d3.zoom()
        .scaleExtent([1 / 32, 32])
        .on("zoom", zoomed);

    const width = 1000;
    const height = 1000;

    const svg = d3.select($.parseHTML('<svg class="w-100 h-100"></svg>')[0])
        .style("font", font)
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .attr("viewBox", [-width / 2, -height / 2, width, height])
        .call(zoom);

    svg.append("defs")
        .selectAll("marker")
        .data(new Set(data.links.map(d => d.rel)))
        .join("marker")
        .attr("id", d => `marker-${d}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 7.85)
        .attr("markerWidth", 4)
        .attr("markerHeight", 4)
        .attr("stroke-width", 0.2)
        .attr("stroke", black)
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
        .attr("title", d => `${d.source} ${ref_type[d.rel]} ${d.target}`)
        .attr("marker-end", d => `url(#marker-${d.rel})`)
        .attr("stroke", d => link_color[d.rel])
        .attr("class", d => d.rel);

    const node = svg.append("g")
        .selectAll("g")
        .data(data.nodes)
        .join("g");

    let max_r = 0;
    const a = node.append("a")
        .attr("href", d => d.url)
        .attr("title", d => {
            let type = ["replaced", "dead", "expired"].filter(x => d[x])
                .join(" ");
            if (type) {
                type += " ";
            }
            if (d.level) {
                type += `${d.level} `
            }
            if (d.group != undefined && d.group != "none" && d.group != "") {
                const word = d.rfc ? "from" : "in";
                type += `group document ${word} ${d.group.toUpperCase()}`;
            } else {
                type += "individual document";
            }
            const name = d.rfc ? d.id.toUpperCase() : d.id;
            return `${name} is a${"aeiou".includes(type[0].toLowerCase()) ? "n" : ""} ${type}`
        });

    a
        .append("text")
        .attr("fill", d => d.rfc || d.replaced ? white : black)
        .each(d => {
            d.lines = lines(d.id);
            d.r = text_radius(d.lines);
            max_r = Math.max(d.r, max_r);
        })
        .selectAll("tspan")
        .data(d => d.lines)
        .join("tspan")
        .attr("x", 0)
        .attr("y", (d, i, x) => ((i - x.length / 2) + 0.5) * line_height)
        .text(d => d.text);

    a
        .append("circle")
        .attr("stroke", black)
        .lower()
        .attr("fill", d => {
            if (d.rfc) {
                return green;
            }
            if (d.replaced) {
                return orange;
            }
            if (d.dead) {
                return red;
            }
            if (d.expired) {
                return gray400;
            }
            if (d["post-wg"]) {
                return teal;
            }
            if (d.group == group || d.group == "this group") {
                return yellow;
            }
            if (d.group == "") {
                return white;
            }
            return cyan;
        })
        .each(d => d.stroke = stroke(d))
        .attr("r", d => d.r + d.stroke / 2)
        .attr("stroke-width", d => d.stroke)
        .attr("stroke-dasharray", d => {
            if (d.group != "" || d.rfc) { return 0; }
            return 4;
        });

    const adjust = stroke("something") / 2;

    function ticked() {
        // don't animate each tick
        for (let i = 0; i < 3; i++) {
            this.tick();
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
            const r = Math.hypot(d.target.x - d
                .source.x, d.target.y - d.source
                .y);
            return `M${d.source.x},${d.source.y} A${r},${r} 0 0,1 ${d.target.x},${d.target.y}`;
        });
        // TODO: figure out how to combine this with above
        link.attr("d", function (d) {
            const pl = this.getTotalLength();
            const start = this.getPointAtLength(
                d.source.r + d.source.stroke
            );
            const end = this.getPointAtLength(
                pl - d.target.r - d.target.stroke
            );
            const r = Math.hypot(
                d.target.x - d.source.x, d.target.y - d.source.y
            );
            return `M${start.x},${start.y} A${r},${r} 0 0,1 ${end.x},${end.y}`;
        });

        node.selectAll("circle, text")
            .attr("transform", d => `translate(${d.x}, ${d.y})`)

        // auto pan and zoom during simulation
        const bbox = svg.node()
            .getBBox();
        svg.attr("viewBox",
            [
                bbox.x - adjust, bbox.y - adjust,
                bbox.width + 2 * adjust, bbox.height + 2 * adjust
            ]
        );
    }

    function zoomed({ transform }) {
        link.attr("transform", transform);
        node.attr("transform", transform);
    }

    return [svg.node(), d3
        .forceSimulation()
        .nodes(data.nodes)
        .force("link", d3.forceLink(data.links)
            .id(d => d.id)
            .distance(0)
            // .strength(1)
        )
        .force("charge", d3.forceManyBody()
            .strength(-max_r))
        .force("collision", d3.forceCollide(1.25 * max_r))
        .force("x", d3.forceX())
        .force("y", d3.forceY())
        .stop()
        .on("tick", ticked)
        .on("end", function () {
            $("#download-svg")
                .removeClass("disabled")
                .html('<i class="bi bi-download"></i> Download');
        })
    ];

    // // See https://github.com/d3/d3-force/blob/main/README.md#simulation_tick
    // for (let i = 0, n = Math.ceil(Math.log(simulation.alphaMin()) /
    //         Math.log(1 - simulation.alphaDecay())); i <
    //     n; ++i) {
    //     simulation.tick();
    // }
    // ticked();

}

// Fill modal with content from link href
$("#deps-modal")
    .on("shown.bs.modal", function (e) {
        $(e.relatedTarget)
            .one("focus", function () {
                $(this)
                    .trigger("blur");
            });

        const link = $(e.relatedTarget)
            .data("href");
        const group = $(e.relatedTarget)
            .data("group");

        $("#download-svg")
            .addClass("disabled");

        $("#legend")
            .prop("disabled", true)
            .prop("checked", false);

        if (link && $(this)
            .find(".modal-body")) {
            const controller = new AbortController();
            const { signal } = controller;

            const legend = {
                nodes: [{
                    id: "Individual submission",
                    level: "Informational",
                    group: ""
                }, {
                    id: "Replaced",
                    level: "Experimental",
                    replaced: true
                }, {
                    id: "IESG or RFC queue",
                    level: "Proposed Standard",
                    "post-wg": true
                }, {
                    id: "Product of other group",
                    level: "Best Current Practice",
                    group: "other group"
                }, {
                    id: "Expired",
                    level: "Informational",
                    group: "this group",
                    expired: true
                }, {
                    id: "Product of this group",
                    level: "Proposed Standard",
                    group: "this group"
                }, {
                    id: "RFC published",
                    level: "Draft Standard",
                    group: "other group",
                    rfc: true
                }],
                links: [{
                    source: "Individual submission",
                    target: "Replaced",
                    rel: "replaces"
                }, {
                    source: "Individual submission",
                    target: "IESG or RFC queue",
                    rel: "refnorm"
                }, {
                    source: "Expired",
                    target: "RFC published",
                    rel: "refunk"
                }, {
                    source: "Product of other group",
                    target: "IESG or RFC queue",
                    rel: "refinfo"
                }, {
                    source: "Product of this group",
                    target: "Product of other group",
                    rel: "refold"
                }, {
                    source: "Product of this group",
                    target: "Expired",
                    rel: "downref"
                }]
            };
            let [leg_el, leg_sim] = draw_graph(legend, "this group");

            $("#legend-tab")
                .on("show.bs.tab", function () {
                    $(".modal-body")
                        .children()
                        .replaceWith(leg_el);
                    leg_sim.restart();
                })
                .on("hide.bs.tab", function () {
                    leg_sim.stop();
                });

            d3.json(link, { signal })
                .catch(e => {})
                .then((data) => {
                    // the user may have closed the modal in the meantime
                    if (!$("#deps-modal")
                        .hasClass("show")) {
                        return;
                    }

                    let [dep_el, dep_sim] = draw_graph(data, group);
                    $("#dep-tab")
                        .on("show.bs.tab", function () {
                            $(".modal-body")
                                .children()
                                .replaceWith(dep_el);
                            dep_sim.restart();
                        })
                        .on("hide.bs.tab", function () {
                            dep_sim.stop();
                        });

                    // shown by default
                    $(".modal-body")
                        .children()
                        .replaceWith(dep_el);
                    dep_sim.restart();

                    $('svg [title]:not([title=""])')
                        .tooltip();

                    $("#legend")
                        .prop("disabled", false)
                        .on("click", function () {
                            if (this.checked) {
                                $(".modal-body")
                                    .children()
                                    .replaceWith(leg_el);
                                leg_sim.restart();
                            } else {
                                $(".modal-body")
                                    .children()
                                    .replaceWith(dep_el);
                                dep_sim.restart();
                            }

                            $('svg [title]:not([title=""])')
                                .tooltip();
                        });

                    $(this)
                        .on("hide.bs.modal", function (e) {
                            controller.abort();
                            if (leg_sim) {
                                leg_sim.stop();
                            }
                            if (dep_sim) {
                                dep_sim.stop();
                            }
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
            .attr("href", "data:image/svg+xml;base64,\n" + btoa(
                unescape(
                    encodeURIComponent(html))))
    });
