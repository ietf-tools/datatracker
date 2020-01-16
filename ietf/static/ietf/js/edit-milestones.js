$(document).ready(function () {
    var idCounter = -1;
    var milestonesForm = $('#milestones-form');
    var group_uses_milestone_dates = ( $('#uses_milestone_dates').length > 0 );
    var milestone_order_has_changed = false;
    var switch_date_use_form = $("#switch-date-use-form")

    // make sure we got the lowest number for idCounter
    milestonesForm.find('.edit-milestone input[name$="-id"]').each(function () {
        var v = +this.value;
        if (!isNaN(v) && v < idCounter)
            idCounter = v - 1;
    });

    function setChanged() {
        $(this).closest(".edit-milestone").addClass("changed");
        setSubmitButtonState();
        if (switch_date_use_form) {
            switch_date_use_form.hide();
        }
    }

    milestonesForm.on("change", '.edit-milestone select,.edit-milestone input,.edit-milestone textarea', setChanged);
    milestonesForm.on("click", '.edit-milestone .select2 input', setChanged);

    // the required stuff seems to trip up many browsers with dynamic forms
    milestonesForm.find("input").prop("required", false);


    function setSubmitButtonState() {
        var action, label;
        if ( milestonesForm.find("input[name$=delete]:visible").length > 0 || milestone_order_has_changed )
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
        var template = $("#extratemplatecontainer .extratemplate");
        var templateclone = template.clone();
        $("#dragdropcontainer").append(templateclone);
        var new_milestone = $("#dragdropcontainer > div:last")
        var new_edit_milestone = new_milestone.find(".edit-milestone");
        var new_edit_milestone_order = $("#dragdropcontainer > div").length

        new_milestone.removeClass("extratemplate")
        new_milestone.addClass("draggable")
        new_milestone.addClass("milestonerow")

        var newId = idCounter;
        --idCounter;

        var prefix = "m" + newId;
        new_edit_milestone.find('input[name="prefix"]').val(prefix);
        new_edit_milestone.find('input[name="order"]').val(new_edit_milestone_order);

        new_edit_milestone.find("input,select,textarea").each(function () {
            if (this.name == "prefix")
                return;

            if (this.name == "id")
                this.value = "" + idCounter;

            this.name = prefix + "-" + this.name;
            this.id = prefix + "-" + this.id;
        });
        new_edit_milestone.find("label").each(function () {
            if (this.htmlFor)
                this.htmlFor = prefix + "-" + this.htmlFor;
        });

        new_edit_milestone.removeClass("template");
        new_edit_milestone.show();

        new_edit_milestone.find(".select2-field").each(function () {
            window.setupSelect2Field($(this)); // from ietf.js
        });

        if ( ! group_uses_milestone_dates ) {
            setOrderControlValue();
        }
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

    function setOrderControlValue() {
        $("#dragdropcontainer > div").each(function(index){
            var prefix = $(this).find('input[name="prefix"]').val();
            $(this).find('input[name="'+prefix+'-order"]').val(index)
        })
    }

    milestonesForm.find(".edit-milestone [name$=delete]").each(setDeleteState);
    milestonesForm.on("change", ".edit-milestone input[name$=delete]", setDeleteState);

    milestonesForm.find('.edit-milestone .has-error').each(function () {
        $(this).closest(".edit-milestone").prev().click();
    });

    setSubmitButtonState();

    if ( ! group_uses_milestone_dates) {
        setOrderControlValue();

        function onEnd(event) {
            milestone_order_has_changed = true;
            setSubmitButtonState();
            setOrderControlValue();
            if (switch_date_use_form) {
                switch_date_use_form.hide();
            }            

        }

        var options = {
            animation: 150,
            draggable: ".draggable",
            onEnd: function(event) {onEnd(event)}
        };

        var el = document.getElementById('dragdropcontainer');
        var sortable = new Sortable(el, options);
    }
});