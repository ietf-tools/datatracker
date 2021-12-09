// Copyright The IETF Trust 2015-2021, All Rights Reserved
// JS for ietf.utils.fields.SearchableField subclasses
function setupSelect2Field(e) {
    var url = e.data("ajax--url");
    if (!url)
        return;

    var maxEntries = e.data("max-entries");
    var multiple = maxEntries !== 1;
    var prefetched = e.data("pre");

    // FIXME: select2 v4 doesn't work with text inputs anymore, so we replace
    // it with a select. this is super ugly, the correct fix would be to base
    // ietf.utils.fields.SearchableField on Django's SelectMultiple.
    var select = $('<select class="' + e.attr('class') + '" multiple="multiple"><select>');
    // Validate prefetched
    for (var id in prefetched) {
        if (prefetched.hasOwnProperty(id)) {
            if (String(prefetched[id].id) !== id) {
                throw 'data-pre attribute for a select2-field input ' +
                    'must be a JSON object mapping id to object, but ' +
                    id + ' does not map to an object with that id.';
            }
            // Create the DOM option that is pre-selected by default
            var option = new Option(prefetched[id].text, prefetched[id].id, true, true);

            // Append it to the select
            select.append(option);
        }
    }

    select.insertAfter(e);
    // e.hide();

    select.select2({
        multiple: multiple,
        maximumSelectionSize: maxEntries,
        data: [],
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

    select.on("change", function (x) {
        $(x.target)
            .find("option")
            .each(function () {
                var id = $(this)
                    .attr("value");
                console.log(id);
                console.log(select.prev("input").text());
            });
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