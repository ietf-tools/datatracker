jQuery(function () {
    jQuery("table.history .snipped .showAll").click(function () {
        jQuery(this).parents("snipped").hide().siblings("full").show();
    });
});
