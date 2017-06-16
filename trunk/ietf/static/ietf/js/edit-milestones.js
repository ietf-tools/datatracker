$(document).ready(function () {
    var idCounter = -1;
    var milestonesForm = $('#milestones-form');

    // make sure we got the lowest number for idCounter
    milestonesForm.find('.edit-milestone input[name$="-id"]').each(function () {
        var v = +this.value;
        if (!isNaN(v) && v < idCounter)
            idCounter = v - 1;
    });

    function setChanged() {
        $(this).closest(".edit-milestone").addClass("changed");
        setSubmitButtonState();
    }

    milestonesForm.on("change", '.edit-milestone select,.edit-milestone input,.edit-milestone textarea', setChanged);
    milestonesForm.on("click", '.edit-milestone .select2 input', setChanged);

    // the required stuff seems to trip up many browsers with dynamic forms
    milestonesForm.find("input").prop("required", false);


    function setSubmitButtonState() {
        var action, label;
        if (milestonesForm.find("input[name$=delete]:visible").length > 0)
            action = "review";
        else
            action = "save";

        milestonesForm.find("input[name=action]").val(action);

        var submit = milestonesForm.find("[type=submit]");
        submit.text(submit.data("label" + action));
        if (milestonesForm.find(".edit-milestone.changed,.edit-milestone.delete").length > 0 || action == "review")
            submit.show();
        else
            submit.hide();
    }

    milestonesForm.find(".milestone").click(function () {
        var row = $(this), editRow = row.next(".edit-milestone");
        row.hide();
        editRow.show();

        editRow.find('input[name$="desc"]').focus();

        setSubmitButtonState();

        // collapse unchanged rows
        milestonesForm.find(".milestone").not(this).each(function () {
            var e = $(this).next('.edit-milestone');
            if (e.is(":visible") && !e.hasClass("changed")) {
                $(this).show();
                e.hide();
            }
        });
    });

    milestonesForm.find(".add-milestone").click(function() {
        // move Add milestone row and duplicate hidden template
        var row = $(this).closest("tr"), editRow = row.next(".edit-milestone");
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
            this.id = prefix + "-" + this.id;
        });
        editRow.find("label").each(function () {
            if (this.htmlFor)
                this.htmlFor = prefix + "-" + this.htmlFor;
        });

        editRow.removeClass("template");
        editRow.show();

        editRow.find(".select2-field").each(function () {
            window.setupSelect2Field($(this)); // from ietf.js
        });
    });

    function setResolvedState() {
        var resolved = $(this).is(":checked");
        var label = $(this).closest(".edit-milestone").find("label[for=" + this.id + "]");
        var reason = $(this).closest(".edit-milestone").find("[name$=resolved]");
        if (resolved) {
            reason.closest(".form-group").show();
            if (!reason.val())
                reason.val(reason.data("default"));
        }
        else {
            reason.closest(".form-group").hide();
            reason.val("");
        }
    }

    milestonesForm.find(".edit-milestone [name$=resolved_checkbox]").each(setResolvedState);
    milestonesForm.on("change", ".edit-milestone [name$=resolved_checkbox]", setResolvedState);

    function setDeleteState() {
        var edit = $(this).closest(".edit-milestone"), row = edit.prev(".milestone");

        if ($(this).is(":checked")) {
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

    milestonesForm.find(".edit-milestone [name$=delete]").each(setDeleteState);
    milestonesForm.on("change", ".edit-milestone input[name$=delete]", setDeleteState);

    milestonesForm.find('.edit-milestone .has-error').each(function () {
        $(this).closest(".edit-milestone").prev().click();
    });

    setSubmitButtonState();
});
