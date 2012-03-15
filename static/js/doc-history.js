jQuery(function () {
    jQuery("table.history .snippet .showAll").click(function () {
        jQuery(this).parents(".snippet").hide().siblings(".full").show();
    });
});
