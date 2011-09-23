jQuery(document).ready(function () {

    function setMessageDraft(state) {
      if (jQuery("#id_state").val() == "conclude") {
            jQuery("#id_message").val("");
      } else {
        if (message[state]) {
            jQuery("#id_message").val(message[state]);
        } else {
            jQuery("#id_message").val("");
        }
      }
    }
    
    jQuery("#id_charter_state").click(function (e) {
        setMessageDraft(jQuery(this).val());
    });

    jQuery("#id_state").click(function (e) {
        setMessageDraft(jQuery("#id_charter_state").val());
    });

    var prev_mesg = jQuery("#id_message").val();

    if (prev_mesg == "") {
      jQuery("#id_charter_state").click();
    }
    
});
