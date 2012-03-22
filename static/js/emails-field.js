jQuery(function () {
    jQuery(".emails-field").each(function () {
        var e = jQuery(this);
        e.tokenInput(e.data("ajax-url"), {
            hintText: "",
            preventDuplicates: true,
            prePopulate: JSON.parse(e.val())
        });
    });
});
