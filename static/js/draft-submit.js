jQuery(function (){
    // fill in submitter info when an author button is clicked
    jQuery("input[type=button].author").click(function () {
        var name = jQuery(this).data("name");
        var email = jQuery(this).data("email");

        jQuery(this).parents("form").find("input[name=submitter-name]").val(name || "");
        jQuery(this).parents("form").find("input[name=submitter-email]").val(email || "");
    });

    jQuery("form").submit(function() {
        if (this.submittedAlready)
            return false;
        else {
            this.submittedAlready = true;
            return true;
        }
    });

    jQuery("form#cancel-submission").submit(function () {
       return confirm("Cancel this submission?");
    });

    jQuery(".idnits-trigger").click(function (e) {
        e.preventDefault();
        var popup = jQuery(".idnits-popup").clone().show();
        showModalBox(popup);
    });

    jQuery(".twopages-trigger").click(function (e) {
        e.preventDefault();
        var popup = jQuery(".twopages-popup").clone().show();
        showModalBox(popup);
    });

    jQuery("form .add-author").click(function (e) {
        e.preventDefault();

        var table = jQuery("table.authors tbody");
        var row = table.find("tr.empty").clone();

        row.removeClass("empty");
        var prefixInput = row.find('input[name=authors-prefix]');

        // figure out a prefix
        var i = 0, prefix;
        do {
            ++i;
            prefix = prefixInput.val() + i;
        }
        while (table.find('input[name=authors-prefix][value="' + prefix +'"]').length > 0);

        prefixInput.val(prefix);
        row.find('input').not(prefixInput).each(function () {
            this.name = prefix + "-" + this.name;
        });

        table.append(row);
    });
});
