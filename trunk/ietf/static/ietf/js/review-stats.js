$(document).ready(function () {
    if (window.timeSeriesData && window.timeSeriesOptions) {
        var placeholder = $(".stats-time-graph");
        placeholder.height(Math.round(placeholder.width() * 1 / 3));

        $.plot(placeholder, window.timeSeriesData, window.timeSeriesOptions);
    }
});
