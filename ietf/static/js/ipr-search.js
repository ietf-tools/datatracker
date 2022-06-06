$(document)
    .ready(function () {
        // hack the "All States" check box
        $("#id_state")
            .addClass("list-inline");

        $("#id_state input[value!=all]")
            .on("change", function (e) {
                if (this.checked) {
                    $("#id_state input[value=all]")
                        .prop('checked', false);
                }
            });

        $("#id_state_0")
            .on("change", function (e) {
                if (this.checked) {
                    $("#id_state input[value!=all]")
                        .prop('checked', false);
                }
            });

        // make enter presses submit through the nearby button
        // FIXME: this seems to be broken
        $("form.ipr-search input,select")
            .on("keyup", function (e) {
                var submitButton = $(this)
                    .closest(".mb-3")
                    .find('button[type=submit]');
                if (e.which == 13 && submitButton.length > 0) {
                    submitButton.trigger("click");
                    return false;
                } else {
                    return true;
                }
            });
    });