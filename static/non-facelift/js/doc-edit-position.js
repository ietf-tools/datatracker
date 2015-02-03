jQuery(document).ready(function () {
    function setDiscussWidgetVisibility(val) {
        if (val in blockingPositions) {
            jQuery("form.position-form .discuss-widgets").show();
            jQuery("form.position-form .discuss-widgets label").text(blockingPositions[val]);
        }
        else
            jQuery("form.position-form .discuss-widgets").hide();
    }
    
    jQuery("form.position-form input[name=position]").click(function (e) {
        setDiscussWidgetVisibility(jQuery(this).val());
    });

    setDiscussWidgetVisibility(jQuery("form.position-form input[name=position]:checked").val());
});
