jQuery(document).ready(function () {
    jQuery(".permanent-delete").click(function (e) {
        return confirm('Delete file permanently from the server?');
    });
});
