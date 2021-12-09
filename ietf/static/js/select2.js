import $ from "jquery";
import select2 from "select2";

select2($);

$.fn.select2.defaults.set("allowClear", true);
$.fn.select2.defaults.set("dropdownCssClass", ":all:");
$.fn.select2.defaults.set("minimumInputLength", 2);
$.fn.select2.defaults.set("theme", "bootstrap-5");
$.fn.select2.defaults.set("width", "off");
$.fn.select2.defaults.set("escapeMarkup", function (m) {
    return m;
});

// Copyright The IETF Trust 2015-2021, All Rights Reserved
// JS for ietf.utils.fields.SearchableField subclasses
function setupSelect2Field(e) {
    var url = e.data("ajax--url");
    if (!url)
        return;

    var maxEntries = e.data("max-entries");
    e.select2({
        multiple: maxEntries !== 1,
        maximumSelectionSize: maxEntries,
        ajax: {
            url: url,
            dataType: "json",
            quietMillis: 250,
            data: function (params) {
                return {
                    q: params.term,
                    p: params.page || 1
                };
            },
            processResults: function (results) {
                return {
                    results: results,
                    pagination: {
                        more: results.length === 10
                    }
                };
            }
        }
    });
}

$(document)
    .ready(function () {
        $(".select2-field")
            .each(function () {
                if ($(this)
                    .closest(".template")
                    .length > 0)
                    return;
                setupSelect2Field($(this));
            });
    });