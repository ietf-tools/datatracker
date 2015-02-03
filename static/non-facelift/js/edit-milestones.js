jQuery(function () {
    var idCounter = -1;

    // make sure we got the lowest number for idCounter
    jQuery('#milestones-form .edit-milestone input[name$="-id"]').each(function () {
        var v = +this.value;
        if (!isNaN(v) && v < idCounter)
            idCounter = v - 1;
    });

    function setChanged() {
        $(this).closest(".edit-milestone").addClass("changed");
    }

    jQuery('#milestones-form .edit-milestone select,#milestones-form .edit-milestone input,#milestones-form .edit-milestone textarea').live("change", setChanged);
    jQuery('#milestones-form .edit-milestone .token-input-list input').live("click", setChanged);

    function setSubmitButtonState() {
        var action, label;
        if (jQuery("#milestones-form input[name$=delete]:visible").length > 0)
            action = "review";
        else
            action = "save";

        jQuery("#milestones-form input[name=action]").val(action);

        var submit = jQuery("#milestones-form input[type=submit]");
        submit.val(submit.data("label" + action));
        if (jQuery("#milestones-form .edit-milestone.changed").length > 0 || action == "review")
            submit.show();
        else
            submit.hide();
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
            editRow.show();
        }
        else {
            row.hide();
            editRow.show();
        }

        editRow.find('input[name$="desc"]').focus();

        setSubmitButtonState();

        // collapse unchanged rows
        jQuery("#milestones-form tr.milestone").not(this).each(function () {
            var e = jQuery(this).next('tr.edit-milestone');
            if (e.is(":visible") && !e.hasClass("changed")) {
                jQuery(this).show();
                e.hide();
            }
        });
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
        var edit = jQuery(this).closest(".edit-milestone"), row = edit.prev("tr.milestone");

        if (jQuery(this).is(":checked")) {
            if (+edit.find('input[name$="id"]').val() < 0) {
                edit.remove();
                setSubmitButtonState();
            }
            else {
                row.addClass("delete");
                edit.addClass("delete");
            }
        }
        else {
            row.removeClass("delete");
            edit.removeClass("delete");
        }
    }

    jQuery("#milestones-form .edit-milestone .delete input[type=checkbox]")
        .each(setDeleteState)
        .live("change", setDeleteState);

    jQuery('#milestones-form .edit-milestone .errorlist').each(function () {
        jQuery(this).closest(".edit-milestone").prev().click();
    });

    setSubmitButtonState();
});
