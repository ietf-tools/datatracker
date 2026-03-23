(function () {
    var raw = document.getElementById('attendees-chart-data');
    if (!raw) return;
    var chartData = JSON.parse(raw.textContent);
    var chart = null;
    var currentBreakdown = 'type';

    // Override the global transparent background set by highcharts.js so the
    // export menu and fullscreen view use the page background color.
    var container = document.getElementById('attendees-pie-chart');
    var bodyBg = getComputedStyle(document.body).backgroundColor;
    container.style.setProperty('--highcharts-background-color', bodyBg);

    function renderChart(breakdown) {
        var seriesData = chartData[breakdown].map(function (item) {
            return { name: item[0], y: item[1] };
        });
        if (chart) chart.destroy();
        chart = Highcharts.chart(container, {
            chart: { type: 'pie', height: 400 },
            title: { text: null },
            tooltip: { pointFormat: '{point.name}: <b>{point.y}</b> ({point.percentage:.1f}%)' },
            plotOptions: {
                pie: {
                    dataLabels: {
                        enabled: true,
                        format: '<b>{point.name}</b><br>{point.y} ({point.percentage:.1f}%)',
                    },
                    showInLegend: false,
                }
            },
            series: [{ name: 'Attendees', data: seriesData }],
        });
    }

    var modal = document.getElementById('attendees-chart-modal');

    // Render (or re-render) the chart each time the modal becomes fully visible,
    // so Highcharts can measure the container dimensions correctly.
    modal.addEventListener('shown.bs.modal', function () {
        renderChart(currentBreakdown);
    });

    // Release the chart when the modal closes to avoid stale renders.
    modal.addEventListener('hidden.bs.modal', function () {
        if (chart) {
            chart.destroy();
            chart = null;
        }
    });

    document.querySelectorAll('[name="attendees-breakdown"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
            currentBreakdown = this.value;
            renderChart(currentBreakdown);
        });
    });
})();
