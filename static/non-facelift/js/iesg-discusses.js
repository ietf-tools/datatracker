jQuery(function () {
    var radioButtons = jQuery('input[name="discusses"]');

    var url = window.location.hash.replace("#", "");
    if (url == "byme" || url == "forme")
        radioButtons.filter("[value=" + url + "]").click();

    function updateDisplayedRows() {
        var rows = jQuery(".discuss-row");

        var val = radioButtons.filter(":checked").val();

        if (val == "all") {
            rows.show();
            if (window.location.hash)
                window.location.hash = "";
        }
        else if (val == "forme" || val == "byme") {
            console.log(rows.filter("." + val))
            rows.filter("." + val).show();
            rows.not("." + val).hide();
            window.location.hash = val;
        }

        // odd/even are swapped because the jQuery filter is 0-indexed
        rows.filter(":visible").filter(":even").removeClass("even").addClass("odd");
        rows.filter(":visible").filter(":odd").removeClass("odd").addClass("even");
    }

    radioButtons.click(updateDisplayedRows);

    updateDisplayedRows();
});
