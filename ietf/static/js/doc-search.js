$(document)
    .ready(function () {
        // search form
        var form = $("#search_form");

        function anyAdvancedActive() {
            var advanced = false;
            var by = form.find("input[name=by]:checked");

            if (by.length > 0) {
                by.closest(".search_field")
                    .find("input,select")
                    .not("input[name=by]")
                    .each(function () {
                        if (String.prototype.trim(this.value)) {
                            advanced = true;
                        }
                    });
            }

            var additional_doctypes = form.find("input.advdoctype:checked");
            if (additional_doctypes.length > 0) {
                advanced = true;
            }
            return advanced;
        }

        function toggleSubmit() {
            var nameSearch = $("#id_name")
                .val()
                .trim();
            form.find("button[type=submit]")
                .get(0)
                .disabled = !nameSearch && !anyAdvancedActive();
        }

        function updateAdvanced() {
            form.find("input[name=by]:checked")
                .closest(".search_field")
                .find("input,select")
                .not("input[name=by]")
                .each(function () {
                    this.disabled = false;
                    this.focus();
                });

            form.find("input[name=by]")
                .not(":checked")
                .closest(".search_field")
                .find("input,select")
                .not("input[name=by]")
                .each(function () {
                    this.disabled = true;
                });

            toggleSubmit();
        }

        if (form.length > 0) {
            form.find(".search_field input[name=by]")
                .closest(".search_field")
                .find("label,input")
                .on("click", updateAdvanced);

            form.find(".search_field input,select")
                .on("change click keyup", toggleSubmit);

            form.find(".toggle_advanced")
                .on("click", function () {
                    var advanced = $(this)
                        .next();
                    advanced.find('.search_field input[type="radio"]')
                        .attr("checked", false);
                    updateAdvanced();
                });

            updateAdvanced();
        }
    });
