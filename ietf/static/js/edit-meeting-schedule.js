$(function () {
    'use strict';

    let schedEditor = $(".edit-meeting-schedule");
    /* Drag data stored via the drag event dataTransfer interface is only accessible on
     * dragstart and dragend events. Other drag events can see only the MIME types that have
     * data. Use a non-registered type to identify our session drags. Unregistered MIME
     * types are strongly discouraged by RFC6838, but we are not actually attempting to
     * exchange data with anything outside this script so that really does not apply. */
    const dnd_mime_type = 'text/x.session-drag';
    const meetingTimeZone = schedEditor.data('timezone');
    const lockSeconds = Number(schedEditor.data('lock-seconds') || 0);

    function reportServerError(xhr, textStatus, error) {
        let errorText = error || textStatus;
        if (xhr && xhr.responseText) {
            errorText += '\n\n' + xhr.responseText;
        }
        alert("Error: " + errorText);
    }

    function ajaxCall(action, data) {
        const ajaxData = { action: action };
        Object.assign(ajaxData, data);
        return jQuery.ajax({
            url: window.location.href,
            method: "post",
            timeout: 5 * 1000,
            data: ajaxData,
        });
    }

    /**
     * Time to treat as current time for computing whether to lock timeslots
     * @returns {*} Moment object equal to lockSeconds in the future
     */
    function effectiveNow() {
        return moment().add(lockSeconds, 'seconds');
    }

    let sessions = schedEditor.find(".session").not(".readonly");
    let sessionConstraints = sessions.find('.constraints > span');
    let timeslots = schedEditor.find(".timeslot");
    let timeslotLabels = schedEditor.find(".time-label");
    let swapDaysButtons = schedEditor.find('.swap-days');
    let swapTimeslotButtons = schedEditor.find('.swap-timeslot-col');
    let days = schedEditor.find(".day-flow .day");
    let officialSchedule = schedEditor.hasClass('official-schedule');
    let timeSlotTypeInputs = schedEditor.find('.timeslot-type-toggles input');
    let sessionPurposeInputs = schedEditor.find('.session-purpose-toggles input');
    let timeSlotGroupInputs = schedEditor.find("#timeslot-group-toggles-modal .modal-body .individual-timeslots input");
    let sessionParentInputs = schedEditor.find(".session-parent-toggles input");
    let sessionParentToggleAll = schedEditor.find(".session-parent-toggles .session-parent-toggle-all")
    const classes_to_hide = '.hidden-timeslot-group,.hidden-timeslot-type';

    // hack to work around lack of position sticky support in old browsers, see https://caniuse.com/#feat=css-sticky
    if (schedEditor.find(".scheduling-panel").css("position") !== "sticky") {
        schedEditor.find(".scheduling-panel").css("position", "fixed");
        schedEditor.css("padding-bottom", "14em");
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
            const timeslot = jQuery(this);
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
            showTimeSlotTypeIndicators(element.dataset.type);

            let sessionInfoContainer = schedEditor.find(".scheduling-panel .session-info-container");
            sessionInfoContainer.html(jQuery(element).find(".session-info").html());

            sessionInfoContainer.find("[data-bs-original-title]").tooltip();

            sessionInfoContainer.find(".time").text(jQuery(element).closest(".timeslot").data('scheduledatlabel'));

            sessionInfoContainer.find(".other-session").each(function () {
                let otherSessionElement = sessions.filter("#session" + this.dataset.othersessionid).first();
                let scheduledAt = otherSessionElement.closest(".timeslot").data('scheduledatlabel');
                let timeElement = jQuery(this).find(".time");

                otherSessionElement.addClass("other-session-selected");
                if (scheduledAt) {
                    timeElement.text(timeElement.data('scheduled').replace('{time}', scheduledAt));
                } else {
                    timeElement.text(timeElement.data('notscheduled'));
                }
            });
        } else {
            sessions.removeClass("selected");
            showConstraintHints();
            resetTimeSlotTypeIndicators();
            schedEditor.find(".scheduling-panel .session-info-container").html("");
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
     * Remove timeslot classes indicating timeslot type disagreement
     */
    function resetTimeSlotTypeIndicators() {
        timeslots.removeClass('wrong-timeslot-type');
    }

    /**
     * Add timeslot classes indicating timeslot type disagreement
     *
     * @param timeslot_type
     */
    function showTimeSlotTypeIndicators(timeslot_type) {
        timeslots.removeClass('wrong-timeslot-type');
        timeslots.filter('[data-type!="' + timeslot_type + '"]').addClass('wrong-timeslot-type');
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
        timeslots.filter(':not(.past)')
            .filter((_, ts) => !isFutureTimeslot(jQuery(ts), now))
            .addClass('past');

        // hide swap day/timeslot column buttons
        if (officialSchedule) {
            swapDaysButtons.filter(
                (_, elt) => parseISOTimestamp(elt.closest('*[data-start]').dataset.start).isSameOrBefore(now, 'day')
            ).hide();
            swapTimeslotButtons.filter(
                (_, elt) => parseISOTimestamp(elt.closest('*[data-start]').dataset.start).isSameOrBefore(now, 'minute')
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

    schedEditor.on("click", function (event) {
        if (!(
            jQuery(event.target).is('.session-info-container') ||
            jQuery(event.target).closest('.session-info-container').length > 0
        )) {
            selectSessionElement(null);
        }
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
        return event.originalEvent.dataTransfer.types.some(
          (item_type) => item_type.indexOf(dnd_mime_type) === 0
        );
    }

    /**
     * Get the session element being dragged
     *
     * @param event drag-related event
     */
    function getDraggedSession(event) {
        if (!isSessionDragEvent(event)) {
            return null;
        }
        const sessionId = event.originalEvent.dataTransfer.types[0].slice(dnd_mime_type.length);
        const sessionElements = sessions.filter("#" + sessionId);
        if (sessionElements.length > 0) {
            return sessionElements[0];
        }
        return null;
    }

    /**
     * Can a session be dropped in this element?
     *
     * Drop is allowed in drop-zones that are in unassigned-session or timeslot containers
     * not marked as 'past'.
     */
    function sessionDropAllowed(dropElement, sessionElement) {
        const relevant_parent = dropElement.closest('.timeslot, .unassigned-sessions');
        if (!relevant_parent || !sessionElement) {
            return false;
        }

        if (officialSchedule && relevant_parent.classList.contains('past')) {
            return false;
        }

        return !relevant_parent.dataset.type || (
            relevant_parent.dataset.type === sessionElement.dataset.type
        );
    }

    if (!schedEditor.find(".edit-grid").hasClass("read-only")) {
        // dragging
        sessions.on("dragstart", function (event) {
            if (canEditSession(this)) {
                /* Bit of a hack here - per the w3c drag and drop spec, the data being dragged
                 * and dropped are only available during dragstart and drop events. Otherwise,
                 * only their count and type are guaranteed to be available. (See
                 * https://www.w3.org/TR/2011/WD-html5-20110113/dnd.html#drag-data-store-mode)
                 * To work around this, append the sessionId to the dnd_mime_type in the type we
                 * report for our event. The event handlers can then pull it out when needed.
                 * (At least Chrome v106 breaks if we try to peek at the payload.)
                 */
                event.originalEvent.dataTransfer.setData(dnd_mime_type + this.id, this.id);
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
        let dropElements = schedEditor.find(".timeslot .drop-target,.unassigned-sessions .drop-target");
        dropElements.on('dragenter', function (event) {
            if (sessionDropAllowed(this, getDraggedSession(event))) {
                event.preventDefault(); // default action is signalling that this is not a valid target
                jQuery(this).parent().addClass("dropping");
            }
        });

        dropElements.on('dragover', function (event) {
            // we don't actually need this event, except we need to signal
            // that this is a valid drop target, by cancelling the default
            // action
            if (sessionDropAllowed(this, getDraggedSession(event))) {
                event.preventDefault();
            }
        });

        dropElements.on('dragleave', function (event) {
            // skip dragleave events if they are to children
            const leaving_child = event.originalEvent.currentTarget.contains(event.originalEvent.relatedTarget);
            if (!leaving_child && sessionDropAllowed(this, getDraggedSession(event))) {
                jQuery(this).parent().removeClass('dropping');
            }
        });

        dropElements.on('drop', function (event) {
            let dropElement = jQuery(this);

            const sessionElement = getDraggedSession(event);
            if (!sessionElement) {
                // not drag event or not from a session we recognize
                dropElement.parent().removeClass("dropping");
                return;
            }

            if (!sessionDropAllowed(this, sessionElement)) {
                dropElement.parent().removeClass("dropping"); // just in case
                return; // drop not allowed
            }

            event.preventDefault(); // prevent opening as link

            let dragParent = jQuery(sessionElement).parent();
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
                if (response.tombstone) {
                    dragParent.append(response.tombstone);
                }

                updateCurrentSchedulingHints();
                if (dropParent.hasClass("unassigned-sessions")) {
                    sortUnassigned();
                }
            }

            if (dropParent.hasClass("unassigned-sessions")) {
                ajaxCall(
                    "unassign",
                    { session: sessionElement.id.slice('session'.length) }
                ).fail(failHandler)
                    .done(done);
            } else {
                ajaxCall(
                    "assign",
                    {
                        session: sessionElement.id.slice("session".length),
                        timeslot: dropParent.attr("id").slice("timeslot".length)
                    }
                ).fail(failHandler)
                    .done(done);
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
            labels.removeClass('text-body-secondary');
            radios.prop('disabled', false);
            radios.prop('checked', false);
            // disable the input requested by value
            let disableInput = radios.filter('[value="' + disableValue + '"]');
            if (disableInput) {
                disableInput.parent().addClass('text-body-secondary');
                disableInput.prop('disabled', true);
            }
            if (officialSchedule) {
                // disable any that have passed
                const now=effectiveNow();
                const past_radios = radios.filter(
                    (_, radio) => parseISOTimestamp(radio.closest('*[data-start]').dataset.start).isSameOrBefore(now, datePrecision)
                );
                past_radios.parent().addClass('text-body-secondary');
                past_radios.prop('disabled', true);
            }
            return disableInput; // return the input that was specifically disabled, if any
        };

        // swap days
        let swapDaysModal = schedEditor.find("#swap-days-modal");
        let swapDaysLabels = swapDaysModal.find(".modal-body label");
        let swapDaysRadios = swapDaysLabels.find('input[name=target_day]');
        let updateSwapDaysSubmitButton = function () {
            updateSwapSubmitButton(swapDaysModal, 'target_day');
        };
        // handler to prep and open the modal
        schedEditor.find(".swap-days").on("click", function () {
            let originDay = this.dataset.dayid;
            let originRadio = updateSwapRadios(swapDaysLabels, swapDaysRadios, originDay, 'day');

            // Fill in label in the modal title
            swapDaysModal.find(".modal-title .day").text(originRadio.parent().text().trim());

            // Fill in the hidden form fields
            swapDaysModal.find("input[name=source_day]").val(originDay);

            updateSwapDaysSubmitButton();
            swapDaysModal.modal('show'); // show via JS so it won't open until it is initialized
        });
        swapDaysRadios.on("change", function () {updateSwapDaysSubmitButton();});

        // swap timeslot columns
        let swapTimeslotsModal = schedEditor.find('#swap-timeslot-col-modal');
        let swapTimeslotsLabels = swapTimeslotsModal.find(".modal-body label");
        let swapTimeslotsRadios = swapTimeslotsLabels.find('input[name=target_timeslot]');
        let updateSwapTimeslotsSubmitButton = function () {
            updateSwapSubmitButton(swapTimeslotsModal, 'target_timeslot');
        };
        // handler to prep and open the modal
        schedEditor.find('.swap-timeslot-col').on('click', function() {
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
        swapTimeslotsRadios.on("change", function () {updateSwapTimeslotsSubmitButton();});
    }

    // hints for the current schedule

    /** Find all pairs of overlapping intervals
     *
     * @param data Array of arbitrary interval-like objects with 'start' and 'end' properties
     * @returns Map from data item index to a list of overlapping data item indexes
     */
    function findOverlappingIntervals(data) {
        const overlaps = {}; // results
        // Build ordered lists of start/end times, keeping track of the original index for each item
        const startIndexes = data.map((d, i) => ({time: d.start, index: i}));
        startIndexes.sort((a, b) => (b.time - a.time)); // sort reversed
        const endIndexes = data.map((d, i) => ({time: d.end, index: i}));
        endIndexes.sort((a, b) => (b.time - a.time)); // sort reversed

        // items are sorted in reverse, so pop() will get the earliest item from each list
        let nextStart = startIndexes.pop();
        let nextEnd = endIndexes.pop();
        const openIntervalIndexes = [];
        while (nextStart && nextEnd) {
            if (nextStart.time < nextEnd.time) {
                // an interval opened - it overlaps all open intervals and all open intervals overlap it
                for (const intervalIndex of openIntervalIndexes) {
                    overlaps[intervalIndex].push(nextStart.index);
                }
                overlaps[nextStart.index] = [...openIntervalIndexes]; // make a copy of the open list
                openIntervalIndexes.push(nextStart.index);
                nextStart = startIndexes.pop();
            } else {
                // an interval closed - remove its index from the list of open intervals
                openIntervalIndexes.splice(openIntervalIndexes.indexOf(nextEnd.index), 1);
                nextEnd = endIndexes.pop();
            }
        }
        return overlaps;
    }

    function updateSessionConstraintViolations() {
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

        // helper function to mark constraint violations
        const markSessionConstraintViolations = function (sess, currentlyOpen) {
            sess.element.find(".constraints > span").each(function() {
                let sessionIds = this.dataset.sessions;

                let violated = sessionIds && sessionIds.split(",").filter(function (v) {
                    return (
                        v !== sess.id &&
                        v in currentlyOpen &&
                        // ignore errors within the same timeslot
                        // under the assumption that the sessions
                        // in the timeslot happen sequentially
                        sess.timeslot !== currentlyOpen[v].timeslot
                    );
                }).length > 0;

                jQuery(this).toggleClass("violated-hint", violated);
            });
        };

        // now go through the sessions and mark constraint violations
        const overlaps = findOverlappingIntervals(scheduledSessions);
        for (const index in overlaps) {
            const currentlyOpen = {};
            for (const overlapIndex of overlaps[index]) {
                const otherSess = scheduledSessions[overlapIndex];
                currentlyOpen[otherSess.id] = otherSess;
            }
            markSessionConstraintViolations(scheduledSessions[index], currentlyOpen);
        }
    }

    function updateTimeSlotDurationViolations() {
        timeslots.each(function () {
            const sessionsInSlot = Array.from(this.getElementsByClassName('session'));
            const requiredDuration = Math.max(sessionsInSlot.map(elt => Number(elt.dataset.duration)));
            this.classList.toggle('overfull', requiredDuration > Number(this.dataset.duration));
        });
    }

    function updateAttendeesViolations() {
        sessions.each(function () {
            let roomCapacity = jQuery(this).closest(".timeslots").data("roomcapacity");
            if (roomCapacity && this.dataset.attendees) {
                jQuery(this).toggleClass("too-many-attendees", +this.dataset.attendees > +roomCapacity);
            }
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

                if (ai > bi) {
                    return 1;
                } else if (ai < bi) {
                    return -1;
                }
            }

            return 0;
        }

        let arrayWithSortKeys = array.map(function (a) {
            let res = [a];
            for (let i = 0; i < keyFunctions.length; ++i) {
                res.push(keyFunctions[i](a));
            }
            return res;
        });

        arrayWithSortKeys.sort(compareArrays);

        return arrayWithSortKeys.map(function (l) {
            return l[0];
        });
    }

    function sortUnassigned() {
        let sortBy = schedEditor.find("select[name=sort_unassigned]").val();

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

        let unassignedSessionsContainer = schedEditor.find(".unassigned-sessions .drop-target");

        let sortedSessions = sortArrayWithKeyFunctions(unassignedSessionsContainer.children(".session").toArray(), keyFunctions);
        for (let i = 0; i < sortedSessions.length; ++i) {
            unassignedSessionsContainer.append(sortedSessions[i]);
        }
    }

    schedEditor.find("select[name=sort_unassigned]").on("change click", function () {
        sortUnassigned();
    });

    sortUnassigned();

    // toggling visible sessions by session parents

    function setSessionHiddenParent(sess, hide) {
        sess.toggleClass('hidden-parent', hide);
        sess.prop('draggable', !hide);
    }

    function updateSessionParentToggling() {
        let checked = [];
        sessionParentInputs.filter(":checked").each(function () {
            checked.push(".parent-" + this.value);
        });

        setSessionHiddenParent(sessions.not(".untoggleable-by-parent").filter(checked.join(",")), false);
        setSessionHiddenParent(sessions.not(".untoggleable-by-parent").not(checked.join(",")), true);
    }

    sessionParentInputs.on("click", updateSessionParentToggling);
    updateSessionParentToggling();

    // Toggle _all_ session parents
    function toggleAllSessionParents() {
        if (sessionParentInputs.filter(":checked").length < sessionParentInputs.length) {
            sessionParentInputs.prop("checked", true);
        } else {
            sessionParentInputs.prop("checked", false);
        }
        updateSessionParentToggling();
    }
    sessionParentToggleAll.on("click", toggleAllSessionParents);

    // Toggling timeslot types
    function updateTimeSlotTypeToggling() {
        const checkedTypes = jQuery.map(timeSlotTypeInputs.filter(":checked"), elt => elt.value);
        const checkedSelectors = checkedTypes.map(t => '[data-type="' + t + '"]').join(",");

        sessions.filter(checkedSelectors).removeClass('hidden-timeslot-type');
        sessions.not(checkedSelectors).addClass('hidden-timeslot-type');
        timeslots.filter(checkedSelectors).removeClass('hidden-timeslot-type');
        timeslots.not(checkedSelectors).addClass('hidden-timeslot-type');
        updateGridVisibility();
        return checkedTypes;
    }

    function updateTimeSlotTypeTogglingAndSave() {
        const checkedTypes = updateTimeSlotTypeToggling();
        ajaxCall('updateview', {enabled_timeslot_types: checkedTypes});
    }

    // Toggling session purposes
    function updateSessionPurposeToggling() {
        let checked = [];
        sessionPurposeInputs.filter(":checked").each(function () {
            checked.push(".purpose-" + this.value);
        });

        sessions.filter(checked.join(",")).removeClass('hidden-purpose');
        sessions.not(checked.join(",")).addClass('hidden-purpose');
    }

    if (timeSlotTypeInputs.length > 0) {
        timeSlotTypeInputs.on("change", updateTimeSlotTypeTogglingAndSave);
        updateTimeSlotTypeToggling();
        schedEditor.find('#timeslot-type-toggles-modal .timeslot-type-toggles .select-all')
            .get(0)
            .addEventListener(
                'click',
                function() {
                    timeSlotTypeInputs.prop('checked', true);
                    updateTimeSlotTypeTogglingAndSave();
                });
        schedEditor.find('#timeslot-type-toggles-modal .timeslot-type-toggles .clear-all')
            .get(0)
            .addEventListener(
                'click',
                function() {
                    timeSlotTypeInputs.prop('checked', false);
                    updateTimeSlotTypeTogglingAndSave();
                });
    }

    if (sessionPurposeInputs.length > 0) {
        sessionPurposeInputs.on("change", updateSessionPurposeToggling);
        updateSessionPurposeToggling();
        schedEditor.find('#session-toggles-modal .select-all')
            .get(0)
            .addEventListener(
                'click',
                function() {
                    sessionPurposeInputs.not(':disabled').prop('checked', true);
                    updateSessionPurposeToggling();
                });
        schedEditor.find('#session-toggles-modal .clear-all')
            .get(0)
            .addEventListener(
                'click',
                function() {
                    sessionPurposeInputs.not(':disabled').prop('checked', false);
                    updateSessionPurposeToggling();
                });
    }

    // toggling visible timeslots
    function updateTimeSlotGroupToggling() {
        let checked = [];
        timeSlotGroupInputs.filter(":checked").each(function () {
            checked.push("." + this.value);
        });

        timeslots.filter(checked.join(",")).removeClass("hidden-timeslot-group");
        timeslots.not(checked.join(",")).addClass("hidden-timeslot-group");
        updateGridVisibility();
    }

    function updateSessionPurposeOptions() {
        sessionPurposeInputs.each((_, purpose_input) => {
            if (sessions
                .filter('.purpose-' + purpose_input.value)
                .not('.hidden')
                .length === 0) {
                purpose_input.setAttribute('disabled', 'disabled');
                purpose_input.closest('.session-purpose-toggle').classList.add('text-body-secondary');
            } else {
                purpose_input.removeAttribute('disabled');
                purpose_input.closest('.session-purpose-toggle').classList.remove('text-body-secondary');
            }
        });
    }

    /**
     * Hide timeslot toggles for hidden timeslots
     */
    function updateTimeSlotOptions() {
        timeSlotGroupInputs.each((_, timeslot_input) => {
            if (timeslots
                .filter('.' + timeslot_input.value)
                .not('.hidden-timeslot-type')
                .length === 0) {
                timeslot_input.setAttribute('disabled', 'disabled');
            } else {
                timeslot_input.removeAttribute('disabled');
            }
        });
    }

    /**
     * Make timeslots visible/invisible/hidden
     *
     * Responsible for final determination of whether a timeslot is visible, invisible, or hidden.
     */
    function updateTimeSlotVisibility() {
        const tsToShow = timeslots.not(classes_to_hide);
        tsToShow.removeClass('hidden');
        tsToShow.show();
        const tsToHide = timeslots.filter(classes_to_hide);
        tsToHide.addClass('hidden');
        tsToHide.hide();
    }

    /**
     * Make sessions visible/invisible/hidden
     *
     * Responsible for final determination of whether a session is visible or hidden.
     */
    function updateSessionVisibility() {
        const sessToShow = sessions.not(classes_to_hide);
        sessToShow.removeClass('hidden');
        sessToShow.show();
        const sessToHide = sessions.filter(classes_to_hide);
        sessToHide.addClass('hidden');
        sessToHide.hide();
    }

    /**
     * Make day / time headers visible / hidden to match visible grid contents
     */
    function updateHeaderVisibility() {
        days.each(function () {
            jQuery(this).toggle(jQuery(this).find(".timeslot").not(".hidden").length > 0);
        });

        const rgs = schedEditor.find('.day-flow .room-group');
        rgs.each(function (index, roomGroup) {
            const headerLabels = jQuery(roomGroup).find('.time-header .time-label');
            const rgTimeslots = jQuery(roomGroup).find('.timeslot');
            headerLabels.each(function(index, label) {
                jQuery(label).toggle(
                    rgTimeslots
                        .filter('[data-start="' + label.dataset.start + '"][data-end="' + label.dataset.end + '"]')
                        .not('.hidden')
                        .length > 0
                );
            });
        });
    }

    /**
     * Update visibility of room rows
     */
    function updateRoomVisibility() {
        const tsContainers = { toShow: [], toHide: [] };
        const roomGroups = { toShow: [], toHide: [] };
        // roomsWithVisibleSlots is an array of room IDs that have at least one visible timeslot
        let roomsWithVisibleSlots = schedEditor.find('.day-flow .timeslots')
            .has('.timeslot:not(.hidden)')
            .map((_, e) => e.dataset.roomId).get();
        roomsWithVisibleSlots = [...new Set(roomsWithVisibleSlots)]; // unique-ify by converting to Set and back

        /* The "timeslots" class identifies elements (now and probably always <div>s) that are containers (i.e.,
         * parents) of timeslots (elements with the "timeslot" class). Sort these containers based on whether
         * their room has at least one timeslot visible - if so, we will show it, if not it will be hidden.
         * This will hide containers both in the day-flow and room label sections, so it will hide the room
         * labels for rooms with no visible timeslots. */
        schedEditor.find('.timeslots').each((_, e) => {
            if (roomsWithVisibleSlots.indexOf(e.dataset.roomId) === -1) {
                tsContainers.toHide.push(e);
            } else {
                tsContainers.toShow.push(e);
            }
        });

        /* Now check whether each room group has any rooms not being hidden. If not, entirely hide the
         * room group so that all its headers, etc, do not take up space. */
        schedEditor.find('.room-group').each((_, e) => {
            if (jQuery(e).has(tsContainers.toShow).length > 0) {
                roomGroups.toShow.push(e);
            } else {
                roomGroups.toHide.push(e);
            }
        });
        jQuery(roomGroups.toShow).show();
        jQuery(roomGroups.toHide).hide();
        jQuery(tsContainers.toShow).show();
        jQuery(tsContainers.toHide).hide();
    }

    /**
     * Update visibility of UI elements
     *
     * Call this after changing 'hidden-*' classes on timeslots
     */
    function updateGridVisibility() {
        updateTimeSlotVisibility();
        updateSessionVisibility();
        updateHeaderVisibility();
        updateRoomVisibility();
        updateTimeSlotOptions();
        updateSessionPurposeOptions();
        schedEditor.find('div.edit-grid').removeClass('hidden');
    }

    timeSlotGroupInputs.on("click change", updateTimeSlotGroupToggling);
    schedEditor.find('#timeslot-group-toggles-modal .timeslot-group-buttons .select-all')
        .get(0)
        .addEventListener(
            'click',
            function() {
                timeSlotGroupInputs.not(':disabled').prop('checked', true);
                updateTimeSlotGroupToggling();
            });
    schedEditor.find('#timeslot-group-toggles-modal .timeslot-group-buttons .clear-all')
        .get(0)
        .addEventListener(
            'click',
            function() {
                timeSlotGroupInputs.not(':disabled').prop('checked', false);
                updateTimeSlotGroupToggling();
            });

    updateTimeSlotGroupToggling();
    updatePastTimeslots();
    setInterval(updatePastTimeslots, 10 * 1000 /* ms */);

    // session info
    schedEditor.find(".session-info-container")
        .on("mouseover", ".other-session", function () {
            sessions.filter("#session" + this.dataset.othersessionid)
                .addClass("highlight");
        })
        .on("mouseleave", ".other-session", function () {
            sessions.filter("#session" + this.dataset.othersessionid).removeClass("highlight");
        });
});
