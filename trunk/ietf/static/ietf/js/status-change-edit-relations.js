$(function () {
    var form = $(".new-relation-row").closest("form");
    var newRowHtml = form.find(".new-relation-row").get(0).outerHTML;
    var counter = 1;

    form.on("click", ".delete", function (e) {
        e.preventDefault();
        $(this).closest(".row").remove();
    });

    form.on("keydown", ".new-relation-row input[type=text]", function () {
        var top = $(this).closest(".new-relation-row");
        top.removeClass("new-relation-row");
        top.find(".help-block").remove();
        top.find(".delete").show();
        top.find("input,select").each(function () {
            this.name += counter;
        });
        ++counter;
        top.after(newRowHtml);
    });
});
