import $ from "jquery";
import select2 from "select2";

select2($);

$.fn.select2.defaults.set("allowClear", true);
$.fn.select2.defaults.set("debug", false);
$.fn.select2.defaults.set("dropdownCssClass", ":all:");
$.fn.select2.defaults.set("minimumInputLength", 2);
$.fn.select2.defaults.set("placeholder", "");
$.fn.select2.defaults.set("selectionCssClass", ":all:");
$.fn.select2.defaults.set("theme", "bootstrap-5");
$.fn.select2.defaults.set("width", "off");
$.fn.select2.defaults.set("escapeMarkup", function (m) {
    return m;
});

function prettify_tz(x) {
    return x.text.replaceAll("_", " ").replaceAll("/", " / ");
}

function search_template_result(data) {
    if (data.url == null) {
        return data.text;
    }
    var $link = $("<a>" + data.text + "</a>");
    $link.prop("href", data.url);
    $link.on("mouseup", function (evt) {
        // Do not propagate any events which have modifiers keys
        // or if some other mouse button than 1 (left) was used.
        if (evt.shiftKey || evt.ctrlKey || evt.metaKey || evt.altKey ||
            evt.which != 1) {
            evt.stopPropagation();
        }
    });

    return $link;
}

// Copyright The IETF Trust 2015-2021, All Rights Reserved
// JS for ietf.utils.fields.SearchableField subclasses
window.setupSelect2Field = function (e) {
    // Avoid using data attributes that match any of the search2 option attributes.
    // These will override settings in the options object that we use below.
    // (see https://select2.org/configuration/data-attributes)
    // Note: e.data('k') returns undefined if there is no data-k attribute.
    let url = e.data("select2-ajax-url");
    let maxEntries = e.data("max-entries");
    let minSearchLength = e.data("min-search-length");
    let result_key = e.data("result-key");
    let options = e.data("pre");
    if (options) {
        options.forEach(
          opt => e.append(new Option(opt.text, opt.id, false, opt.selected))
        );
    }

    template_modify = e.hasClass("tz-select") ? prettify_tz :
	(e.hasClass("search-select") ? search_template_result : undefined);

    // focus the search field automatically
    $(document)
        .on("select2:open", () => {
            document.querySelector(
                    ".select2-container--open .select2-search__field")
                .focus()
        });

    // Remove spurious title attribute (https://github.com/select2/select2/pull/3988)
    $(document)
        .on("mouseenter", ".select2-selection__rendered", function () { $(this)
                .removeAttr("title"); });

    e.select2({
        multiple: maxEntries !== 1,
        maximumSelectionSize: maxEntries,
        minimumInputLength: minSearchLength,
        templateResult: template_modify,
        templateSelection: template_modify,
        ajax: url ? {
            url: url,
            dataType: "json",
            delay: 250,
            data: function (params) {
                return {
                    q: params.term,
                    p: params.page || 1
                };
            },
            processResults: function (results) {
                if (result_key) {
                    // overwrite the returned "id" fields with the data in the result_key fields
                    results = results.map(x => ({ ...x, ...{ id: x[result_key] } }));
                }
                return {
                    results: results,
                    pagination: {
                        more: results.length === 10
                    }
                };
            }
        } : undefined
    });
};

$(document)
    .ready(function () {
        $(".select2-field")
            .not(".select2-hidden-accessible")
            .each(function () {
                if ($(this)
                    .closest(".template")
                    .length > 0)
                    return;
                setupSelect2Field($(this));
            });
    });
