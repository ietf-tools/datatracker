// Copyright The IETF Trust 2026, All Rights Reserved
import Chart from 'chart.js/auto'
import zoomPlugin from 'chartjs-plugin-zoom'

document.addEventListener('DOMContentLoaded', () => {
    Chart.register(zoomPlugin) // enable the zoom plugin

    // ── Safely parse JSON data injected from Django view ──
    const chartData = JSON.parse(document.getElementById('chart_data').textContent) ;

    function displayChart (id, data) {
        const ctx = document.getElementById(id).getContext('2d') ;
        return new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                indexAxis: 'y',
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
                                return `${context.parsed.y} authors`;
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
