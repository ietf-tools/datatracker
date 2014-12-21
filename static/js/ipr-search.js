// this is required to trigger the correct submit button if enter is pressed
jQuery(function() {
    jQuery("#id_state input[value!=all]").change(function(e) {
        if (this.checked) {
            jQuery("#id_state_0").prop('checked',false);
        }
    });
    jQuery("#id_state_0").change(function(e) {
        if (this.checked) {
            jQuery("#id_state input[value!=all]").prop('checked',false);
        }
    });
    
    jQuery("form input,select").keypress(function (e) {
        //alert("key press");
        if ((e.which && e.which == 13) || (e.keyCode && e.keyCode == 13)) {
            jQuery(this).next('button[type=submit]').click();
            return false;
        } else {
            return true;
        }
    });
});