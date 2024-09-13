$(document)
    .ready(function () {
        var form = $(".ipr-form");

        $('.draft-add-row')
            .on("click", function () {
                var template = form.find('.draft-row.template');
                var el = template.clone(true)
                    .removeClass("template d-none");

                var totalField = $('#id_iprdocrel_set-TOTAL_FORMS');
                var total = +totalField.val();

                el.find("*[for*=iprdocrel], *[id*=iprdocrel], *[name*=iprdocrel]")
                    .not(".d-none")
                    .each(function () {
                        var x = $(this);
                        ["for", "id", "name"].forEach(function (at) {
                            var val = x.attr(at);
                            if (val && val.match("iprdocrel")) {
                                x.attr(at, val.replace('__prefix__', total.toString()));
                            }
                        });
                    });
                ++total;

                totalField.val(total);

                template.before(el);

                el.find('.select2-field').each((index, element) => setupSelect2Field($(element)));
            });

        function updateRevisions() {
            if ($(this)
                .hasClass("template"))
                return;

            var selectbox = $(this)
                .find('[name$="document"]');

            if (selectbox.val()) {
                var name = selectbox.select2("data")[0]
                    .text;
                var prefix = name.toLowerCase()
                    .substring(0, 3);
                if (prefix == "rfc" || prefix == "bcp" || prefix == "std")
                    $(this)
                    .find('[name$=revisions]')
                    .val("")
                    .hide();
                else
                    $(this)
                    .find('[name$=revisions]')
                    .show();
            }
        }

        form.on("change", ".select2-field", function () {
            $(this)
                .closest(".draft-row")
                .each(updateRevisions);
        });

        // add a little bit of delay to let the select2 box have time to do its magic
        // FIXME: this should be done after a select2 event fires!
        // See https://select2.org/programmatic-control/events
        setTimeout(function () {
            form.find(".draft-row")
                .each(updateRevisions);
        }, 10);

        // Manage fields that depend on the Blanket IPR Disclosure choice
        const blanketCheckbox = document.getElementById('id_is_blanket_disclosure') 
        if (blanketCheckbox) {
            const patentDetailInputs = [
                // The ids are from the HolderIprDisclosureForm and its base form class,
                // intentionally excluding patent_notes because it's never required
                'id_patent_number',
                'id_patent_inventor',
                'id_patent_title',
                'id_patent_date'
            ].map((id) => document.getElementById(id))
            const patentDetailRowDivs = patentDetailInputs.map(
                (elt) => elt.closest('div.row')
            )
            const royaltyFreeLicensingRadio = document.querySelector(
                '#id_licensing input[value="royalty-free"]'
            )
            let lastSelectedLicensingRadio
            const otherLicensingRadios = document.querySelectorAll(
                '#id_licensing input:not([value="royalty-free"])'
            ) 
            
            const handleBlanketCheckboxChange = () => {
                const isBlanket = blanketCheckbox.checked
                // Update required fields
                for (elt of patentDetailInputs) {
                    // disable the input element
                    elt.required = !isBlanket
                }
                for (elt of patentDetailRowDivs) {
                    // update the styling on the row that indicates required field
                    if (isBlanket) {
                        elt.classList.remove('required')
                    } else {
                        elt.classList.add('required')
                    }
                }
                // Update licensing selection
                if (isBlanket) {
                    lastSelectedLicensingRadio = document.querySelector(
                        '#id_licensing input:checked'
                    )
                    royaltyFreeLicensingRadio.checked = true
                    otherLicensingRadios
                        .forEach(
                            (elt) => elt.setAttribute('disabled', '')
                        )
                } else {
                    royaltyFreeLicensingRadio.checked = false
                    if (lastSelectedLicensingRadio) {
                        lastSelectedLicensingRadio.checked = true
                    }
                    otherLicensingRadios
                        .forEach(
                            (elt) => elt.removeAttribute('disabled')
                        )
                }
            }
            handleBlanketCheckboxChange()
            blanketCheckbox.addEventListener(
                'change', 
                (evt) => handleBlanketCheckboxChange()
            )
        }
    });
