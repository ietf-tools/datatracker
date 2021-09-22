/* globals alert, jQuery, moment */
jQuery(document).ready(function () {
    let content = jQuery(".edit-meeting-schedule");
    /* Drag data stored via the drag event dataTransfer interface is only accessible on
     * dragstart and dragend events. Other drag events can see only the MIME types that have
     * data. Use a non-registered type to identify our session drags. Unregistered MIME
     * types are strongly discouraged by RFC6838, but we are not actually attempting to
     * exchange data with anything outside this script so that really does not apply. */
    const dnd_mime_type = 'text/x.session-drag';
    const meetingTimeZone = content.data('timezone');
    const lockSeconds = Number(content.data('lock-seconds') || 0);

    function reportServerError(xhr, textStatus, error) {
        let errorText = error || textStatus;
        if (xhr && xhr.responseText)
            errorText += "\n\n" + xhr.responseText;
        alert("Error: " + errorText);
    }

    /**
     * Time to treat as current time for computing whether to lock timeslots
     * @returns {*} Moment object equal to lockSeconds in the future
     */
    function effectiveNow() {
        return moment().add(lockSeconds, 'seconds');
    }

    let sessions = content.find(".session").not(".readonly");
    let sessionConstraints = sessions.find('.constraints > span');
    let timeslots = content.find(".timeslot");
    let timeslotLabels = content.find(".time-label");
    let swapDaysButtons = content.find('.swap-days');
    let swapTimeslotButtons = content.find('.swap-timeslot-col');
    let days = content.find(".day-flow .day");
    let officialSchedule = content.hasClass('official-schedule');

    // hack to work around lack of position sticky support in old browsers, see https://caniuse.com/#feat=css-sticky
    if (content.find(".scheduling-panel").css("position") != "sticky") {
        content.find(".scheduling-panel").css("position", "fixed");
        content.css("padding-bottom", "14em");
    }

    /**
     * Parse a timestamp using meeting-local time zone if the timestamp does not specify one.
     */
    function parseISOTimestamp(s) {
        return moment.tz(s, moment.ISO_8601, meetingTimeZone);
    }

    function startMoment(timeslot) {
        return parseISOTimestamp(timeslot.data('start'));
    }

    function endMoment(timeslot) {
        return parseISOTimestamp(timeslot.data('end'));
    }

    function findTimeslotsOverlapping(intervals) {
        let res = [];

        timeslots.each(function () {
            var timeslot = jQuery(this);
            let start = startMoment(timeslot);
            let end = endMoment(timeslot);

            for (let i = 0; i < intervals.length; ++i) {
                if (end >= intervals[i][0] && intervals[i][1] >= start) {
                    res.push(timeslot);
                    break;
                }
            }
        });

        return res;
    }

    // selecting
    function selectSessionElement(element) {
        sessions.removeClass("other-session-selected");
        if (element) {
            sessions.not(element).removeClass("selected");
            jQuery(element).addClass("selected");

            showConstraintHints(element);

            let sessionInfoContainer = content.find(".scheduling-panel .session-info-container");
            sessionInfoContainer.html(jQuery(element).find(".session-info").html());

            sessionInfoContainer.find("[data-original-title]").tooltip();

            sessionInfoContainer.find(".time").text(jQuery(element).closest(".timeslot").data('scheduledatlabel'));

            sessionInfoContainer.find(".other-session").each(function () {
                let otherSessionElement = sessions.filter("#session" + this.dataset.othersessionid).first();
                let scheduledAt = otherSessionElement.closest(".timeslot").data('scheduledatlabel');
                let timeElement = jQuery(this).find(".time");

                otherSessionElement.addClass("other-session-selected");
                if (scheduledAt)
                    timeElement.text(timeElement.data("scheduled").replace("{time}", scheduledAt));
                else
                    timeElement.text(timeElement.data("notscheduled"));
            });
        }
        else {
            sessions.removeClass("selected");
            showConstraintHints();
            content.find(".scheduling-panel .session-info-container").html("");
        }
    }

    /**
     * Mark or unmark a session that conflicts with the selected session
     *
     * @param constraintElt The element corresponding to the specific constraint
     * @param wouldViolate True to mark or false to unmark
     */
    function setSessionWouldViolate(constraintElt, wouldViolate) {
        constraintElt = jQuery(constraintElt);
        let constraintDiv = constraintElt.closest('div.session');  // find enclosing session div
        constraintDiv.toggleClass('would-violate-hint', wouldViolate);  // mark the session container
        constraintElt.toggleClass('would-violate-hint', wouldViolate);  // and the specific constraint
    }

    /**
     * Mark or unmark a timeslot that conflicts with the selected session
     *
     * If wholeInterval is true, marks the entire column in addition to the timeslot.
     * This currently works by setting the class for the timeslot and the time-label
     * in its column. Because this is called for every timeslot in the interval, the
     * overall effect is to highlight the entire column.
     *
     * @param timeslotElt Timeslot element to be marked/unmarked
     * @param wouldViolate True to mark or false to unmark
     * @param wholeInterval Should the entire time interval be flagged or just the timeslot?
     */
    function setTimeslotWouldViolate(timeslotElt, wouldViolate, wholeInterval) {
        timeslotElt = jQuery(timeslotElt);
        timeslotElt.toggleClass('would-violate-hint', wouldViolate);
        if (wholeInterval) {
            let index = timeslotElt.index(); // position of this timeslot relative to its container
            let label = timeslotElt
                          .closest('div.room-group')
                          .find('div.time-header .time-label')
                          .get(index); // get time-label corresponding to this timeslot
            jQuery(label).toggleClass('would-violate-hint', wouldViolate);
        }
    }

    /**
     * Remove all would-violate-hint classes on timeslots
     */
    function resetTimeslotsWouldViolate() {
        timeslots.removeClass("would-violate-hint");
        timeslotLabels.removeClass("would-violate-hint");
    }

    /**
     * Remove all would-violate-hint classes on sessions and their formatted constraints
     */
    function resetSessionsWouldViolate() {
        sessions.removeClass("would-violate-hint");
        sessionConstraints.removeClass("would-violate-hint");
    }

    function showConstraintHints(selectedSession) {
        let sessionId = selectedSession ? selectedSession.id.slice("session".length) : null;
        // hints on the sessions
        resetSessionsWouldViolate();
        if (sessionId) {
            sessionConstraints.each(function () {
                let sessionIds = this.dataset.sessions;
                if (sessionIds && (sessionIds.split(",").indexOf(sessionId) !== -1)) {
                    setSessionWouldViolate(this, true);
                }
            });
        }

        // hints on timeslots
        resetTimeslotsWouldViolate();
        if (selectedSession) {
            let intervals = [];
            timeslots.filter(":has(.session .constraints > span.would-violate-hint)").each(function () {
                intervals.push(
                  [parseISOTimestamp(this.dataset.start), parseISOTimestamp(this.dataset.end)]
                );
            });

            let overlappingTimeslots = findTimeslotsOverlapping(intervals);
            for (let i = 0; i < overlappingTimeslots.length; ++i) {
                setTimeslotWouldViolate(overlappingTimeslots[i], true, true);
            }

            // check room sizes
            let attendees = +selectedSession.dataset.attendees;
            if (attendees) {
                timeslots.not(".would-violate-hint").each(function () {
                    if (attendees > +jQuery(this).closest(".timeslots").data("roomcapacity")) {
                        setTimeslotWouldViolate(this, true, false);
                    }
                });
            }
        }
    }

    /**
     * Should this timeslot be treated as a future timeslot?
     *
     * @param timeslot timeslot to test
     * @param now (optional) threshold time (defaults to effectiveNow())
     * @returns Boolean true if the timeslot is in the future
     */
    function isFutureTimeslot(timeslot, now) {
        // resist the temptation to use native JS Date parsing, it is hopelessly broken
        const timeslot_time = startMoment(timeslot);
        return timeslot_time.isAfter(now || effectiveNow());
    }

    function hidePastTimeslotHints() {
        timeslots.removeClass('past-hint');
    }

    function showPastTimeslotHints() {
        timeslots.filter('.past').addClass('past-hint');
    }

    function updatePastTimeslots() {
        const now = effectiveNow();

        // mark timeslots
        timeslots.filter(
          ':not(.past)'
        ).filter(
          (_, ts) => !isFutureTimeslot(jQuery(ts), now)
        ).addClass('past');

        // hide swap day/timeslot column buttons
        if (officialSchedule) {
            swapDaysButtons.filter(
              (_, elt) => parseISOTimestamp(elt.dataset.start).isSameOrBefore(now, 'day')
            ).hide();
            swapTimeslotButtons.filter(
              (_, elt) => parseISOTimestamp(elt.dataset.start).isSameOrBefore(now, 'minute')
            ).hide();
        }
    }

    function canEditSession(session) {
        if (!officialSchedule) {
            return true;
        }

        const timeslot = jQuery(session).closest('div.timeslot');
        if (timeslot.length === 0) {
            return true;
        }

        return isFutureTimeslot(timeslot);
    }

    content.on("click", function (event) {
        if (jQuery(event.target).is(".session-info-container") || jQuery(event.target).closest(".session-info-container").length > 0)
            return;
        selectSessionElement(null);
    });

    sessions.on("click", function (event) {
        event.stopPropagation();
        // do not allow hidden sessions to be selected
        if (!jQuery(this).hasClass('hidden-parent')) {
            selectSessionElement(this);
        }
    });

    // Was this drag started by dragging a session?
    function isSessionDragEvent(event) {
        return Boolean(event.originalEvent.dataTransfer.getData(dnd_mime_type));
    }

    /**
     * Can a session be dropped in this element?
     *
     * Drop is allowed in drop-zones that are in unassigned-session or timeslot containers
     * not marked as 'past'.
     */
    function sessionDropAllowed(elt) {
        if (!officialSchedule) {
            return true;
        }

        const relevant_parent = elt.closest('.timeslot, .unassigned-sessions');
        return relevant_parent && !(relevant_parent.classList.contains('past'));
    }

    if (!content.find(".edit-grid").hasClass("read-only")) {
        // dragging
        sessions.on("dragstart", function (event) {
            if (canEditSession(this)) {
                event.originalEvent.dataTransfer.setData(dnd_mime_type, this.id);
                jQuery(this).addClass("dragging");
                selectSessionElement(this);
                showPastTimeslotHints();
            } else {
                event.preventDefault(); // do not start the drag
            }
        });
        sessions.on("dragend", function () {
            jQuery(this).removeClass("dragging");
            hidePastTimeslotHints();
        });

        sessions.prop('draggable', true);

        // dropping
        let dropElements = content.find(".timeslot .drop-target,.unassigned-sessions .drop-target");
        dropElements.on('dragenter', function (event) {
            if (sessionDropAllowed(this)) {
                event.preventDefault(); // default action is signalling that this is not a valid target
                jQuery(this).parent().addClass("dropping");
            }
        });

        dropElements.on('dragover', function (event) {
            // we don't actually need this event, except we need to signal
            // that this is a valid drop target, by cancelling the default
            // action
            if (sessionDropAllowed(this)) {
                event.preventDefault();
            }
        });

        dropElements.on('dragleave', function (event) {
            // skip dragleave events if they are to children
            const leaving_child = event.originalEvent.currentTarget.contains(event.originalEvent.relatedTarget);
            if (!leaving_child && sessionDropAllowed(this)) {
                jQuery(this).parent().removeClass('dropping');
            }
        });

        dropElements.on('drop', function (event) {
            let dropElement = jQuery(this);

            if (!isSessionDragEvent(event)) {
                // event is result of something other than a session drag
                dropElement.parent().removeClass("dropping");
                return;
            }

            const sessionId = event.originalEvent.dataTransfer.getData(dnd_mime_type);
            let sessionElement = sessions.filter("#" + sessionId);
            if (sessionElement.length === 0) {
                // drag event is not from a session we recognize
                dropElement.parent().removeClass("dropping");
                return;
            }

            // We now know this is a drop of a recognized session

            if (!sessionDropAllowed(this)) {
                dropElement.parent().removeClass("dropping"); // just in case
                return; // drop not allowed
            }

            event.preventDefault(); // prevent opening as link

            let dragParent = sessionElement.parent();
            if (dragParent.is(this)) {
                dropElement.parent().removeClass("dropping");
                return;
            }

            let dropParent = dropElement.parent();

            function failHandler(xhr, textStatus, error) {
                dropElement.parent().removeClass("dropping");
                reportServerError(xhr, textStatus, error);
            }

            function done(response) {
                dropElement.parent().removeClass("dropping");

                if (!response.success) {
                    reportServerError(null, null, response);
                    return;
                }

                dropElement.append(sessionElement); // move element
                if (response.tombstone)
                    dragParent.append(response.tombstone);

                updateCurrentSchedulingHints();
                if (dropParent.hasClass("unassigned-sessions"))
                    sortUnassigned();
            }

            if (dropParent.hasClass("unassigned-sessions")) {
                jQuery.ajax({
                    url: window.location.href,
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
                    url: window.location.href,
                    method: "post",
                    data: {
                        action: "assign",
                        session: sessionId.slice("session".length),
                        timeslot: dropParent.attr("id").slice("timeslot".length)
                    },
                    timeout: 5 * 1000
                }).fail(failHandler).done(done);
            }
        });


        // Helpers for swap days / timeslots
        // Enable or disable a swap modal's submit button
        let updateSwapSubmitButton = function (modal, inputName) {
            modal.find("button[type=submit]").prop(
              "disabled",
              modal.find("input[name='" + inputName + "']:checked").length === 0
            );
        };

        // Disable a particular swap modal radio input
        let updateSwapRadios = function (labels, radios, disableValue, datePrecision) {
            labels.removeClass('text-muted');
            radios.prop('disabled', false);
            radios.prop('checked', false);
            // disable the input requested by value
            let disableInput = radios.filter('[value="' + disableValue + '"]');
            if (disableInput) {
                disableInput.parent().addClass('text-muted');
                disableInput.prop('disabled', true);
            }
            if (officialSchedule) {
                // disable any that have passed
                const now=effectiveNow();
                const past_radios = radios.filter(
                  (_, radio) => parseISOTimestamp(radio.dataset.start).isSameOrBefore(now, datePrecision)
                );
                past_radios.parent().addClass('text-muted');
                past_radios.prop('disabled', true);
            }
            return disableInput; // return the input that was specifically disabled, if any
        };

        // swap days
        let swapDaysModal = content.find("#swap-days-modal");
        let swapDaysLabels = swapDaysModal.find(".modal-body label");
        let swapDaysRadios = swapDaysLabels.find('input[name=target_day]');
        let updateSwapDaysSubmitButton = function () {
            updateSwapSubmitButton(swapDaysModal, 'target_day')
        };
        // handler to prep and open the modal
        content.find(".swap-days").on("click", function () {
            let originDay = this.dataset.dayid;
            let originRadio = updateSwapRadios(swapDaysLabels, swapDaysRadios, originDay, 'day');

            // Fill in label in the modal title
            swapDaysModal.find(".modal-title .day").text(jQuery.trim(originRadio.parent().text()));

            // Fill in the hidden form fields
            swapDaysModal.find("input[name=source_day]").val(originDay);

            updateSwapDaysSubmitButton();
            swapDaysModal.modal('show'); // show via JS so it won't open until it is initialized
        });
        swapDaysRadios.on("change", function () {updateSwapDaysSubmitButton()});

        // swap timeslot columns
        let swapTimeslotsModal = content.find('#swap-timeslot-col-modal');
        let swapTimeslotsLabels = swapTimeslotsModal.find(".modal-body label");
        let swapTimeslotsRadios = swapTimeslotsLabels.find('input[name=target_timeslot]');
        let updateSwapTimeslotsSubmitButton = function () {
            updateSwapSubmitButton(swapTimeslotsModal, 'target_timeslot');
        };
        // handler to prep and open the modal
        content.find('.swap-timeslot-col').on('click', function() {
            let roomGroup = this.closest('.room-group').dataset;
            updateSwapRadios(swapTimeslotsLabels, swapTimeslotsRadios, this.dataset.timeslotPk, 'minute');

            // show only options for this room group
            swapTimeslotsModal.find('.room-group').hide();
            swapTimeslotsModal.find('.room-group-' + roomGroup.index).show();

            // Fill in label in the modal title
            swapTimeslotsModal.find('.modal-title .origin-label').text(this.dataset.originLabel);

            // Fill in the hidden form fields
            swapTimeslotsModal.find('input[name="origin_timeslot"]').val(this.dataset.timeslotPk);
            swapTimeslotsModal.find('input[name="rooms"]').val(roomGroup.rooms);

            // Open the modal via JS so it won't open until it is initialized
            updateSwapTimeslotsSubmitButton();
            swapTimeslotsModal.modal('show');
        });
        swapTimeslotsRadios.on("change", function () {updateSwapTimeslotsSubmitButton()});
    }

    // hints for the current schedule

    function updateSessionConstraintViolations() {
        // do a sweep on sessions sorted by start time
        let scheduledSessions = [];

        sessions.each(function () {
            let timeslot = jQuery(this).closest(".timeslot");
            if (timeslot.length === 1) {
                scheduledSessions.push({
                    start: startMoment(timeslot),
                    end: endMoment(timeslot),
                    id: this.id.slice('session'.length),
                    element: jQuery(this),
                    timeslot: timeslot.get(0)
                });
            }
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
            let roomCapacity = jQuery(this).closest(".timeslots").data("roomcapacity");
            if (roomCapacity && this.dataset.attendees)
                jQuery(this).toggleClass("too-many-attendees", +this.dataset.attendees > +roomCapacity);
        });
    }

    function updateCurrentSchedulingHints() {
        updateSessionConstraintViolations();
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

        function extractId(e) {
            return e.id.slice("session".length);
        }

        function extractName(e) {
            let labelElement = e.querySelector(".session-label");
            return labelElement ? labelElement.innerHTML : '';
        }

        function extractParent(e) {
            let parentElement = e.querySelector(".session-parent");
            return parentElement ? parentElement.innerHTML : '';
        }

        function extractDuration(e) {
            return +e.dataset.duration;
        }

        function extractComments(e) {
            return e.querySelector(".session-info .comments") ? 0 : 1;
        }

        const keyFunctionMap = {
            name: [extractName, extractDuration, extractId],
            parent: [extractParent, extractName, extractDuration, extractId],
            duration: [extractDuration, extractParent, extractName, extractId],
            comments: [extractComments, extractParent, extractName, extractDuration, extractId]
        };
        let keyFunctions = keyFunctionMap[sortBy];

        let unassignedSessionsContainer = content.find(".unassigned-sessions .drop-target");

        let sortedSessions = sortArrayWithKeyFunctions(unassignedSessionsContainer.children(".session").toArray(), keyFunctions);
        for (let i = 0; i < sortedSessions.length; ++i)
            unassignedSessionsContainer.append(sortedSessions[i]);
    }

    content.find("select[name=sort_unassigned]").on("change click", function () {
        sortUnassigned();
    });

    sortUnassigned();

    // toggling visible sessions by session parents
    let sessionParentInputs = content.find(".session-parent-toggles input");

    function setSessionHidden(sess, hide) {
        sess.toggleClass('hidden-parent', hide);
        sess.prop('draggable', !hide);
    }

    function updateSessionParentToggling() {
        let checked = [];
        sessionParentInputs.filter(":checked").each(function () {
            checked.push(".parent-" + this.value);
        });

        setSessionHidden(sessions.not(".untoggleable").filter(checked.join(",")), false);
        setSessionHidden(sessions.not(".untoggleable").not(checked.join(",")), true);
    }

    sessionParentInputs.on("click", updateSessionParentToggling);
    updateSessionParentToggling();

    // toggling visible timeslots
    let timeslotGroupInputs = content.find("#timeslot-group-toggles-modal .modal-body input");
    function updateTimeslotGroupToggling() {
        let checked = [];
        timeslotGroupInputs.filter(":checked").each(function () {
            checked.push("." + this.value);
        });

        timeslots.filter(checked.join(",")).removeClass("hidden");
        timeslots.not(checked.join(",")).addClass("hidden");

        days.each(function () {
            jQuery(this).toggle(jQuery(this).find(".timeslot:not(.hidden)").length > 0);
        });
    }

    timeslotGroupInputs.on("click change", updateTimeslotGroupToggling);
    updateTimeslotGroupToggling();
    updatePastTimeslots();
    setInterval(updatePastTimeslots, 10 * 1000 /* ms */);

    // session info
    content.find(".session-info-container").on("mouseover", ".other-session", function (event) {
        sessions.filter("#session" + this.dataset.othersessionid).addClass("highlight");
    }).on("mouseleave", ".other-session", function (event) {
        sessions.filter("#session" + this.dataset.othersessionid).removeClass("highlight");
    });
});

