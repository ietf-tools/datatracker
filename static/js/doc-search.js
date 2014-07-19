$(function () {
    // search form
    var form = jQuery("#search_form");

    function anyAdvancedActive() {
        var advanced = false;

        var by = form.find("input[name=by]:checked");
        if (by.length > 0)
            by.closest(".search_field").find("input,select").not("input[name=by]").each(function () {
                if ($.trim(this.value))
                    advanced = true;
            });

	var additional_doctypes = form.find("input[advdoctype=true]:checked");
	if (additional_doctypes.length > 0)
	    advanced = true; 

        return advanced;
    }

    function toggleSubmit() {
        var nameSearch = $.trim($("#id_name").val());
        form.find("input[type=submit]").get(0).disabled = !nameSearch && !anyAdvancedActive();
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

    function updateAdvanced() {
        form.find("input[name=by]:checked").closest(".search_field").find("input,select").not("input[name=by]").each(function () {
            this.disabled = false;
        });

        form.find("input[name=by]").not(":checked").closest(".search_field").find("input,select").not("input[name=by]").each(function () {
            this.disabled = true;
        });

        toggleSubmit();
    }

    if (form.length > 0) {
        form.find(".search_field input[name=by]").closest("label").click(updateAdvanced);

        form.find(".search_field input,select")
            .change(toggleSubmit).click(toggleSubmit).keyup(toggleSubmit);

        form.find(".toggle_advanced").click(function () {
            var advanced = $(this).next();
            advanced.find('.search_field input[type="radio"]').attr("checked", false);
            togglePlusMinus($(this), advanced);
            updateAdvanced();
        });

        updateAdvanced();
    }

    // search results
    $('.search-results .addtolist a').click(function(e) {
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

    $('.search-results .removefromlist a').click(function(e) {
        e.preventDefault();
        var trigger = $(this);
        $.ajax({
            url: trigger.attr('href'),
            type: 'POST',
            cache: false,
            dataType: 'json',
            success: function(response){
                if (response.success) {
                    trigger.replaceWith('removed');
                }
            }
        });
    });

    $("a.ballot-icon").click(function (e) {
        e.preventDefault();

        $.ajax({
            url: $(this).data("popup"),
            success: function (data) {
                showModalBox(data);
            },
            error: function () {
                showModalBox("<div>Error retrieving popup content</div>");
            }
        });
    }).each(function () {
        // bind right-click shortcut
        var editPositionUrl = $(this).data("edit");
        if (editPositionUrl) {
            $(this).bind("contextmenu", function (e) {
                e.preventDefault();
                window.location = editPositionUrl;
            });
        }
    });
});
