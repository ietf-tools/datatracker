jQuery(function () {
    jQuery(".emails-field").each(function () {
        var e = jQuery(this);
        var pre = [];
        if (e.val())
            pre = JSON.parse(e.val());
        e.tokenInput(e.data("ajax-url"), {
            hintText: "",
            preventDuplicates: true,
            prePopulate: pre
        });
    });
});
