import Highcharts from "highcharts";

import Highcharts_Exporting from "highcharts/modules/exporting";
import Highcharts_Offline_Exporting from "highcharts/modules/offline-exporting";
import Highcharts_Export_Data from "highcharts/modules/export-data";
import Highcharts_Accessibility from "highcharts/modules/accessibility";
import Highcharts_Sunburst from "highcharts/modules/sunburst";

document.documentElement.style.setProperty("--highcharts-background-color", "transparent");

Highcharts_Exporting(Highcharts);
Highcharts_Offline_Exporting(Highcharts);
Highcharts_Export_Data(Highcharts);
Highcharts_Accessibility(Highcharts);
Highcharts_Sunburst(Highcharts);

Highcharts.setOptions({
    chart: {
        height: "100%",
        styledMode: true,
    },
    credits: {
        enabled: false
    },
});

window.Highcharts = Highcharts;

window.group_stats = function (url, chart_selector) {
    $.getJSON(url, function (data) {
        $(chart_selector)
            .each(function (_, e) {
                const dataset = e.dataset.dataset;
                if (!dataset) {
                    console.log("dataset data attribute not set");
                    return;
                }
                const area = e.dataset.area;
                if (!area) {
                    console.log("area data attribute not set");
                    return;
                }

                const chart = Highcharts.chart(e, {
                    title: {
                        text: `${dataset == "docs" ? "Documents" : "Pages"} in ${area.toUpperCase()}`
                    },
                    series: [{
                        type: "sunburst",
                        data: [],
                        tooltip: {
                            pointFormatter: function () {
                                return `There ${this.value == 1 ? "is" : "are"} ${this.value} ${dataset == "docs" ? "documents" : "pages"} in ${this.name}.`;
                            }
                        },
                        dataLabels: {
                            formatter() {
                                return this.point.active ? this.point.name : `(${this.point.name})`;
                            }
                        },
                        allowDrillToNode: true,
                        cursor: 'pointer',
                        levels: [{
                            level: 1,
                            color: "transparent",
                            levelSize: {
                                value: .5
                            }
                        }, {
                            level: 2,
                            colorByPoint: true
                        }, {
                            level: 3,
                            colorVariation: {
                                key: "brightness",
                                to: 0.5
                            }
                        }]
                    }],
                });

                // limit data to area if set and (for now) drop docs
                const slice = data.filter(d => (area == "ietf" && d.grandparent == area) || d.parent == area || d.id == area)
                    .map((d) => {
                        return {
                            value: d[dataset],
                            id: d.id,
                            parent: d.parent,
                            grandparent: d.grandparent,
                            active: d.active,
                        };
                    })
                    .sort((a, b) => {
                        if (a.parent != b.parent) {
                            if (a.parent < b.parent) {
                                return -1;
                            }
                            if (a.parent > b.parent) {
                                return 1;
                            }
                        } else if (a.parent == area) {
                            if (a.id < b.id) {
                                return 1;
                            }
                            if (a.id > b.id) {
                                return -1;
                            }
                            return 0;
                        }
                        return b.value - a.value;
                    });
                chart.series[0].setData(slice);
            });
    });
}
