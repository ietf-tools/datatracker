jQuery(document).ready(function () {
    jQuery("#clear-all-on-schedule").click(function (e) {
        e.preventDefault();

        jQuery("div.reschedule select").attr("selectedIndex", 0);
    })
});
