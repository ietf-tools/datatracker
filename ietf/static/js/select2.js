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

// Copyright The IETF Trust 2015-2021, All Rights Reserved
// JS for ietf.utils.fields.SearchableField subclasses
window.setupSelect2Field = function (e) {
    var url = e.data("ajax--url");
    var maxEntries = e.data("max-entries");
    var result_key = e.data("result-key");
    var options = e.data("pre");
    for (var id in options) {
        e.append(new Option(options[id].text, options[id].id, false, options[id].selected));
    }

    template_modify = e.hasClass("tz-select") ? prettify_tz : undefined;

    e.select2({
        multiple: maxEntries !== 1,
        maximumSelectionSize: maxEntries,
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
