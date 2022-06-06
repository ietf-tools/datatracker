const interimRequest = (function() {
    'use strict';
    return {
        // functions for Interim Meeting Request
        init: function () {
            // get elements
            interimRequest.form = $(this);
            interimRequest.addButton = $('#add_session');
            interimRequest.inPerson = $('#id_in_person');
            interimRequest.timezone = $('#id_time_zone');
            interimRequest.addButton.on("click", interimRequest.addSession);
            $('.btn-delete')
                .on("click", interimRequest.deleteSession);
            interimRequest.inPerson.on("change", interimRequest.toggleLocation);
            $('input[name="meeting_type"]')
                .on("change", interimRequest.meetingTypeChanged);
            $('input[name$="-requested_duration"]')
                .on("blur", interimRequest.calculateEndTime);
            const timeInput = $('input[name$="-time"]');
            timeInput.on("blur", interimRequest.calculateEndTime);
            timeInput.on("blur", interimRequest.updateInfo);
            $('input[name$="-end_time"]')
                .prop('disabled', true)
                .on("change", interimRequest.updateInfo);
            interimRequest.timezone.on("change", interimRequest.timezoneChange);
            // init
            interimRequest.inPerson.each(interimRequest.toggleLocation);
            interimRequest.checkAddButton();
            interimRequest.initTimezone();
            timeInput.each(interimRequest.calculateEndTime);
            timeInput.each(interimRequest.updateInfo);
            const remoteParticipations = $('select[id$="-remote_participation"]');
            remoteParticipations.on(
                'change',
                evt => interimRequest.updateRemoteInstructionsVisibility(evt.target)
            );
            remoteParticipations.each((index, elt) => interimRequest.updateRemoteInstructionsVisibility(elt));
        },

        addSession: function () {
            const template = interimRequest.form.find('.fieldset.template');
            const el = template.clone(true);
            const totalField = $('#id_session_set-TOTAL_FORMS');
            let total = +totalField.val();
            // var meeting_type = $('input[name="meeting_type"]:checked').val();

            // increment formset counter
            template.find(':input')
                .each(function () {
                    const name = $(this)
                        .attr('name')
                        .replace('-' + (total - 1) + '-', '-' + total + '-');
                    const id = 'id_' + name;
                    $(this)
                        .attr({ name: name, id: id })
                        .val('');
                });

            template.find('label')
                .each(function () {
                    const newFor = $(this)
                        .attr('for')
                        .replace('-' + (total - 1) + '-', '-' + total + '-');
                    $(this)
                        .attr('for', newFor);
                });

            template.find('div.utc-time')
                .each(function () {
                    const newId = $(this)
                        .attr('id')
                        .replace('-' + (total - 1) + '-', '-' + total + '-');
                    $(this)
                        .attr('id', newId);
                });

            ++total;

            totalField.val(total);

            template.before(el);
            el.removeClass("template d-none");

            // copy field contents
            const first_session = $(".fieldset:first");
            el.find("input[name$='remote_instructions']")
                .val(first_session.find("input[name$='remote_instructions']")
                    .val());

            $('.btn-delete')
                .removeClass("d-none");
        },

        updateInfo: function () {
            // makes ajax call to server and sets UTC field
            const time = $(this)
                .val();
            if (!time) {
                return;
            }
            const url = "/meeting/ajax/get-utc";
            const fieldset = $(this)
                .parents(".fieldset");
            const date = fieldset.find("input[name$='-date']")
                .val();
            const timezone = interimRequest.timezone.val();
            const name = $(this)
                .attr("id") + "_utc";
            const utc = fieldset.find("#" + name);
            //console.log(name,utc.attr("id"));
            $.ajax({
                url: url,
                type: 'GET',
                cache: false,
                async: true,
                dataType: 'json',
                data: {
                    date: date,
                    time: time,
                    timezone: timezone
                },
                success: function (response) {
                    if (!response.error && response.html) {
                        utc.html(response.html);
                    }
                }
            });
            return false;
        },

        calculateEndTime: function () {
            // gets called when either start_time or duration change
            const fieldset = $(this)
                .parents(".fieldset");
            const start_time = fieldset.find("input[name$='-time']");
            const end_time = fieldset.find("input[name$='-end_time']");
            const duration = fieldset.find("input[name$='-requested_duration']");
            if (!start_time.val() || !duration.val()) {
                return;
            }
            const start_values = start_time.val()
                .split(":");
            const duration_values = duration.val()
                .split(":");
            const d = new Date(2000, 1, 1, start_values[0], start_values[1]);
            const d1 = new Date(d.getTime() + (duration_values[0] * 60 * 60 * 1000));
            const d2 = new Date(d1.getTime() + (duration_values[1] * 60 * 1000));
            end_time.val(interimRequest.get_formatted_time(d2));
            end_time.trigger('change');
        },

        checkAddButton: function () {
            const meeting_type = $('input[name="meeting_type"]:checked')
                .val();
            if (meeting_type === 'single') {
                interimRequest.addButton.addClass("d-none");
            } else {
                interimRequest.addButton.removeClass("d-none");
            }
        },

        checkInPerson: function () {
            const meeting_type = $('input[name="meeting_type"]:checked')
                .val();
            if (meeting_type === 'series') {
                interimRequest.inPerson.prop('disabled', true);
                interimRequest.inPerson.prop('checked', false);
                interimRequest.toggleLocation();
            } else {
                interimRequest.inPerson.prop('disabled', false);
            }
        },

        initTimezone: function () {
            if (interimRequest.isEditView()) {
                // Don't set timezone in edit view, already set
                return true;
            }

            if (window.Intl && typeof window.Intl === "object") {
                const tzname = Intl.DateTimeFormat()
                    .resolvedOptions()
                    .timeZone;
                if ($('#id_time_zone option[value="' + tzname + '"]')
                    .length > 0) {
                    $('#id_time_zone')
                        .val(tzname);
                }
            }
        },

        get_formatted_time: function (d) {
            // returns time from Date object as HH:MM
            const minutes = d.getMinutes()
                .toString();
            const hours = d.getHours()
                .toString();
            return interimRequest.pad(hours) + ":" + interimRequest.pad(minutes);
        },

        deleteSession: function () {
            const fieldset = $(this)
                .parents(".fieldset");
            fieldset.remove();
            const totalField = $('#id_form-TOTAL_FORMS');
            let total = +totalField.val();
            --total;
            totalField.val(total);
            if (total === 2) {
                $(".btn-delete")
                    .addClass("d-none");
            }
        },

        isEditView: function () {
            // Called on init, returns true if editing existing meeting request
            return !!$('#id_session_set-0-date').val();
        },

        meetingTypeChanged: function () {
            interimRequest.checkAddButton();
            interimRequest.checkInPerson();
        },

        pad: function (str) {
            // zero pads string 00
            if (str.length === 1) {
                str = "0" + str;
            }
            return str;
        },

        timezoneChange: function () {
            $("input[name$='-time']")
                .trigger('blur');
            $("input[name$='-end_time']")
                .trigger('change');
        },

        toggleLocation: function () {
            if (this.checked) {
                $(".location")
                    .prop('disabled', false);
            } else {
                $(".location")
                    .prop('disabled', true);
            }
        },

        updateRemoteInstructionsVisibility : function(elt) {
            const sessionSetPrefix = elt.id.replace('-remote_participation', '');
            const remoteInstructionsId = sessionSetPrefix + '-remote_instructions';
            const remoteInstructions = $('#' + remoteInstructionsId);

            switch (elt.value) {
            case 'meetecho':
                remoteInstructions.closest('.row').hide();
                break;

            default:
                remoteInstructions.closest('.row').show();
                break;
            }
        }
    };
})();

$(function () {
    'use strict';
    $('#interim-request-form').each(interimRequest.init);
});