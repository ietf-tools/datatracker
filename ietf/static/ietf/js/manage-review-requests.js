$(document).ready(function () {
    var form = $("form.review-requests");

    function setControlDisplay(row) {
        var action = row.find("[name$=\"-action\"]").val();
        if (action == "assign") {
            row.find(".reviewer-controls").show();
            row.find(".close-controls").hide();
            row.find(".assign-action,.close-action").hide();
        }
        else if (action == "close") {
            row.find(".reviewer-controls").hide();
            row.find(".close-controls").show();
            row.find(".assign-action,.close-action").hide();
        }
        else {
            row.find(".reviewer-controls,.close-controls").hide();
            row.find(".assign-action,.close-action").show();
        }
    }

    form.find(".assign-action button").on("click", function () {
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

        row.find("[name$=\"-action\"]").val("assign");
        setControlDisplay(row);
    });

    form.find(".reviewer-controls .undo").on("click", function () {
        var row = $(this).closest("tr");
        row.find("[name$=\"-action\"]").val("");
        row.find("[name$=\"-reviewer\"]").val($(this).data("initial"));
        setControlDisplay(row);
    });

    form.find(".close-action button").on("click", function () {
        var row = $(this).closest("tr");
        row.find("[name$=\"-action\"]").val("close");
        setControlDisplay(row);
    });

    form.find(".close-controls .undo").on("click", function () {
        var row = $(this).closest("tr");
        row.find("[name$=\"-action\"]").val("");
        setControlDisplay(row);
    });

    form.find("[name$=\"-action\"]").each(function () {
        var v = $(this).val();
        if (!v)
            return;

        var row = $(this).closest("tr");
        setControlDisplay(row);
    });
});
