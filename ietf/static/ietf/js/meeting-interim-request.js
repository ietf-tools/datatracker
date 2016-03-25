
var interimRequest = {
    // functions for Interim Meeting Request 
    init : function() {
        interimRequest.form = $(this);
        //interimRequest.sessionTemplate = interimRequest.form.find('.fieldset.template');
        $('.select2-field').select2();
        $('#add_session').click(interimRequest.addSession);
        $('#id_face_to_face').change(interimRequest.toggleLocation);
        $('#id_face_to_face').each(interimRequest.toggleLocation);
    },

    addSession : function() {
        //var templateData = interimRequest.sessionTemplate.clone();
        var template = interimRequest.form.find('.fieldset.template');
        var el = template.clone(true);
        var totalField = $('#id_form-TOTAL_FORMS');
        var total = +totalField.val();

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
