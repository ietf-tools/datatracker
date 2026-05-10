// Copyright The IETF Trust 2026, All Rights Reserved
import Chart from 'chart.js/auto'
import zoomPlugin from 'chartjs-plugin-zoom'

document.addEventListener('DOMContentLoaded', () => {
    Chart.register(zoomPlugin) // enable the zoom plugin
    const hidden = new Set();   // track suppressed categories

    // ── Safely parse JSON data injected from Django view ──
    const chartData = JSON.parse(document.getElementById('chart_data').textContent) ;

    function refreshChart() {
        // On first call, snapshot the original data onto the chart instance itself
        if (!chart._originalData) {
            chart._originalData = {
                labels: [...chart.data.labels],
                values: [...chart.data.datasets[0].data],
                colors: Array.isArray(chart.data.datasets[0].backgroundColor)
                    ? [...chart.data.datasets[0].backgroundColor]
                    : chart.data.labels.map(() => chart.data.datasets[0].backgroundColor),
            };
        }

        const original = chart._originalData;
        const labels = [], values = [], colors = [];

        original.labels.forEach((lbl, i) => {
            if (!hidden.has(lbl)) {
                labels.push(lbl);
                values.push(original.values[i]);
                colors.push(original.colors[i]);
            }
        });

        chart.data.labels = labels;
        chart.data.datasets[0].data = values;
        chart.data.datasets[0].backgroundColor = colors;
        chart.update();
    }

    function displayChart (id, data) {
        const ctx = document.getElementById(id).getContext('2d') ;
        chart = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                indexAxis: 'y',
                onClick: (event, elements) => {
                    console.log('Clicked elements:', elements);
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const label = chart.data.labels[idx];
                        hidden.add(label);
                        refreshChart();
                    }
                },
                responsive: true,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Number of authors',
                        },
                    },
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0,0,0,0.8)',
                        titleFont: { size: 14 },
                        bodyFont: { size: 13 },
                        callbacks: {
                            title: function(items) {
                                return `${items[0].label}`;
                            },
                            label: function(context) {
                                return `${context.formattedValue} authors`;
                            }
                        }
                    },
                    zoom: {
                        zoom: {
                            wheel: { 
                                enabled: true,
                                modifierKey: 'alt'   // Alt + scroll wheel to zoom
                            },      // scroll to zoom
                            pinch: { 
                                enabled: true 

                            },      // pinch on mobile
                            drag: {                        // drag to select range 
                                enabled: true,
                                modifierKey: 'alt'
                            },
                            mode: 'xy',                     // zoom X-axis and Y-axis
                        },
                        pan: {
                            enabled: true,
                            modifierKey: 'alt',
                            mode: 'xy',                     // pan X-axis and Y-axis
                        },
                    },
                }
            }
        }) ;
        return chart;
    }

    const documentsChart = displayChart('documentsChart', chartData) ;

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            documentsChart.resetZoom()
        }
    })
    document.getElementById('resetButton').addEventListener('click', () => {
        documentsChart.resetZoom()
    })
})
