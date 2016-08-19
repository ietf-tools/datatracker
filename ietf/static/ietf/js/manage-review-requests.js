$(document).ready(function () {
    var form = $("form.review-requests");

    form.find(".reviewer-action").on("click", function () {
        var row = $(this).closest("tr");
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

        if (v == "assign")
            row.find(".reviewer-action").click();
        else if (v == "close")
            row.find(".close-action").click();
    });
});
