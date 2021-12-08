jQuery(document).ready(function () {
    function reportServerError(xhr, textStatus, error) {
        let errorText = error || textStatus;
        if (xhr && xhr.responseText)
            errorText += "\n\n" + xhr.responseText;
        alert("Error: " + errorText);
    }

    let content = jQuery(".edit-meeting-timeslots-and-misc-sessions");

    if (content.data('scroll'))
        jQuery(document).scrollTop(+content.data('scroll'));
    else {
        let scrollFragment = "#scroll=";
        if (window.location.hash.slice(0, scrollFragment.length) == scrollFragment && !isNaN(+window.location.hash.slice(scrollFragment.length))) {
            jQuery(document).scrollTop(+window.location.hash.slice(scrollFragment.length));
            history.replaceState(null, document.title, window.location.pathname + window.location.search);
        }
    }

    function reportServerError(xhr, textStatus, error) {
        let errorText = error || textStatus;
        if (xhr && xhr.responseText)
            errorText += "\n\n" + xhr.responseText;
        alert("Error: " + errorText);
    }

    let timeslots = content.find(".timeslot");

    timeslots.each(function () {
        jQuery(this).tooltip({title: jQuery(this).text()});
    });

    content.find(".day-grid").on("click", cancelCurrentActivity);

    let schedulingPanel = content.find(".scheduling-panel");

    function cancelCurrentActivity() {
        content.find(".selected").removeClass("selected");

        schedulingPanel.hide();
        schedulingPanel.find(".panel-content").children().remove();
        // if we came from a failed POST, that's no longer relevant so overwrite history
        history.replaceState(null, document.title, window.location.pathname + window.location.search);
    }

    if (!content.hasClass("read-only")) {
        // we handle the hover effect in Javascript because we don't want
        // it to show in case the timeslot itself is hovered
        content.find(".room-label,.timeline").on("mouseover", function () {
            jQuery(this).closest(".day").find(".timeline.hover").removeClass("hover");
            jQuery(this).closest(".room-row").find(".timeline").addClass("hover");
        }).on("mouseleave", function (){
            jQuery(this).closest(".day").find(".timeline.hover").removeClass("hover");
        });

        content.find(".timeline .timeslot").on("mouseover", function (e) {
            e.stopPropagation();
            jQuery(this).closest(".day").find(".timeline.hover").removeClass("hover");
        }).on("mouseleave", function (e) {
            jQuery(this).closest(".day").find(".timeline.hover").removeClass("hover");
        });

        content.find(".room-row").on("click", function (e) {
            e.stopPropagation();
            cancelCurrentActivity();

            jQuery(this).find(".timeline").addClass("selected");

            schedulingPanel.find(".panel-content").append(content.find(".add-timeslot-template").html());
            schedulingPanel.find("[name=day]").val(this.dataset.day);
            schedulingPanel.find("[name=location]").val(this.dataset.room);
            schedulingPanel.find("[name=type]").trigger("change");
            schedulingPanel.show();
            schedulingPanel.find("[name=time]").focus();
        });
    }

    content.find(".timeline .timeslot").on("click", function (e) {
        e.stopPropagation();

        let element = jQuery(this);

        element.addClass("selected");

        jQuery.ajax({
            url: window.location.href,
            method: "get",
            timeout: 5 * 1000,
            data: {
                action: "edit-timeslot",
                timeslot: this.id.slice("timeslot".length)
            }
        }).fail(reportServerError).done(function (response) {
            if (!response.form) {
                reportServerError(null, null, response);
                return;
            }

            cancelCurrentActivity();
            element.addClass("selected");

            schedulingPanel.find(".panel-content").append(response.form);
            schedulingPanel.find(".timeslot-form [name=type]").trigger("change");
            schedulingPanel.find(".timeslot-form").show();
            schedulingPanel.show();
        });
    });

    content.on("change click", ".timeslot-form [name=type]", function () {
        let form = jQuery(this).closest("form");

        let hide = {};

        form.find("[name=group],[name=short],[name=\"agenda_note\"]").prop('disabled', false).closest(".form-group").show();

        if (this.value == "break") {
            form.find("[name=short]").closest(".form-group").hide();
        }
        else if (this.value == "plenary") {
            let group = form.find("[name=group]");
            group.val(group.data('ietf'));
        }
        else if (this.value == "regular") {
            form.find("[name=short]").closest(".form-group").hide();
        }

        if (this.value != "regular")
            form.find("[name=\"agenda_note\"]").closest(".form-group").hide();

        if (['break', 'reg', 'reserved', 'unavail', 'regular'].indexOf(this.value) != -1) {
            let group = form.find("[name=group]");
            group.prop('disabled', true);
            group.closest(".form-group").hide();
        }
    });

    content.on("submit", ".timeslot-form", function () {
        let form = jQuery(this).closest("form");
        form.find("[name=scroll]").remove();
        form.append("<input type=hidden name=scroll value=" + jQuery(document).scrollTop() + ">");
    });

    content.on("click", "button[type=submit][name=action][value=\"delete-timeslot\"],button[type=submit][name=action][value=\"cancel-timeslot\"]", function (e) {
        let msg = this.value == "delete-timeslot" ? "Delete this time slot?" : "Cancel the session in this time slot?";
        if (!confirm(msg)) {
            e.preventDefault();
        }
    });

    schedulingPanel.find(".close").on("click", function () {
        cancelCurrentActivity();
    });

    schedulingPanel.find('.timeslot-form [name=type]').trigger("change");
});
