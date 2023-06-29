$(document)
    .ready(function () {
        var form = $("form.upload-content");
        // review submission selection
        form.find("[name=statement_submission]")
            .on("click change", function () {
                var val = form.find("[name=statement_submission]:checked")
                    .val();

                var shouldBeVisible = {
                    enter: ['[name="statement_content"]'],
                    upload: ['[name="statement_file"]'],
                };

                for (var v in shouldBeVisible) {
                    for (var i in shouldBeVisible[v]) {
                        var selector = shouldBeVisible[v][i];
                        var row = form.find(selector);
                        if (!row.is(".row"))
                            row = row.closest(".row");
                        if ($.inArray(selector, shouldBeVisible[val]) != -1)
                            row.show();
                        else
                            row.hide();
                    }
                }
            })
            .trigger("change");
    });
