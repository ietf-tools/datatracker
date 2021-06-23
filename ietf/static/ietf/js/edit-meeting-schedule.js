jQuery(document).ready(function () {
    let content = jQuery(".edit-meeting-schedule");

    function reportServerError(xhr, textStatus, error) {
        let errorText = error || textStatus;
        if (xhr && xhr.responseText)
            errorText += "\n\n" + xhr.responseText;
        alert("Error: " + errorText);
    }

    let sessions = content.find(".session").not(".readonly");
    let timeslots = content.find(".timeslot");
    let timeslotLabels = content.find(".time-label");
    let days = content.find(".day-flow .day");

    // hack to work around lack of position sticky support in old browsers, see https://caniuse.com/#feat=css-sticky
    if (content.find(".scheduling-panel").css("position") != "sticky") {
        content.find(".scheduling-panel").css("position", "fixed");
        content.css("padding-bottom", "14em");
    }

    function findTimeslotsOverlapping(intervals) {
        let res = [];

        timeslots.each(function () {
            var timeslot = jQuery(this);
            let start = timeslot.data("start");
            let end = timeslot.data("end");

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

    function showConstraintHints(selectedSession) {
        let sessionId = selectedSession ? selectedSession.id.slice("session".length) : null;
        // hints on the sessions
        sessions.find(".constraints > span").each(function () {
            let wouldViolate = false;
            let applyChange = true;
            if (sessionId) {
                let sessionIds = this.dataset.sessions;
                if (!sessionIds) {
                    applyChange = False;
                } else {
                    wouldViolate = sessionIds.split(",").indexOf(sessionId) !== -1;
                }
            }

            if (applyChange) {
                setSessionWouldViolate(this, wouldViolate);
            }
        });

        // hints on timeslots
        resetTimeslotsWouldViolate();
        if (selectedSession) {
            let intervals = [];
            timeslots.filter(":has(.session .constraints > span.would-violate-hint)").each(function () {
                intervals.push([this.dataset.start, this.dataset.end]);
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


    if (!content.find(".edit-grid").hasClass("read-only")) {
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
        let dropElements = content.find(".timeslot .drop-target,.unassigned-sessions .drop-target");
        dropElements.on('dragenter', function (event) {
            if ((event.originalEvent.dataTransfer.getData("text/plain") || "").slice(0, "session".length) != "session")
                return;

            event.preventDefault(); // default action is signalling that this is not a valid target
            jQuery(this).parent().addClass("dropping");
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

            jQuery(this).parent().removeClass("dropping");
        });

        dropElements.on('drop', function (event) {
            let dropElement = jQuery(this);

            let sessionId = event.originalEvent.dataTransfer.getData("text/plain");
            if ((event.originalEvent.dataTransfer.getData("text/plain") || "").slice(0, "session".length) != "session") {
                dropElement.parent().removeClass("dropping");
                return;
            }

            let sessionElement = sessions.filter("#" + sessionId);
            if (sessionElement.length == 0) {
                dropElement.parent().removeClass("dropping");
                return;
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
        let updateSwapRadios = function (labels, radios, disableValue) {
          labels.removeClass('text-muted');
          radios.prop('disabled', false);
          radios.prop('checked', false);
          let disableInput = radios.filter('[value="' + disableValue + '"]');
          if (disableInput) {
              disableInput.parent().addClass('text-muted');
              disableInput.prop('disabled', true);
          }
          return disableInput; // return the input that was disabled, if any
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
            let originRadio = updateSwapRadios(swapDaysLabels, swapDaysRadios, originDay);

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
            updateSwapRadios(swapTimeslotsLabels, swapTimeslotsRadios, this.dataset.timeslotPk)

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

    // session info
    content.find(".session-info-container").on("mouseover", ".other-session", function (event) {
        sessions.filter("#session" + this.dataset.othersessionid).addClass("highlight");
    }).on("mouseleave", ".other-session", function (event) {
        sessions.filter("#session" + this.dataset.othersessionid).removeClass("highlight");
    });
});

