jQuery(document).ready(function () {
    function stateChanged() {
        var v = $(this).val();
        jQuery("#id_message").val(info_msg[v] || "");

        if (jQuery.inArray(+v, statesForBallotWoExtern) != -1)
            jQuery("tr.ballot-wo-extern").show();
        else
            jQuery("tr.ballot-wo-extern").hide();
    }

    jQuery("#id_charter_state").click(stateChanged).change(stateChanged).keydown(stateChanged);

    // trigger event
    jQuery("#id_charter_state").click();
});
