$(function (){
    // fill in submitter info when an author button is clicked
    $("input[type=button]").click(function () {
        var name = $(this).data("name");
        if (name == null) // backwards compatibility
            return;
        var email = $(this).data("email");

        $(this).parents("form").find("input[name=name]").val(name || "");
        $(this).parents("form").find("input[name=email]").val(email || "");
    });
});
