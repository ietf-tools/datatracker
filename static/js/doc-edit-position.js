jQuery(document).ready(function () {
    function setDiscussWidgetVisibility(discuss) {
        if (discuss)
            jQuery("form.position-form .discuss-widgets").show();
        else
            jQuery("form.position-form .discuss-widgets").hide();
    }
    
    jQuery("form.position-form input[name=position]").click(function (e) {
        setDiscussWidgetVisibility(jQuery(this).val() == "discuss");
    });

    setDiscussWidgetVisibility(jQuery("form.position-form input[name=position][value=discuss]").is(':checked'));
});
