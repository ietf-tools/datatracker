jQuery(document).ready(function () {
    function setMessageDraft() {
        var v = $(this).val();
        jQuery("#id_message").val(messages[v] || "");
    }

    jQuery("#id_charter_state").click(setMessageDraft).change(setMessageDraft).keydown(setMessageDraft);

    if (jQuery("#id_message").val() == "")
        jQuery("#id_charter_state").click();
});
