function setupTokenizedField(field) {
    if (field.parents(".template").length > 0)
        return;                 // don't tokenize hidden template snippets

    var pre = [];
    if (field.attr("data-pre"))
        pre = JSON.parse((field.attr("data-pre") || "").replace(/&quot;/g, '"'));

    field.tokenInput(field.attr("data-ajax-url"), {
        preventDuplicates: true,
        prePopulate: pre,
        tokenLimit: field.attr("data-max-entries"),
        noResultsText: "No results - cannot use this entry",
        hintText: field.attr("data-hint-text")
    });
}

jQuery(function () {
    jQuery(".tokenized-field").each(function () { setupTokenizedField(jQuery(this)); });
});
