// Copyright The IETF Trust 2026, All Rights Reserved
import Chart from 'chart.js/auto'
import zoomPlugin from 'chartjs-plugin-zoom'

document.addEventListener('DOMContentLoaded', () => {
    Chart.register(zoomPlugin) // enable the zoom plugin

    // ── Safely parse JSON data injected from Django view ──
    const chartData = JSON.parse(document.getElementById('chart_data').textContent) ;
    const objects = JSON.parse(document.getElementById('objects').textContent) ;
    const stackedLines = false ;
    // Monthly timelines use "YYYY-MM" labels, yearly ones use plain years
    const monthly = chartData.labels.length > 0 && String(chartData.labels[0]).includes('-') ;

    function displayChart (id, data) {
        const ctx = document.getElementById(id).getContext('2d') ;
        return new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                scales: {
                    y: {
                        stacked: stackedLines,
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Year',
                        },
                        ticks: monthly ? {
                            // Only label the year (on its first month) to save space
                            autoSkip: false,
                            maxRotation: 0,
                            callback: function(value) {
                                const label = String(this.getLabelForValue(value)) ;
                                return label.endsWith('-01') ? label.slice(0, 4) : '' ;
                            },
                        } : {},
                    },
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: { size: 12 },
                        },
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
                                return ` ${context.dataset.label}: ${context.parsed.y} ${objects}`;
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
                            modifierKey: 'shift',
                            mode: 'xy',                     // pan X-axis and Y-axis
                        },
                    },
                }
            }
        })
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
