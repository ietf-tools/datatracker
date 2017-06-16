$(document).ready(function () {
    $("[name=rule_type]").on("click change keypress", function () {
        var form = $(this).closest("form");
        var ruleType = $(this).val();
        var emptyForms = $(".empty-forms");

        var currentFormContent = form.find(".form-content-placeholder .rule-type");
        if (!ruleType || !currentFormContent.hasClass(ruleType)) {
            // move previous back into the collection
            if (currentFormContent.length > 0)
                emptyForms.append(currentFormContent);
            else
                currentFormContent.html(""); // make sure it's empty

            // insert new
            if (ruleType)
                form.find(".form-content-placeholder").append(emptyForms.find("." + ruleType));
        }
    });

    $("[name=rule_type]").each(function () {
        // don't trigger the handler if we have a form with errors
        var placeholderContent = $(this).closest("form").find(".form-content-placeholder >");
        if (placeholderContent.length == 0 || placeholderContent.hasClass("rule-type"))
            $(this).trigger("change");
    });
});
