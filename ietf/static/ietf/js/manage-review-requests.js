$(document).ready(function () {
    var form = $("form.review-requests");

    form.find(".reviewer-action").on("click", function () {
        var row = $(this).closest("tr");

        var select = row.find(".reviewer-controls [name$=\"-reviewer\"]");
        if (!select.val()) {
            // collect reviewers already assigned in this session
            var reviewerAssigned = {};
            select.find("option").each(function () {
                if (this.value)
                    reviewerAssigned[this.value] = 0;
            });

            form.find("[name$=\"-action\"][value=\"assign\"]").each(function () {
                var v = $(this).closest("tr").find("[name$=\"-reviewer\"]").val();
                if (v)
                    reviewerAssigned[v] += 1;
            });

            // by default, the select box contains a sorted list, so
            // we should be able to select the first, unless that
            // person has already been assigned to review in this
            // session
            var found = null;
            var options = select.find("option").get();
            for (var round = 0; round < 100 && !found; ++round) {
                for (var i = 0; i < options.length && !found; ++i) {
                    var v = options[i].value;
                    if (!v)
                        continue;

                    if (reviewerAssigned[v] == round)
                        found = v;
                }
            }

            if (found)
                select.val(found);
        }

        row.find(".close-controls .undo").click();
        row.find("[name$=\"-action\"]").val("assign");
        row.find(".reviewer-action").hide();
        row.find(".reviewer-controls").show();
    });

    form.find(".reviewer-controls .undo").on("click", function () {
        var row = $(this).closest("tr");
        row.find(".reviewer-controls").hide();
        row.find(".reviewer-action").show();
        row.find("[name$=\"-action\"]").val("");
        row.find("[name$=\"-reviewer\"]").val($(this).data("initial"));
    });

    form.find(".close-action").on("click", function () {
        var row = $(this).closest("tr");
        row.find(".reviewer-controls .undo").click();
        row.find("[name$=\"-action\"]").val("close");
        row.find(".close-action").hide();
        row.find(".close-controls").show();
    });

    form.find(".close-controls .undo").on("click", function () {
        var row = $(this).closest("tr");
        row.find("[name$=\"-action\"]").val("");
        row.find(".close-controls").hide();
        row.find(".close-action").show();
    });

    form.find("[name$=\"-action\"]").each(function () {
        var v = $(this).val();
        if (!v)
            return;

        var row = $(this).closest("tr");

        if (v == "assign") {
            row.find(".reviewer-action").hide();
            row.find(".reviewer-controls").show();
        }
        else if (v == "close") {
            row.find(".close-action").hide();
            row.find(".close-controls").show();
        }
    });
});
