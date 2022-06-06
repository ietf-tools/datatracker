local_js = function () {
    const sortable_list_id = 'authors-list'; // id of the container element for Sortable
    const prefix = 'author'; // formset prefix - must match the prefix in the edit_authors() view
    var list_container;
    var form_counter;
    var author_template;
    var person_select2_input_selector = 'select.select2-field[name^="author-"][name$="-person"]';

    function handle_drag_end() {
        // after dragging, set order inputs to match new positions in list
        $(list_container)
            .find('.draggable input[name^="' + prefix + '"][name$="ORDER"]')
            .each(
                function (index, elt) {
                    $(elt)
                        .val(index + 1);
                });
    }

    function add_author() {
        // __prefix__ is the unique prefix for each list item, indexed from 0
        var new_html = $(author_template)
            .html()
            .replaceAll('__prefix__', form_counter.value);
        var new_elt = $(new_html);
        $(list_container)
            .append(new_elt);
        var new_person_select = new_elt.find(person_select2_input_selector);
        setupSelect2Field(new_person_select);
        new_person_select.on('change', person_changed);

        var form_count = Number(form_counter.value);
        form_counter.value = String(form_count + 1);

        new_elt[0].scrollIntoView(true);
    }

    function update_email_options_cb_factory(email_select) {
        // factory method creates a closure for the callback
        return function (ajax_data) {
            // keep the first item - it's the 'blank' option
            $(email_select)
                .children()
                .not(':first')
                .remove();
            $.each(ajax_data, function (index, email) {
                $(email_select)
                    .append(
                        $('<option></option>')
                        .attr('value', email.address)
                        .text(email.address)
                    );
            });
            if (ajax_data.length > 0) {
                $(email_select)
                    .val(ajax_data[0].address);
            }
        };
    }

    function person_changed() {
        var person_elt = $(this);
        var email_select = $('#' + person_elt.attr('id')
            .replace(/-person$/, '-email'));
        $.get(
            ajax_url.replace('123454321', $(this)
                .val()),
            null,
            update_email_options_cb_factory(email_select)
        );
    }

    list_container = document.getElementById(sortable_list_id);
    form_counter = document.getElementsByName(prefix + '-TOTAL_FORMS')[0];
    author_template = document.getElementById('empty-author-form');

    Sortable.create(
        list_container, {
            handle: '.handle',
            onEnd: handle_drag_end
        });

    // register handler
    $(person_select2_input_selector)
        .on('change', person_changed);

    return {
        add_author: add_author
    };
}();