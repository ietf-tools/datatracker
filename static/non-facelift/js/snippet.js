jQuery(function () {
    jQuery("table .snippet .show-all").click(function () {
        jQuery(this).parents(".snippet").hide().siblings(".full").show();
    });
});
