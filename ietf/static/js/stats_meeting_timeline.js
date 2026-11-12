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
        const canvas = document.getElementById(id)
        if (!canvas) { return null }
        const ctx = canvas.getContext('2d')
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
                            wheel: {
                                enabled: true,
                                modifierKey: 'alt'   // Alt + scroll wheel to zoom
                            },
                            pinch: {
                                enabled: true,
                                modifierKey: 'alt'
                            },
                            drag: {                        // drag to select range
                                enabled: true,
                                modifierKey: 'alt'
                            },
                            mode: 'xy',
                        },
                        pan: {
                            enabled: true,
                            // must differ from the drag-zoom key, otherwise the plugin rejects both
                            modifierKey: 'shift',
                            mode: 'xy',
                        },
                    },
                }
            }
        })
    }

    const totalChart = displayChart('totalRegistrationChart', totalChartData)
    const inPersonChart = inPersonChartData
        ? displayChart('inPersonRegistrationChart', inPersonChartData)
        : null

    function resetZoom () {
        if (totalChart) { totalChart.resetZoom() }
        if (inPersonChart) { inPersonChart.resetZoom() }
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') { resetZoom() }
    })
    const resetButton = document.getElementById('resetButton')
    if (resetButton) { resetButton.addEventListener('click', resetZoom) }
})
