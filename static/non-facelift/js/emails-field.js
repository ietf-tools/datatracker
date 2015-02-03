jQuery(function () {
    jQuery(".tokenized-field").each(function () {
        var e = jQuery(this);
        var pre = [];
        if (e.val())
            pre = JSON.parse(e.val());
        e.tokenInput(e.data("data-ajax-url"), {
            hintText: "",
            preventDuplicates: true,
            prePopulate: pre
        });
    });
});
