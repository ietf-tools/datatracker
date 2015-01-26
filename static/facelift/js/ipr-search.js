$(document).ready(function() {
    // hack the "All States" check box
    $("#id_state input[value!=all]").change(function(e) {
        if (this.checked) {
            $("#id_state input[value=all]").prop('checked',false);
        }
    });

    $("#id_state_0").change(function(e) {
        if (this.checked) {
            $("#id_state input[value!=all]").prop('checked',false);
        }
    });

    // make enter presses submit through the nearby button
    $("form.ipr-search input,select").keyup(function (e) {
        if (e.which == 13) {
            $(this).next('button[type=submit]').click();
            return false;
        } else {
            return true;
        }
    });
});
