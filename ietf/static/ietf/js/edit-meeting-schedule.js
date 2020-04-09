jQuery(document).ready(function () {
    let content = jQuery(".edit-meeting-schedule");

    function failHandler(xhr, textStatus, error) {
        let errorText = error;
        if (xhr && xhr.responseText)
            errorText += "\n\n" + xhr.responseText;
        alert("Error: " + errorText);
    }

    let sessions = content.find(".session");
    let timeslots = content.find(".timeslot");

    // hack to work around lack of position sticky support in old browsers, see https://caniuse.com/#feat=css-sticky
    if (content.find(".scheduling-panel").css("position") != "sticky") {
        content.find(".scheduling-panel").css("position", "fixed");
        content.css("padding-bottom", "14em");
    }

    // selecting
    function selectSessionElement(element) {
        if (element) {
            sessions.not(element).removeClass("selected");
            jQuery(element).addClass("selected");
            showConstraintHints(element.id.slice("session".length));
            content.find(".scheduling-panel .session-info-container").html(jQuery(element).find(".session-info").html());
        }
        else {
            sessions.removeClass("selected");
            showConstraintHints();
            content.find(".scheduling-panel .session-info-container").html("");
        }
    }

    function showConstraintHints(sessionIdStr) {
        sessions.find(".constraints > span").each(function () {
            if (!sessionIdStr) {
                jQuery(this).removeClass("selected-hint");
                return;
            }

            let sessionIds = this.dataset.sessions;
            if (sessionIds)
                jQuery(this).toggleClass("selected-hint", sessionIds.split(",").indexOf(sessionIdStr) != -1);
        });
    }

    content.on("click", function (event) {
        selectSessionElement(null);
    });

    sessions.on("click", function (event) {
        event.stopPropagation();
        selectSessionElement(this);
    });


    if (ietfData.can_edit) {
        // dragging
        sessions.on("dragstart", function (event) {
            event.originalEvent.dataTransfer.setData("text/plain", this.id);
            jQuery(this).addClass("dragging");

            selectSessionElement(this);
        });
        sessions.on("dragend", function () {
            jQuery(this).removeClass("dragging");

        });

        sessions.prop('draggable', true);

        // dropping
        let dropElements = content.find(".timeslot,.unassigned-sessions");
        dropElements.on('dragenter', function (event) {
            if ((event.originalEvent.dataTransfer.getData("text/plain") || "").slice(0, "session".length) != "session")
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
            // skip dragleave events if they are to children
            if (event.originalEvent.currentTarget.contains(event.originalEvent.relatedTarget))
                return;

            jQuery(this).removeClass("dropping");
        });

        dropElements.on('drop', function (event) {
            jQuery(this).removeClass("dropping");

            let sessionId = event.originalEvent.dataTransfer.getData("text/plain");
            if ((event.originalEvent.dataTransfer.getData("text/plain") || "").slice(0, "session".length) != "session")
                return;

            let sessionElement = sessions.filter("#" + sessionId);
            if (sessionElement.length == 0)
                return;

            event.preventDefault(); // prevent opening as link

            if (sessionElement.parent().is(this))
                return;

            let dropElement = jQuery(this);

            function done(response) {
                if (response != "OK") {
                    failHandler(null, null, response);
                    return;
                }

                dropElement.append(sessionElement); // move element
                updateCurrentSchedulingHints();
                if (dropElement.hasClass("unassigned-sessions"))
                    sortUnassigned();
            }

            if (dropElement.hasClass("unassigned-sessions")) {
                jQuery.ajax({
                    url: ietfData.urls.assign,
                    method: "post",
                    timeout: 5 * 1000,
                    data: {
                        action: "unassign",
                        session: sessionId.slice("session".length)
                    }
                }).fail(failHandler).done(done);
            }
            else {
                jQuery.ajax({
                    url: ietfData.urls.assign,
                    method: "post",
                    data: {
                        action: "assign",
                        session: sessionId.slice("session".length),
                        timeslot: dropElement.attr("id").slice("timeslot".length)
                    },
                    timeout: 5 * 1000
                }).fail(failHandler).done(done);
            }
        });
    }

    // hints for the current schedule

    function updateCurrentSessionConstraintViolations() {
        // do a sweep on sessions sorted by start time
        let scheduledSessions = [];

        sessions.each(function () {
            let timeslot = jQuery(this).closest(".timeslot");
            if (timeslot.length == 1)
                scheduledSessions.push({
                    start: timeslot.data("start"),
                    end: timeslot.data("end"),
                    id: this.id.slice("session".length),
                    element: jQuery(this),
                    timeslot: timeslot.get(0)
                });
        });

        scheduledSessions.sort(function (a, b) {
            if (a.start < b.start)
                return -1;
            if (a.start > b.start)
                return 1;
            return 0;
        });

        let currentlyOpen = {};
        let openedIndex = 0;
        for (let i = 0; i < scheduledSessions.length; ++i) {
            let s = scheduledSessions[i];

            // prune
            for (let sessionIdStr in currentlyOpen) {
                if (currentlyOpen[sessionIdStr].end <= s.start)
                    delete currentlyOpen[sessionIdStr];
            }

            // expand
            while (openedIndex < scheduledSessions.length && scheduledSessions[openedIndex].start < s.end) {
                let toAdd = scheduledSessions[openedIndex];
                currentlyOpen[toAdd.id] = toAdd;
                ++openedIndex;
            }

            // check for violated constraints
            s.element.find(".constraints > span").each(function () {
                let sessionIds = this.dataset.sessions;

                let violated = sessionIds && sessionIds.split(",").filter(function (v) {
                    return (v != s.id
                            && v in currentlyOpen
                            // ignore errors within the same timeslot
                            // under the assumption that the sessions
                            // in the timeslot happen sequentially
                            && s.timeslot != currentlyOpen[v].timeslot);
                }).length > 0;

                jQuery(this).toggleClass("violated-hint", violated);
            });
        }
    }

    function updateTimeSlotDurationViolations() {
        timeslots.each(function () {
            let total = 0;
            jQuery(this).find(".session").each(function () {
                total += +jQuery(this).data("duration");
            });

            jQuery(this).toggleClass("overfull", total > +jQuery(this).data("duration"));
        });
    }

    function updateAttendeesViolations() {
        sessions.each(function () {
            let roomCapacity = jQuery(this).closest(".timeline").data("roomcapacity");
            if (roomCapacity && this.dataset.attendees)
                jQuery(this).toggleClass("too-many-attendees", +this.dataset.attendees > +roomCapacity);
        });
    }

    function updateCurrentSchedulingHints() {
        updateCurrentSessionConstraintViolations();
        updateAttendeesViolations();
        updateTimeSlotDurationViolations();
    }

    updateCurrentSchedulingHints();

    // sorting unassigned
    function sortArrayWithKeyFunctions(array, keyFunctions) {
        function compareArrays(a, b) {
            for (let i = 1; i < a.length; ++i) {
                let ai = a[i];
                let bi = b[i];

                if (ai > bi)
                    return 1;
                else if (ai < bi)
                    return -1;
            }

            return 0;
        }

        let arrayWithSortKeys = array.map(function (a) {
            let res = [a];
            for (let i = 0; i < keyFunctions.length; ++i)
                res.push(keyFunctions[i](a));
            return res;
        });

        arrayWithSortKeys.sort(compareArrays);

        return arrayWithSortKeys.map(function (l) {
            return l[0];
        });
    }

    function sortUnassigned() {
        let sortBy = content.find("select[name=sort_unassigned]").val();

        function extractName(e) {
            return e.querySelector(".session-label").innerHTML;
        }

        function extractParent(e) {
            return e.querySelector(".session-parent").innerHTML;
        }

        function extractDuration(e) {
            return +e.dataset.duration;
        }

        function extractComments(e) {
            return e.querySelector(".session-info .comments") ? 0 : 1;
        }

        let keyFunctions = [];
        if (sortBy == "name")
            keyFunctions = [extractName, extractDuration];
        else if (sortBy == "parent")
            keyFunctions = [extractParent, extractName, extractDuration];
        else if (sortBy == "duration")
            keyFunctions = [extractDuration, extractParent, extractName];
        else if (sortBy == "comments")
            keyFunctions = [extractComments, extractParent, extractName, extractDuration];

        let unassignedSessionsContainer = content.find(".unassigned-sessions");

        let sortedSessions = sortArrayWithKeyFunctions(unassignedSessionsContainer.children(".session").toArray(), keyFunctions);
        for (let i = 0; i < sortedSessions.length; ++i)
            unassignedSessionsContainer.append(sortedSessions[i]);
    }

    content.find("select[name=sort_unassigned]").on("change click", function () {
        sortUnassigned();
    });

    sortUnassigned();

    // toggling of sessions
    let sessionParentInputs = content.find(".session-parent-toggles input");

    function updateSessionParentToggling() {
        let checked = [];
        sessionParentInputs.filter(":checked").each(function () {
            checked.push(".parent-" + this.value);
        });

        sessions.not(".untoggleable").filter(checked.join(",")).show();
        sessions.not(".untoggleable").not(checked.join(",")).hide();
    }

    sessionParentInputs.on("click", updateSessionParentToggling);

    updateSessionParentToggling();
});

