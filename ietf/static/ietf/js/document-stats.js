$(document).ready(function () {
    if (window.chartConf) {
        var chart = Highcharts.chart('chart', window.chartConf);
    }

    $(".popover-docnames").each(function () {
        var stdNameRegExp = new RegExp("^(rfc|bcp|fyi|std)[0-9]+$", 'i');

        var html = [];
        $.each(($(this).data("docnames") || "").split(" "), function (i, docname) {
            if (!$.trim(docname))
                return;

            var displayName = docname;

            if (stdNameRegExp.test(docname))
                displayName = docname.slice(0, 3).toUpperCase() + " " + docname.slice(3);

            html.push('<div class="docname"><a href="/doc/' + docname + '/">' + displayName + '</a></div>');
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
