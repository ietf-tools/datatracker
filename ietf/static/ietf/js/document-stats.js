$(document).ready(function () {
    if (window.chartConf) {
        window.chartConf.credits = {
            enabled: false
        };
        window.chartConf.exporting = {
            fallbackToExportServer: false
        };

        if (!window.chartConf.legend)
            window.chartConf.legend = {
                enabled: false
            };
        
        var chart = Highcharts.chart('chart', window.chartConf);
    }

    $(".popover-details").each(function () {
        var stdNameRegExp = new RegExp("^(rfc|bcp|fyi|std)[0-9]+$", 'i');
        var draftRegExp = new RegExp("^draft-", 'i');

        var html = [];t
        $.each(($(this).data("elements") || "").split("|"), function (i, element) {
            if (!$.trim(element))
                return;

            if (draftRegExp.test(element) || stdNameRegExp.test(element)) {
                var displayName = element;

                if (stdNameRegExp.test(element))
                    displayName = element.slice(0, 3).toUpperCase() + " " + element.slice(3);

                html.push('<div class="docname"><a href="/doc/' + element + '/">' + displayName + '</a></div>');
            }
            else {
                html.push('<div>' + element + '</div>');
            }
        });

        if ($(this).data("sliced"))
            html.push('<div class="text-center">&hellip;</div>');

        $(this).popover({
            trigger: "focus",
            template: '<div class="popover" role="tooltip"><div class="arrow"></div><h3 class="popover-title"></h3><div class="popover-content"></div></div>',
            content: html.join(""),
            html: true
        }).on("click", function (e) {
            e.preventDefault();
        });
    });
});
