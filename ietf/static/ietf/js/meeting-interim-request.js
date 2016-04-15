
var interimRequest = {
    // functions for Interim Meeting Request 
    init : function() {
        // get elements
        interimRequest.form = $(this);
        interimRequest.addButton = $('#add_session');
        interimRequest.faceToFace = $('#id_face_to_face');
        // bind functions
        $('.select2-field').select2();
        $('#add_session').click(interimRequest.addSession);
        $('.btn-delete').click(interimRequest.deleteSession);
        $('#id_face_to_face').change(interimRequest.toggleLocation);
        $('input[name="meeting_type"]').change(interimRequest.checkAddButton);
        $('input[name$="-duration"]').blur(interimRequest.calculateEndTime);
        $('input[name$="-time"]').blur(interimRequest.calculateEndTime);
        //$('input[name$="-time"]').blur(interimRequest.setUTC);
        $('input[name$="-time"]').blur(interimRequest.updateInfo);
        $('input[name$="-end_time"]').change(interimRequest.updateInfo);
        $('select[name$="-timezone"]').change(interimRequest.timezoneChange);
        // init
        interimRequest.faceToFace.each(interimRequest.toggleLocation);
        interimRequest.checkAddButton();
    },

    addSession : function() {
        //var templateData = interimRequest.sessionTemplate.clone();
        var template = interimRequest.form.find('.fieldset.template');
        var el = template.clone(true);
        var totalField = $('#id_form-TOTAL_FORMS');
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

        //if(interimRequest.faceToFace.prop('checked')){
            var first_session = $(".fieldset:first");
            el.find("input[name$='city']").val(first_session.find("input[name$='city']").val());
            el.find("select[name$='country']").val(first_session.find("select[name$='country']").val());
            el.find("select[name$='timezone']").val(first_session.find("select[name$='timezone']").val());
        //}

        if(meeting_type == 'multi-day'){
            el.find(".location").prop('disabled', true);
        }
        
        $('.btn-delete').removeClass("hidden");
    },

    updateInfo : function() {
        //var url = liaisonForm.form.data("ajaxInfoUrl");
        //alert('called update');
        var url = "/meeting/ajax/get-utc";
        var fieldset = $(this).parents(".fieldset");
        var time = $(this).val();
        var timezone_field = fieldset.find('[name$="timezone"]');
        var timezone = timezone_field.val();
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
        var duration = fieldset.find("input[name$='-duration']");
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
        //alert( d2 );
        //alert( end_time.attr("id") );
    },
    
    checkAddButton : function() {
        var meeting_type = $('input[name="meeting_type"]:checked').val();
        if(meeting_type == 'single'){
            interimRequest.addButton.hide();
        } else {
            interimRequest.addButton.show();
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
        //alert(utc.attr("id"));
    },
    
    timezoneChange : function() {
        //alert("tz change");
        var fieldset = $(this).parents(".fieldset");
        var start_time = fieldset.find("input[name$='-time']");
        var end_time = fieldset.find("input[name$='-end_time']");
        start_time.trigger('blur');
        end_time.trigger('change');
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
