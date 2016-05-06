
var interimRequest = {
    // functions for Interim Meeting Request 
    init : function() {
        // get elements
        interimRequest.form = $(this);
        interimRequest.addButton = $('#add_session');
        interimRequest.inPerson = $('#id_in_person');
        interimRequest.timezone = $('#id_time_zone');
        // bind functions
        $('.select2-field').select2();
        interimRequest.addButton.click(interimRequest.addSession);
        $('.btn-delete').click(interimRequest.deleteSession);
        interimRequest.inPerson.change(interimRequest.toggleLocation);
        $('input[name="meeting_type"]').change(interimRequest.meetingTypeChanged);
        $('input[name$="-requested_duration"]').blur(interimRequest.calculateEndTime);
        $('input[name$="-time"]').blur(interimRequest.calculateEndTime);
        $('input[name$="-time"]').blur(interimRequest.updateInfo);
        $('input[name$="-end_time"]').change(interimRequest.updateInfo);
        interimRequest.timezone.change(interimRequest.timezoneChange);
        // init
        interimRequest.inPerson.each(interimRequest.toggleLocation);
        interimRequest.checkAddButton();
        interimRequest.checkHelpText();
        $('input[name$="-time"]').each(interimRequest.calculateEndTime);
        $('input[name$="-time"]').each(interimRequest.updateInfo);
        //interimRequest.form.submit(interimRequest.onSubmit);
        //$('input[name$="-time"]').blur(interimRequest.setUTC);
    },

    addSession : function() {
        var template = interimRequest.form.find('.fieldset.template');
        var el = template.clone(true);
        var totalField = $('#id_session_set-TOTAL_FORMS');
        var total = +totalField.val();
        var meeting_type = $('input[name="meeting_type"]:checked').val();

        el.find(':input').each(function() {
            var name = $(this).attr('name').replace('-' + (total-1) + '-','-' + total + '-');
            var id = 'id_' + name;
            $(this).attr({'name': name, 'id': id}).val('');
        });

        el.find('label').each(function() {
            var newFor = $(this).attr('for').replace('-' + (total-1) + '-','-' + total + '-');
            $(this).attr('for', newFor);
        });

        ++total;

        totalField.val(total);

        template.before(el);
        el.removeClass("template");

        el.find(".select2-field").each(function () {
            setupSelect2Field($(this));
        });

        // copy field contents
        var first_session = $(".fieldset:first");
        el.find("input[name$='remote_instructions']").val(first_session.find("input[name$='remote_instructions']").val());
        
        $('.btn-delete').removeClass("hidden");
    },

    onSubmit : function() {
        // must remove required attribute from non visible fields
        var template = $(this).find(".template");
        //template.find('input,textarea,select').filter('[required]').prop('required',false);
        var x = template.find('input,textarea,select')
        alert(x.length);
        return true;
    },

    updateInfo : function() {
        // makes ajax call to server and sets UTC field
        var time = $(this).val();
        if(!time){
            return;
        }
        var url = "/meeting/ajax/get-utc";
        var fieldset = $(this).parents(".fieldset");
        var timezone = interimRequest.timezone.val();
        var name = $(this).attr("id") + "_utc";
        var utc = fieldset.find("#" + name);
        $.ajax({
            url: url,
            type: 'GET',
            cache: false,
            async: true,
            dataType: 'json',
            data: {time: time,
                   timezone: timezone},
            success: function(response){
                if (!response.error) {
                    utc.val(response.utc + " UTC");
                }
            }
        });
        return false;
    },


    calculateEndTime : function() {
        // gets called when either start_time or duration change
        var fieldset = $(this).parents(".fieldset");
        var start_time = fieldset.find("input[name$='-time']");
        var end_time = fieldset.find("input[name$='-end_time']");
        var duration = fieldset.find("input[name$='-requested_duration']");
        if(!start_time.val() || !duration.val()){
            return;
        }
        var start_values = start_time.val().split(":");
        var duration_values = duration.val().split(":");
        var d = new Date(2000,1,1,start_values[0],start_values[1]);
        var d1 = new Date(d.getTime() + (duration_values[0]*60*60*1000));
        var d2 = new Date(d1.getTime() + (duration_values[1]*60*1000));
        end_time.val(interimRequest.get_formatted_time(d2));
        end_time.trigger('change');
        //interimRequest.updateInfo(end_time);
    },
    
    checkAddButton : function() {
        var meeting_type = $('input[name="meeting_type"]:checked').val();
        if(meeting_type == 'single'){
            interimRequest.addButton.hide();
        } else {
            interimRequest.addButton.show();
        }
    },
    
    checkHelpText : function() {
        var meeting_type = $('input[name="meeting_type"]:checked').val();
        if(meeting_type == 'single'){
            $('.meeting-type-help').hide();
        } else if(meeting_type == 'multi-day') {
            $('.meeting-type-help').hide();
            $('.mth-multi').show();
        } else if(meeting_type == 'series') {
            $('.meeting-type-help').hide();
            $('.mth-series').show();
        }
    },
    
    checkInPerson : function() {
        var meeting_type = $('input[name="meeting_type"]:checked').val();
        if(meeting_type == 'series'){
            interimRequest.inPerson.prop('disabled', true);
            interimRequest.inPerson.prop('checked', false);
            interimRequest.toggleLocation();
        } else {
            interimRequest.inPerson.prop('disabled', false);
        }
    },

    get_formatted_time : function (d) {
        // returns time from Date object as HH:MM
        var minutes = d.getMinutes().toString();
        var hours = d.getHours().toString();
        return interimRequest.pad(hours) + ":" + interimRequest.pad(minutes);
    },
    
    deleteSession : function() {
        var fieldset = $(this).parents(".fieldset");
        fieldset.remove();
        var totalField = $('#id_form-TOTAL_FORMS');
        var total = +totalField.val();
        --total;
        totalField.val(total);
        if(total == 2){
            $(".btn-delete").addClass("hidden");
        }
    },
    
    get_formatted_utc_time : function (d) {
        // returns time from Date object as HH:MM
        var minutes = d.getUTCMinutes().toString();
        var hours = d.getUTCHours().toString();
        return interimRequest.pad(hours) + ":" + interimRequest.pad(minutes);
    },
    
    meetingTypeChanged : function () {
        interimRequest.checkAddButton();
        interimRequest.checkInPerson();
        interimRequest.checkHelpText();
    },
    
    pad : function(str) {
        // zero pads string 00
        if(str.length == 1){
            str = "0" + str;
        }
        return str;
    },
    
    setUTC : function() {
        var fieldset = $(this).parents(".fieldset");
        var values = $(this).val().split(":");
        var name = $(this).attr("id") + "_utc";
        var utc = fieldset.find("#" + name);
        var d = new Date(2000,1,1,values[0],values[1]);
        utc.val(interimRequest.get_formatted_utc_time(d) + " UTC");
    },
    
    timezoneChange : function() {
        $("input[name$='-time']").trigger('blur');
        $("input[name$='-end_time']").trigger('change');
    },
    
    toggleLocation : function() {
        if(this.checked){
            $(".location").prop('disabled', false);
        } else {
            $(".location").prop('disabled', true);
        }
    }
}

$(document).ready(function () {
    $('#interim-request-form').each(interimRequest.init);
});
