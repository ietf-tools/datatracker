local_js = function () {
    let select2_elem = $('#id_action_holders');
    let role_ids = select2_elem.data('role-ids');

    function update_selection(elem, entries, selected) {
        elem.children("option")
            .each(function () {
                if (entries.some(x => x == $(this)
                        .val())) {
                    $(this)
                        .prop("selected", selected);
                }
            })
            .trigger('change');
    }

    function add_ah(role) {
        if (role_ids[role]) {
            update_selection(select2_elem, role_ids[role], true);
        }
    }

    function del_ah(role) {
        if (role_ids[role] && select2_elem.val()) {
            update_selection(select2_elem, role_ids[role], false);
        }
    }

    function all_selected(elem, role) {
        if (!elem.val()) { return false; }
        let data_ids = elem.val()
            .map(Number);
        for (let ii = 0; ii < role_ids[role].length; ii++) {
            if (-1 === data_ids.indexOf(role_ids[role][ii])) {
                return false;
            }
        }
        return true;
    }

    function none_selected(elem, role) {
        if (!elem.val()) { return true; }

        let data_ids = elem.val()
            .map(Number);
        for (let ii = 0; ii < role_ids[role].length; ii++) {
            if (-1 !== data_ids.indexOf(role_ids[role][ii])) {
                return false;
            }
        }
        return true;
    }

    function update_buttons() {
        for (let role_slug in role_ids) {
            if (!role_ids.hasOwnProperty(role_slug)) { return; }

            if (all_selected(select2_elem, role_slug)) {
                $('#add-' + role_slug)
                    .attr('disabled', true);
            } else {
                $('#add-' + role_slug)
                    .attr('disabled', false);
            }

            if (none_selected(select2_elem, role_slug)) {
                $('#del-' + role_slug)
                    .attr('disabled', true);
            } else {
                $('#del-' + role_slug)
                    .attr('disabled', false);
            }
        }

    }

    select2_elem.on('change', update_buttons);
    $(document)
        .ready(update_buttons);

    return {
        add_ah: add_ah,
        del_ah: del_ah
    };
}();
