
var interimRequest = {
    // functions for Interim Meeting Request 
    init : function() {
        interimRequest.form = $(this);
        $('.select2-field').select2();
        $('#id_face_to_face').change(interimRequest.toggleLocation);
        $('#id_face_to_face').each(interimRequest.toggleLocation)
    },

    toggleLocation : function() {
        if(this.checked){
            $("#id_city").prop('disabled', false);
            $("#id_country").prop('disabled', false);
            $("#id_timezone").prop('disabled', false);
        } else {
            $("#id_city").prop('disabled', true);
            $("#id_country").prop('disabled', true);
            $("#id_timezone").prop('disabled', true);
        }
    }
}

$(document).ready(function () {
    $('#interim-request-form').each(interimRequest.init);
});
