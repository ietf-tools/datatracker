jQuery(function () {
    var idCounter = -1;

    // make sure we got the lowest number for idCounter
    jQuery('#milestones-form .edit-milestone input[name$="-id"]').each(function () {
        var v = +this.value;
        if (!isNaN(v) && v < idCounter)
            idCounter = v - 1;
    });

    function setSubmitButtonState() {
        var action, label;
        if (jQuery("#milestones-form input[name$=desc]:visible").length > 0)
            action = "review";
        else
            action = "save";

        var submit = jQuery("#milestones-form input[type=submit]");
        submit.val(submit.data("label" + action));
        jQuery("#milestones-form input[name=action]").val(action);
    }

    jQuery("#milestones-form tr.milestone").click(function () {
        var row = jQuery(this), editRow = row.next("tr.edit-milestone");

        if (row.hasClass("add")) {
            // move Add milestone row and duplicate hidden template
            row.closest("table").append(row).append(editRow.clone());

            // fixup template
            var newId = idCounter;
            --idCounter;

            var prefix = "m" + newId;
            editRow.find('input[name="prefix"]').val(prefix);

            editRow.find("input,select,textarea").each(function () {
                if (this.name == "prefix")
                    return;

                if (this.name == "id")
                    this.value = "" + idCounter;

                this.name = prefix + "-" + this.name;
            });

            editRow.removeClass("template");
            setupTokenizedField(editRow.find(".tokenized-field")); // from tokenized-field.js
            setInputMasks(editRow);
            editRow.show();
        }
        else {
            row.hide();
            editRow.show();
        }

        editRow.find('input[name$="expanded_for_editing"]').val("True");
        editRow.find('input[name$="desc"]').focus();

        setSubmitButtonState();
    });

    function setResolvedState() {
        var resolved = jQuery(this).is(":checked");
        var label = jQuery(this).siblings("label");
        var reason = jQuery(this).siblings("input[type=text]");
        if (resolved) {
            if (label.text().indexOf(":") == -1)
                label.text(label.text() + ":");
            reason.show();
            if (!reason.val())
                reason.val(finishedMilestoneText);
        }
        else {
            if (label.text().indexOf(":") != -1)
                label.text(label.text().replace(":", ""));
            reason.hide();
            reason.val("");
        }
    }

    jQuery("#milestones-form .edit-milestone .resolved input[type=checkbox]")
        .each(setResolvedState)
        .live("change", setResolvedState);

    function setDeleteState() {
        var top = jQuery(this).closest(".edit-milestone");

        if (jQuery(this).is(":checked")) {
            if (+top.find('input[name$="id"]').val() < 0) {
                top.remove();
                setSubmitButtonState();
            }
            else
                top.addClass("delete")
        }
        else
            top.removeClass("delete")
    }

    jQuery("#milestones-form .edit-milestone .delete input[type=checkbox]")
        .each(setDeleteState)
        .live("change", setDeleteState);

    function setInputMasks(editRows) {
        editRows.find(".due input").mask("9999-99-99");
    }

    setInputMasks(jQuery("#milestone-form .edit-milestone").not(".template"));

    jQuery('#milestones-form .edit-milestone .errorlist').each(function () {
        jQuery(this).closest(".edit-milestone").prev().click();
    });
});
