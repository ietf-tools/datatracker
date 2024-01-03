$(document)
    .ready(function () {
        var form = $("form.my-3");

        // review submission selection
        form.find("[name=submission_method]")
            .on("click change", function () {
                var val = form.find("[name=submission_method]:checked")
                    .val();

                var shouldBeVisible = {
                    upload: ['[name="file"]'],
                    enter: ['[name="content"]']
                };

                for (var v in shouldBeVisible) {
                    for (var i in shouldBeVisible[v]) {
                        var selector = shouldBeVisible[v][i];
                        var row = form.find(selector).parent();
                        if ($.inArray(selector, shouldBeVisible[val]) != -1)
                            row.show();
                        else
                            row.hide();
                    }
                }
            })
            .trigger("change");
    });