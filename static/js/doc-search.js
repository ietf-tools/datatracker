$(function () {
    var form = jQuery("#search_form");

    // we want to disable our submit button if we have no search text,
    // and we have no advanced options selected
    function toggleSubmit() {
        var nameSearch = $.trim($("#id_name").val());

        var noAdvanced = true;

        var by = form.find("input[name=by]:checked");
        if (by.length > 0)
            by.closest(".search_field").find("input,select").not("input[name=by]").each(function () {
                if ($.trim(this.value))
                    noAdvanced = false;
            });

        form.find("input[type=submit]").get(0).disabled = !nameSearch && noAdvanced;
    }

    function togglePlusMinus(toggler, toggled) {
        var img = toggler.find("img").get(0);
        if (toggled.is(":hidden")) {
            toggled.show();
            img.src = "/images/minus.png";
        } else { 
            toggled.hide();
            img.src = "/images/plus.png";
        }
    }

    function updateBy() {
        form.find("input[name=by]:checked").closest(".search_field").find("input,select").not("input[name=by]").each(function () {
            this.disabled = false;
        });

        form.find("input[name=by]").not(":checked").closest(".search_field").find("input,select").not("input[name=by]").each(function () {
            this.disabled = true;
        });

        toggleSubmit();
    }

    form.find(".search_field input[name=by]").closest("label").click(updateBy);

    form.find(".search_field input,select")
        .change(toggleSubmit).click(toggleSubmit).keyup(toggleSubmit);

    form.find(".toggle_advanced").click(function () {
        var advanced = $(this).next();
        advanced.find('.search_field input[type="radio"]').attr("checked", false);
        togglePlusMinus($(this), advanced);
        updateBy();
    });

    updateBy();

    $("#search_results th").click(function (e) {
        window.location = $(this).find("a").attr("href");
    })

    $('#search_results .addtolist a').click(function(e) {
        e.preventDefault();
        var trigger = $(this);
        $.ajax({
            url: trigger.attr('href'),
            type: 'POST',
            cache: false,
            dataType: 'json',
            success: function(response){
                if (response.success) {
                    trigger.replaceWith('added');
                }
            }
        });
    });
});
