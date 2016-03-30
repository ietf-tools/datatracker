
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
        $('#id_face_to_face').change(interimRequest.toggleLocation);
        $('input[name="meeting_type"]').change(interimRequest.checkAddButton);
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

        if(interimRequest.faceToFace.prop('checked')){
            var first_session = $(".fieldset:first");
            el.find("input[name$='city']").val(first_session.find("input[name$='city']").val());
            el.find("select[name$='country']").val(first_session.find("select[name$='country']").val());
            el.find("select[name$='timezone']").val(first_session.find("select[name$='timezone']").val());
        }

        if(meeting_type == 'multi-day'){
            el.find(".location").prop('disabled', true);
        }

    },

    checkAddButton : function() {
        var meeting_type = $('input[name="meeting_type"]:checked').val();
        if(meeting_type == 'single'){
            interimRequest.addButton.hide();
        } else {
            interimRequest.addButton.show();
        }
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
