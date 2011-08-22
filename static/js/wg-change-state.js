jQuery(document).ready(function () {
    var initial_time = jQuery("#id_initial_time").parent().parent()
    if (jQuery("#id_charter_state").val() != "infrev") {
	initial_time.hide()
    }

    function setMessageDraft(state) {
      if (jQuery("#id_state").val() != "conclude") {
	if (message[state]) {
	    if (state == "infrev") {
		initial_time.show();
		jQuery("#id_initial_time").val(1);
	    } else {
		initial_time.hide();
		jQuery("#id_initial_time").val(0);
	    }
            jQuery("#id_message").val(message[state]);
	} else {
            jQuery("#id_message").val("");
	}
      } else {
            jQuery("#id_message").val("");
      }
    }
    
    jQuery("#id_charter_state").click(function (e) {
        setMessageDraft(jQuery(this).val());
    });

    jQuery("#id_charter_state").click();
    
});
