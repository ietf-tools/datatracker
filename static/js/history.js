jQuery(function () {
    jQuery("table.history .snippet .show-all").click(function () {
        jQuery(this).parents(".snippet").hide().siblings(".full").show();
    });
});
