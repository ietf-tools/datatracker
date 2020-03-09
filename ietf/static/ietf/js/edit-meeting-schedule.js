jQuery(document).ready(function () {
    if (!ietfScheduleData.can_edit)
        return;

    var content = jQuery(".edit-meeting-schedule");

    function failHandler(xhr, textStatus, error) {
        alert("Error: " + error);
    }

    var sessions = content.find(".session");
    var timeslots = content.find(".timeslot");

    // dragging
    sessions.on("dragstart", function (event) {
        event.originalEvent.dataTransfer.setData("text/plain", this.id);
        jQuery(this).addClass("dragging");
    });
    sessions.on("dragend", function () {
        jQuery(this).removeClass("dragging");

    });

    sessions.prop('draggable', true);

    // dropping
    var dropElements = content.find(".timeslot,.unassigned-sessions");
    dropElements.on('dragenter', function (event) {
        if ((event.originalEvent.dataTransfer.getData("text/plain") || "").slice(0, "session".length) != "session")
            return;

        if (jQuery(this).hasClass("disabled"))
            return;

        event.preventDefault(); // default action is signalling that this is not a valid target
        jQuery(this).addClass("dropping");
    });

    dropElements.on('dragover', function (event) {
        // we don't actually need this event, except we need to signal
        // that this is a valid drop target, by cancelling the default
        // action
        event.preventDefault();
    });
    
    dropElements.on('dragleave', function (event) {
        jQuery(this).removeClass("dropping");
    });
    
    dropElements.on('drop', function (event) {
        jQuery(this).removeClass("dropping");

        var sessionId = event.originalEvent.dataTransfer.getData("text/plain");
        if ((event.originalEvent.dataTransfer.getData("text/plain") || "").slice(0, "session".length) != "session")
            return;

        var sessionElement = sessions.filter("#" + sessionId);
        if (sessionElement.length == 0)
            return;

        event.preventDefault(); // prevent opening as link

        if (sessionElement.parent().is(this))
            return;

        var dropElement = jQuery(this);

        function done() {
            dropElement.append(sessionElement); // move element
            maintainTimeSlotHints();
        }

        if (dropElement.hasClass("unassigned-sessions")) {
            jQuery.ajax({
                url: ietfScheduleData.urls.assign,
                method: "post",
                data: {
                    action: "unassign",
                    session: sessionId.slice("session".length)
                }
            }).fail(failHandler).done(done);
        }
        else {
            jQuery.ajax({
                url: ietfScheduleData.urls.assign,
                method: "post",
                data: {
                    action: "assign",
                    session: sessionId.slice("session".length),
                    timeslot: dropElement.data("timeslot")
                }
            }).fail(failHandler).done(done);
        }
    });


    // hints
    function maintainTimeSlotHints() {
        timeslots.each(function () {
            var total = 0;
            jQuery(this).find(".session").each(function () {
                total += +jQuery(this).data("duration");
            });

            jQuery(this).toggleClass("overfull", total > +jQuery(this).data("duration"));
        });
    }

    maintainTimeSlotHints();

    // toggling of parents
    var sessionParentInputs = content.find(".session-parent-toggles input");

    function maintainSessionParentToggling() {
        var checked = [];
        sessionParentInputs.filter(":checked").each(function () {
            checked.push(".parent-" + this.value);
        });

        sessions.filter(".toggleable").filter(checked.join(",")).show();
        sessions.filter(".toggleable").not(checked.join(",")).hide();
    }

    sessionParentInputs.on("click", maintainSessionParentToggling);

    maintainSessionParentToggling();
});

