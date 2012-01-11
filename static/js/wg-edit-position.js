jQuery(document).ready(function () {
    function setDiscussWidgetVisibility(block) {
        if (block)
            jQuery("form.position-form .block_comment-widgets").show();
        else
            jQuery("form.position-form .block_comment-widgets").hide();
    }
    
    jQuery("form.position-form input[name=position]").click(function (e) {
        setDiscussWidgetVisibility(jQuery(this).val() == "block");
    });

    setDiscussWidgetVisibility(jQuery("form.position-form input[name=position][value=block]").is(':checked'));
});
