$(document)
    .ready(function () {
        // hack the "All States" check box
        $("#id_state .form-check")
            .addClass("form-check-inline");

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

        $("form.ipr-search button[type=submit]")
            .on("click", function (e) {
                const value = $(e.target)
                    .attr("value");
                $("form.ipr-search input[name=submit]")
                    .attr("value", value);
            });

        // make enter presses submit through the nearby button
        $("form.ipr-search input")
            .on("keydown", function (e) {
                if (e.key != "Enter") {
                    return;
                }
                e.preventDefault();
                $(this)
                    .closest(".input-group")
                    .find('button[type=submit]')
                    .trigger("click");
            });
    });
