var agenda_filter_for_testing = {}; // methods to be accessed for automated testing
var agenda_filter = function () {
    'use strict'

    var update_callback // function(filter_params)
    var enable_non_area = false // if true, show the non-area filters

    /* Add to list without duplicates */
    function add_list_item (list, item) {
        if (list.indexOf(item) === -1) {
            list.push(item);
        }
    }

    /* Remove from list, if present */
    function remove_list_item (list, item) {
        var item_index = list.indexOf(item);
        if (item_index !== -1) {
            list.splice(item_index, 1)
        }
    }

    /* Add to list if not present, remove if present */
    function toggle_list_item (list, item) {
        var item_index = list.indexOf(item);
        if (item_index === -1) {
            list.push(item)
        } else {
            list.splice(item_index, 1)
        }
    }

    function parse_query_params (qs) {
        var params = {}
        qs = decodeURI(qs).replace(/^\?/, '').toLowerCase()
        if (qs) {
            var param_strs = qs.split('&')
            for (var ii = 0; ii < param_strs.length; ii++) {
                var toks = param_strs[ii].split('=', 2)
                params[toks[0]] = toks[1] || true
            }
        }
        return params
    }

    /* filt = 'show' or 'hide' */
    function get_filter_from_qparams (qparams, filt) {
        if (!qparams[filt] || (qparams[filt] === true)) {
            return [];
        }
        return $.map(qparams[filt].split(','), function(s){return s.trim();});
    }

    function get_filter_params (qparams) {
        var enabled = !!(qparams.show || qparams.hide || qparams.showtypes || qparams.hidetypes);
        return {
            enabled: enabled,
            show_groups: get_filter_from_qparams(qparams, 'show'),
            hide_groups: get_filter_from_qparams(qparams, 'hide'),
            show_types: get_filter_from_qparams(qparams, 'showtypes'),
            hide_types: get_filter_from_qparams(qparams, 'hidetypes'),
        }
    }

    function filtering_is_enabled (filter_params) {
        return filter_params['enabled'];
    }

    function get_area_items (area) {
        var types = [];
        var groups = [];
        var neg_groups = [];

        $('.view.' + area).find('button').each(function (index, elt) {
            elt = $(elt) // jquerify
            var item = elt.text().trim().toLowerCase()
            if (elt.hasClass('picktype')) {
                types.push(item)
            } else if (elt.hasClass('pickview')) {
                groups.push(item);
            } else if (elt.hasClass('pickviewneg')) {
                neg_groups.push(item)
            }
        });
        return { 'groups': groups, 'neg_groups': neg_groups, 'types': types };
    }

    // Update the filter / customization UI to match the current filter parameters
    function update_filter_ui (filter_params) {
        var area_group_buttons = $('.view .pickview, .pick-area');
        var non_area_header_button = $('button.pick-non-area');
        var non_area_type_buttons = $('.view.non-area .picktype');
        var non_area_group_buttons = $('.view.non-area button.pickviewneg');

        if (!filtering_is_enabled(filter_params)) {
            // Not filtering - set everything to defaults and exit
            area_group_buttons.removeClass('active');
            non_area_header_button.removeClass('active');
            non_area_type_buttons.removeClass('active');
            non_area_group_buttons.removeClass('active');
            non_area_group_buttons.addClass('disabled');
            return;
        }

        // show the customizer - it will stay visible even if filtering is disabled
        $('#customize').collapse('show')

        // Group and area buttons - these are all positive selections
        area_group_buttons.each(function (index, elt) {
            elt = $(elt);
            var item = elt.text().trim().toLowerCase();
            var area = elt.attr('data-group-area');
            if ((filter_params['hide_groups'].indexOf(item) === -1) // not hidden...
                && ((filter_params['show_groups'].indexOf(item) !== -1) // AND shown...
                    || (area && (filter_params['show_groups'].indexOf(area.trim().toLowerCase()) !== -1))) // OR area shown
            ) {
                elt.addClass('active');
            } else {
                elt.removeClass('active');
            }
        });

        // Non-area buttons need special handling. Only have positive type and negative group buttons.
        // Assume non-area heading is disabled, then enable if one of the types is active
        non_area_header_button.removeClass('active');
        non_area_group_buttons.addClass('disabled');
        non_area_type_buttons.each(function (index, elt) {
            // Positive type selection buttons
            elt = $(elt);
            var item = elt.text().trim().toLowerCase();
            if ((filter_params['show_types'].indexOf(item) !== -1)
                && (filter_params['hide_types'].indexOf(item) === -1)){
                elt.addClass('active');
                non_area_header_button.addClass('active');
                non_area_group_buttons.removeClass('disabled');
            } else {
                elt.removeClass('active');
            }
        });

        non_area_group_buttons.each(function (index, elt) {
            // Negative group selection buttons
            elt = $(elt);
            var item = elt.text().trim().toLowerCase();
            if (filter_params['hide_groups'].indexOf(item) === -1) {
                elt.addClass('active');
            } else {
                elt.removeClass('active');
            }
        });
    }

    /* Update state of the view to match the filters
     *
     * Calling the individual update_* functions outside of this method will likely cause
     * various parts of the page to get out of sync.
     */
    function update_view () {
        var filter_params = get_filter_params(parse_query_params(window.location.search))
        update_filter_ui(filter_params)
        if (update_callback) {
            update_callback(filter_params)
        }
    }


    /* Trigger an update so the user will see the page appropriate for given filter_params
     *
     * Updates the URL to match filter_params, then updates the history / display to match
     * (if supported) or loads the new URL.
     */
    function update_filters (filter_params) {
        var qparams = []
        var search = ''
        if (filter_params['show_groups'].length > 0) {
            qparams.push('show=' + filter_params['show_groups'].join())
        }
        if (filter_params['hide_groups'].length > 0) {
            qparams.push('hide=' + filter_params['hide_groups'].join())
        }
        if (filter_params['show_types'].length > 0) {
            qparams.push('showtypes=' + filter_params['show_types'].join())
        }
        if (filter_params['hide_types'].length > 0) {
            qparams.push('hidetypes=' + filter_params['hide_types'].join())
        }
        if (qparams.length > 0) {
            search = '?' + qparams.join('&')
        }

        // strip out the search / hash, then add back
        var new_url = window.location.href.replace(/(\?.*)?(#.*)?$/, search + window.location.hash)
        if (window.history && window.history.replaceState) {
            // Keep current origin, replace search string, no page reload
            history.replaceState({}, document.title, new_url)
            update_view()
        } else {
            // No window.history.replaceState support, page reload required
            window.location = new_url
        }
    }

    /* Helper for pick group/type button handlers - toggles the appropriate parameter entry
     *    elt - the jquery element that was clicked
     *    param_type - key of the filter param to update (show_groups, show_types, etc)
     */
    function handle_pick_button (elt, param_type) {
        var area = elt.attr('data-group-area');
        var item = elt.text().trim().toLowerCase();
        var fp = get_filter_params(parse_query_params(window.location.search));
        var neg_param_type = {
            show_groups: 'hide_groups',
            hide_groups: 'show_groups',
            show_types: 'hide_types',
            hide_types: 'show_types'
        }[param_type];

        if (area && (fp[param_type].indexOf(area.trim().toLowerCase()) !== -1)) {
            // Area is shown - toggle hide list
            toggle_list_item(fp[neg_param_type], item);
            remove_list_item(fp[param_type], item);
        } else {
            toggle_list_item(fp[param_type], item);
            remove_list_item(fp[neg_param_type], item);
        }
        return fp;
    }

    function is_disabled(elt) {
        return elt.hasClass('disabled');
    }

    // Various "pick" button handlers
    $('.pickview').click(function () {
        if (is_disabled($(this))) { return; }
        update_filters(handle_pick_button($(this), 'show_groups'))
    });

    $('.pickviewneg').click(function () {
        if (is_disabled($(this))) { return; }
        update_filters(handle_pick_button($(this), 'hide_groups'))
    });

    $('.picktype').click(function () {
        if (is_disabled($(this))) { return; }
        var fp = handle_pick_button($(this), 'show_types')
        // If we just disabled the last non-area type, clear out the hide groups list.
        var items = get_area_items('non-area')
        var any_left = false
        $.each(items.types, function (index, session_type) {
            if (fp['show_types'].indexOf(session_type) !== -1) {
                any_left = true
            }
        })
        if (!any_left) {
            fp['hide_groups'] = []
        }
        update_filters(fp);
    });

    // Click handler for an area header button
    $('.pick-area').click(function() {
        if (is_disabled($(this))) { return; }
        var fp = handle_pick_button($(this), 'show_groups');
        var items = get_area_items($(this).text().trim().toLowerCase());

        // Clear all the individual group show/hide options
        $.each(items.groups, function(index, group) {
            remove_list_item(fp['show_groups'], group);
            remove_list_item(fp['hide_groups'], group);
        });
        update_filters(fp);
    });

    // Click handler for the "Non-Area" header button
    $('.pick-non-area').click(function () {
        var items = get_area_items('non-area');

        var fp = get_filter_params(parse_query_params(window.location.search))
        if ($(this).hasClass('active')) {
            // Were active - disable or hide everything
            $.each(items.types, function (index, session_type) {
                remove_list_item(fp['show_types'], session_type)
            })
            // When no types are shown, no need to hide groups. Empty hide_groups list.
            fp['hide_groups'] = []
        } else {
            // Were not active - enable or stop hiding everything
            $.each(items.types, function (index, session_type) {
                add_list_item(fp['show_types'], session_type)
            })
            $.each(items.neg_groups, function (index, group) {
                remove_list_item(fp['hide_groups'], group)
            })
        }
        update_filters(fp);
    });

    // Entry point to filtering code when page loads
    function enable () {
        $(document).ready(function () {
            update_view()
        })
    }

    // Make private functions available for unit testing
    agenda_filter_for_testing.toggle_list_item = toggle_list_item;
    agenda_filter_for_testing.parse_query_params = parse_query_params;

    // Public interface methods
    return {
        enable: enable,
        filtering_is_enabled: filtering_is_enabled,
        include_non_area_selectors: function () {enable_non_area = true},
        set_update_callback: function (cb) {update_callback = cb}
    }
}();