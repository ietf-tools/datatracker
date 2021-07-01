var agenda_filter; // public interface
var agenda_filter_for_testing; // methods to be accessed for automated testing

// closure to create private scope
(function () {
    'use strict'

    /* n.b., const refers to the opts object itself, not its contents.
     * Use camelCase for easy translation into element.dataset keys,
     * which are automatically camel-cased from the data attribute name.
     * (e.g., data-always-show -> elt.dataset.alwaysShow) */
    const opts = {
        alwaysShow: false,
        updateCallback: null // function(filter_params)
    };

    /* Remove from list, if present */
    function remove_list_item (list, item) {
        var item_index = list.indexOf(item);
        if (item_index !== -1) {
            list.splice(item_index, 1)
        }
    }

    /* Add to list if not present, remove if present
     * 
     * Returns true if added to the list, otherwise false.
     */
    function toggle_list_item (list, item) {
        var item_index = list.indexOf(item);
        if (item_index === -1) {
            list.push(item)
            return true;
        } else {
            list.splice(item_index, 1)
            return false;
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
        var result = [];
        var qp = qparams[filt].split(',');
        
        for (var ii = 0; ii < qp.length; ii++) {
            result.push(qp[ii].trim());
        }
        return result;
    }

    function get_filter_params (qparams) {
        var enabled = opts.alwaysShow || qparams.show || qparams.hide;
        return {
            enabled: enabled,
            show: get_filter_from_qparams(qparams, 'show'),
            hide: get_filter_from_qparams(qparams, 'hide')
        }
    }

    function get_keywords(elt) {
        var keywords = $(elt).attr('data-filter-keywords');
        if (keywords) {
            return keywords.toLowerCase().split(',');
        }
        return [];
    }

    function get_item(elt) {
        return $(elt).attr('data-filter-item');
    }

    // utility method - is there a match between two lists of keywords?
    function keyword_match(list1, list2) {
        for (var ii = 0; ii < list1.length; ii++) {
            if (list2.indexOf(list1[ii]) !== -1) {
                return true;
            }
        }
        return false;
    }
    
    // Find the items corresponding to a keyword
    function get_items_with_keyword (keyword) {
        var items = [];

        $('.view button.pickview').filter(function(index, elt) {
            return keyword_match(get_keywords(elt), [keyword]);
        }).each(function (index, elt) {
            items.push(get_item($(elt)));
        });
        return items;
    }

    function filtering_is_enabled (filter_params) {
        return filter_params.enabled;
    }

    // Update the filter / customization UI to match the current filter parameters
    function update_filter_ui (filter_params) {
        var buttons = $('.pickview');

        if (!filtering_is_enabled(filter_params)) {
            // Not filtering - set to default and exit
            buttons.removeClass('active');
            return;
        }

        update_href_querystrings(filter_params_as_querystring(filter_params))

        // show the customizer - it will stay visible even if filtering is disabled
        const customizer = $('#customize');
        if (customizer.hasClass('collapse')) {
            customizer.collapse('show')
        }

        // Update button state to match visibility
        buttons.each(function (index, elt) {
            elt = $(elt);
            var keywords = get_keywords(elt);
            keywords.push(get_item(elt)); // treat item as one of its keywords
            var hidden = keyword_match(filter_params.hide, keywords);
            var shown = keyword_match(filter_params.show, keywords); 
            if (shown && !hidden) {
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
        if (opts.updateCallback) {
            opts.updateCallback(filter_params)
        }
    }

    /* Trigger an update so the user will see the page appropriate for given filter_params
     *
     * Updates the URL to match filter_params, then updates the history / display to match
     * (if supported) or loads the new URL.
     */
    function update_filters (filter_params) {
        var new_url = replace_querystring(
          window.location.href,
          filter_params_as_querystring(filter_params)
        )
        update_href_querystrings(filter_params_as_querystring(filter_params))
        if (window.history && window.history.replaceState) {
            // Keep current origin, replace search string, no page reload
            history.replaceState({}, document.title, new_url)
            update_view()
        } else {
            // No window.history.replaceState support, page reload required
            window.location = new_url
        }
    }

    /**
     * Update the querystring in the href filterable agenda links
     */
    function update_href_querystrings(querystring) {
        Array.from(
          document.getElementsByClassName('agenda-link filterable')
        ).forEach(
          (elt) => elt.href = replace_querystring(elt.href, querystring)
        )
    }

    function filter_params_as_querystring(filter_params) {
        var qparams = []
        if (filter_params.show.length > 0) {
            qparams.push('show=' + filter_params.show.join())
        }
        if (filter_params.hide.length > 0) {
            qparams.push('hide=' + filter_params.hide.join())
        }
        if (qparams.length > 0) {
            return '?' + qparams.join('&')
        }
        return ''
    }

    function replace_querystring(url, new_querystring) {
        return url.replace(/(\?.*)?(#.*)?$/, new_querystring + window.location.hash)
    }

    /* Helper for pick group/type button handlers - toggles the appropriate parameter entry
     *    elt - the jquery element that was clicked
     */
    function handle_pick_button (elt) {
        var fp = get_filter_params(parse_query_params(window.location.search));
        var item = get_item(elt);

        /* Normally toggle in and out of the 'show' list. If this item is active because
         * one of its keywords is active, invert the sense and toggle in and out of the
         * 'hide' list instead. */
        var inverted = keyword_match(fp.show, get_keywords(elt));
        var just_showed_item = false;
        if (inverted) {
            toggle_list_item(fp.hide, item);
            remove_list_item(fp.show, item);
        } else {
            just_showed_item = toggle_list_item(fp.show, item);
            remove_list_item(fp.hide, item);
        }

        /* If we just showed an item, remove its children from the 
         * show/hide lists to keep things consistent. This way, selecting
         * an area will enable all items in the row as one would expect. */
        if (just_showed_item) {
            var children = get_items_with_keyword(item);
            $.each(children, function(index, child) {
                remove_list_item(fp.show, child);
                remove_list_item(fp.hide, child);
            });
        }
        
        // If the show list is empty, clear the hide list because there is nothing to hide
        if (fp.show.length === 0) {
            fp.hide = [];
        }
        
        return fp;
    }

    function is_disabled(elt) {
        return elt.hasClass('disabled');
    }

    function register_handlers() {
        $('.pickview').click(function () {
            if (is_disabled($(this))) { return; }
            var fp = handle_pick_button($(this));
            update_filters(fp);
        });
    }

    /**
     * Read options from the template
     */
    function read_template_options() {
        const opts_elt = document.getElementById('agenda-filter-options');
        opts.keys().forEach((opt) => {
            if (opt in opts_elt.dataset) {
                opts[opt] = opts_elt.dataset[opt];
            }
        });
    }

    /* Entry point to filtering code when page loads
     * 
     * This must be called if you are using the HTML template to provide a customization
     * button UI. Do not call if you only want to use the parameter parsing routines.
     */
    function enable () {
        // ready handler fires immediately if document is already "ready"
        $(document).ready(function () {
            register_handlers();
            update_view();
        })
    }

    // utility method - filter a jquery set to those matching a keyword
    function rows_matching_filter_keyword(rows, kw) {
        return rows.filter(function(index, element) {
            var row_kws = get_keywords(element);
            return keyword_match(row_kws, [kw.toLowerCase()]);
        });
    }

    // Make private functions available for unit testing
    agenda_filter_for_testing = {
        parse_query_params: parse_query_params,
        toggle_list_item: toggle_list_item
    };

    // Make public interface methods accessible
    agenda_filter = {
        enable: enable,
        filtering_is_enabled: filtering_is_enabled,
        get_filter_params: get_filter_params,
        keyword_match: keyword_match,
        parse_query_params: parse_query_params,
        rows_matching_filter_keyword: rows_matching_filter_keyword,
        set_update_callback: function (cb) {opts.updateCallback = cb}
    };
})();