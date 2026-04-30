// Copyright The IETF Trust 2026, All Rights Reserved
document.addEventListener('DOMContentLoaded', () => {
    // Need to use autocolors plug-in else all slices are gray...
    const autocolors = window['chartjs-plugin-autocolors']
    Chart.register(autocolors)
    // ── Safely parse JSON data injected from Django view ──
    const totalChartData = JSON.parse(document.getElementById('total-chart-data').textContent)
    const inPersonChartData = JSON.parse(document.getElementById('in-person-chart-data').textContent)

    function displayChart (id, data) {
        const ctx = document.getElementById(id).getContext('2d')
        new Chart(ctx, {
            type: 'pie',   // Change to 'doughnut' for a donut chart
            data: data,
            options: {
                responsive: true,
                plugins: {
                    autocolors: {
                        mode: 'data' // Required for Pie charts to color individual slices
                    },
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            font: { size: 13 },
                            color: '#475569',
                            generateLabels: function (chart) {
                                const dataset = chart.data.datasets[0]
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label}: ${dataset.data[i]}`,
                                    fillStyle: dataset.backgroundColor[i],
                                    hidden: false,
                                    index: i,
                                }))
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const label = context.label || ''
                                const value = context.raw
                                const total = context.dataset.data.reduce((a, b) => a + b, 0)
                                const percentage = ((value / total) * 100).toFixed(1)

                                return `${label}: ${value} (${percentage}%)`
                            }
                        }
                    }
                }
            }
        })
    }

    displayChart('totalRegistrationChart', totalChartData)
    displayChart('inPersonRegistrationChart', inPersonChartData)
})
