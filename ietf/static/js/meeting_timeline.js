// Copyright The IETF Trust 2026, All Rights Reserved
import Chart from 'chart.js/auto'
import zoomPlugin from 'chartjs-plugin-zoom'

document.addEventListener('DOMContentLoaded', () => {
    Chart.register(zoomPlugin) // enable the zoom plugin

    // ── Safely parse JSON data injected from Django view ──
    const totalChartData = JSON.parse(document.getElementById('total-chart-data').textContent)
    const inPersonChartData = JSON.parse(document.getElementById('in-person-chart-data').textContent)
    const statsType = JSON.parse(document.getElementById('stats-type-data').textContent)
    const stackedLines = statsType === 'total'

    function displayChart (id, data) {
        const ctx = document.getElementById(id).getContext('2d')
        return new Chart(ctx, {
            type: 'line',   // Change to 'doughnut' for a donut chart
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
                            text: 'IETF Meeting Number',
                        },
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
                            title: function (items) {
                                return `IETF Meeting ${items[0].label}`
                            },
                            label: function (context) {
                                return ` ${context.dataset.label}: ${context.parsed.y} participants`
                            }
                        }
                    },
                    zoom: {
                        zoom: {
                            wheel: { enabled: true },      // scroll to zoom
                            pinch: { enabled: true },      // pinch on mobile
                            drag: {                        // drag to select range 
                                enabled: true,
                                modifierKey: 'alt'
                            },
                            mode: 'xy',                     // zoom X-axis and Y-axis
                        },
                        pan: {
                            enabled: true,
                            mode: 'xy',                     // pan X-axis and Y-axis
                        },
                    },
                }
            }
        })
    }

    const totalChart = displayChart('totalRegistrationChart', totalChartData)
    if (inPersonChartData !== null) {
        inPersonChart = displayChart('inPersonRegistrationChart', inPersonChartData)
    }
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            totalChart.resetZoom()
            if (inPersonChart !== null) {
                inPersonChart.resetZoom()
            }
        }
    })
    document.getElementById('resetButton').addEventListener('click', () => {
        totalChart.resetZoom()
        if (inPersonChart !== null) {
            inPersonChart.resetZoom()
        }
    })
})
