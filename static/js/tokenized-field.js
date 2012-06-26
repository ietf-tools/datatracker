function setupTokenizedField(field) {
    if (field.parents(".template").length > 0)
        return;                 // don't tokenize hidden template snippets

    var pre = [];
    if (field.val())
        pre = JSON.parse(field.val());
    else if (field.data("pre"))
        pre = JSON.parse(field.data("pre"));
    field.tokenInput(field.data("ajax-url"), {
        hintText: "",
        preventDuplicates: true,
        prePopulate: pre
    });
}

jQuery(function () {
    jQuery(".tokenized-field").each(function () { setupTokenizedField(jQuery(this)); });
});
