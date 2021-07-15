$(document).ready(function () {
    var form = $("form.upload-content");
    // review submission selection
    form.find("[name=bofreq_submission]").on("click change", function () {
        var val = form.find("[name=bofreq_submission]:checked").val();

        var shouldBeVisible = {
            "enter": ['[name="bofreq_content"]'],
            "upload": ['[name="bofreq_file"]'],
        };

        for (var v in shouldBeVisible) {
            for (var i in shouldBeVisible[v]) {
                var selector = shouldBeVisible[v][i];
                var row = form.find(selector);
                if (!row.is(".form-group"))
                    row = row.closest(".form-group");

                if ($.inArray(selector, shouldBeVisible[val]) != -1)
                    row.show();
                else
                    row.hide();
            }
        }
    }).trigger("change");
});