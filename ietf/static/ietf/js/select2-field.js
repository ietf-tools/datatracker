// currently we only include select2 CSS/JS on those pages where forms
// need it, so the generic setup code here is also kept separate
function setupSelect2Field(e) {
    var url = e.data("ajax-url");
    if (!url)
        return;

    var maxEntries = e.data("max-entries");
    var multiple = maxEntries !== 1;
    var prefetched = e.data("pre");
    e.select2({
        multiple: multiple,
        minimumInputLength: 2,
        width: "off",
        allowClear: true,
        maximumSelectionSize: maxEntries,
        ajax: {
            url: url,
            dataType: "json",
            quietMillis: 250,
            data: function (term, page) {
                return {
                    q: term,
                    p: page
                };
            },
            results: function (results) {
                return {
                    results: results,
                    more: results.length === 10
                };
            }
        },
        escapeMarkup: function (m) {
            return m;
        },
        initSelection: function (element, cb) {
            element = $(element);  // jquerify

            // The original data set will contain any values looked up via ajax
            var data = element.select2('data') | [] ;
            var data_map = {};
            
            // map id to its data representation
            for (var ii = 0; ii < data.length; ii++) {
                var this_item = data[ii];
                data_map[this_item.id] = this_item;
            }
            
            // convert values to data objects, letting element data supersede prefetch
            var ids = element.val().split(','); 
            if (!multiple && ids.length > 0) {
                cb(data_map[ids[0]] || prefetched[ids[0]]);
            } else {
                cb(ids.map(function(id) {
                    return data_map[id] || prefetched[id];
                }));
            }
        },
        dropdownCssClass: "bigdrop"
    });
}

$(document).ready(function () {
    $(".select2-field").each(function () {
        if ($(this).closest(".template").length > 0)
            return;

        setupSelect2Field($(this));
    });
});
