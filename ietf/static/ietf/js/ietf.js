// setup CSRF protection using jQuery
function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}
jQuery.ajaxSetup({
    crossDomain: false, // obviates need for sameOrigin test
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type)) {
            xhr.setRequestHeader("X-CSRFToken", $.cookie('csrftoken'));
        }
    }
});

// Remember the state of the "browsehappy" alert
$('#browsehappy .close').click(function(e) {
    e.preventDefault();
    $.cookie('browsehappy', 'closed', { path: '/' });
});

if(typeof $.cookie('browsehappy') === 'undefined') {
    $('#browsehappy').show();
}

// See http://stackoverflow.com/questions/8878033/how-to-make-twitter-bootstrap-menu-dropdown-on-hover-rather-than-click
// Tweaked here, so it only expands on hover for non-collapsed navbars, and works for submenus
function hoverin() {
    var navbar = $(this).closest('.navbar');
    if (navbar.size() === 0 || navbar.find('.navbar-toggle').is(':hidden')) {
	$(this).addClass('open');
    }
}

function hoverout() {
    var navbar = $(this).closest('.navbar');
    if (navbar.size() === 0|| navbar.find('.navbar-toggle').is(':hidden')) {
	$(this).removeClass('open');
    }
}

if (!('ontouchstart' in document.documentElement)) {
    $('ul.nav li.dropdown, ul.nav li.dropdown-submenu').hover(hoverin, hoverout);
}

// This used to be in doc-search.js; consolidate all JS in one file.
$(document).ready(function () {
    // search form
    var form = $("#search_form");

    function anyAdvancedActive() {
	var advanced = false;
	var by = form.find("input[name=by]:checked");

	if (by.length > 0) {
	    by.closest(".search_field").find("input,select").not("input[name=by]").each(function () {
		if ($.trim(this.value)) {
		    advanced = true;
		}
	    });
	}

	var additional_doctypes = form.find("input.advdoctype:checked");
	if (additional_doctypes.length > 0) {
	    advanced = true;
        }
        return advanced;
    }

    function toggleSubmit() {
	var nameSearch = $.trim($("#id_name").val());
	form.find("button[type=submit]").get(0).disabled = !nameSearch && !anyAdvancedActive();
    }

    function updateAdvanced() {
	form.find("input[name=by]:checked").closest(".search_field").find("input,select").not("input[name=by]").each(function () {
	    this.disabled = false;
	    this.focus();
	});

	form.find("input[name=by]").not(":checked").closest(".search_field").find("input,select").not("input[name=by]").each(function () {
	    this.disabled = true;
	});

	toggleSubmit();
    }

    if (form.length > 0) {
	form.find(".search_field input[name=by]").closest(".search_field").find("label,input").click(updateAdvanced);

	form.find(".search_field input,select")
	    .change(toggleSubmit).click(toggleSubmit).keyup(toggleSubmit);

	form.find(".toggle_advanced").click(function () {
	    var advanced = $(this).next();
	    advanced.find('.search_field input[type="radio"]').attr("checked", false);
	    updateAdvanced();
	});

	updateAdvanced();
    }

    // search results
    $('.community-list-add-remove-doc').click(function(e) {
	e.preventDefault();
	var trigger = $(this);
	$.ajax({
	    url: trigger.attr('href'),
	    type: 'GET',
	    cache: false,
	    dataType: 'json',
	    success: function(response){
		if (response.success) {
                trigger.parent().find(".tooltip").remove();
                trigger.find("span.fa").toggleClass("fa-bookmark fa-bookmark-o");
                if (trigger.hasClass('btn')) {
                    trigger.attr('disabled', true).blur();
                } else {
                    trigger.contents().unwrap().blur();
                }
            }
	    }
	});
    });
});


// This used to be in js/draft-submit.js
$(document).ready(function () {
    // fill in submitter info when an author button is clicked
    $("form.idsubmit input[type=button].author").click(function () {
        var name = $(this).data("name");
        var email = $(this).data("email");

        $(this).parents("form").find("input[name=submitter-name]").val(name || "");
        $(this).parents("form").find("input[name=submitter-email]").val(email || "");
    });

    $("form.idsubmit").submit(function() {
        if (this.submittedAlready)
            return false;
        else {
            this.submittedAlready = true;
            return true;
        }
    });

    $("form.idsubmit #cancel-submission").submit(function () {
        return confirm("Cancel this submission?");
    });

    $("form.idsubmit #add-author").click(function (e) {
        // clone the last author block and make it empty
        var cloner = $("#cloner");
        var next = cloner.clone();
        next.find('input:not([type=hidden])').val('');

        // find the author number
        var t = next.children('h3').text();
        n = parseInt(t.replace(/\D/g, ''));

        // change the number in attributes and text
        next.find('*').each(function () {
            var e = this;
            $.each(['id', 'for', 'name', 'value'], function (i, v) {
                if ($(e).attr(v)) {
                    $(e).attr(v, $(e).attr(v).replace(n-1, n));
                }
            });
        });

        t = t.replace(n, n+1);
        next.children('h3').text(t);

        // move the cloner id to next and insert next into the DOM
        cloner.removeAttr('id');
        next.attr('id', 'cloner');
        next.insertAfter(cloner);

    });
});

$(".snippet .show-all").click(function () {
    $(this).parents(".snippet").addClass("hidden").siblings(".full").removeClass("hidden");
});

// Store the shown/hidden state for the search form collapsible persistently
// Not such a great idea after all, comment out for now.
// $('#searchcollapse').on('hidden.bs.collapse', function() {
//	localStorage.removeItem(this.id);
// }).on('shown.bs.collapse', function() {
//	localStorage[this.id] = "show";
// }).each(function() {
//	if (localStorage[this.id] === "show") {
//		$(this).collapse('show');
//	} else {
//		$(this).collapse('hide');
//	}
// });

// Use the Bootstrap3 tooltip plugin for all elements with a title attribute
$('[title][title!=""]').tooltip();

$(document).ready(function () {
    // add a required class on labels on forms that should have
    // explicit requirement asterisks
    $("form.show-required").find("input[required],select[required],textarea[required]").closest(".form-group").find("label").addClass("required");
});


$(document).ready(function () {
    // load data for the menu
    $.ajax({
        url: $(document.body).data("group-menu-data-url"),
        type: 'GET',
        dataType: "json",
        success: function (data) {
            for (var parentId in data) {
                var attachTo = $(".group-menu.group-parent-" + parentId);
                if (attachTo.length == 0)
                    continue;

                attachTo.find(".dropdown-menu").remove();

                var menu = ['<ul class="dropdown-menu" role="menu">'];

                var groups = data[parentId];
                for (var i = 0; i < groups.length; ++i) {
                    var g = groups[i];
                    menu.push('<li><a href="' + g.url + '">' + g.acronym +' &mdash; ' + g.name + '</a></li>');
                }

                menu.push('</ul>');

                attachTo.append(menu.join(""));
            }
        },
        error: function (err) {
            $(".group-menu").removeClass("dropdown-submenu");

            if (console.log)
                console.log("Could not load menu data");
        }
    });
});

$(document).ready(function () {
    // if there is a sortable table on the page
    if ($(".tablesorter").length) {
        // customize the styling a bit; more is done in ietf.css
        $.tablesorter.themes.bootstrap = {
            table: "",
            iconSortNone: "fa fa-sort",
            iconSortAsc: "fa fa-sort-asc",
            iconSortDesc: "fa fa-sort-desc",
            hover: "active"
        };
        // disable the URL-based sorting stuff that uses the django backend
        $(".tablesorter thead a").contents().unwrap();
        // strip the caret used by the django backend sorting
        $(".tablesorter thead th span.fa-caret-down").remove();
        // make the table sortable
        $(".tablesorter").tablesorter({
            emptyTo: "zero",
            theme: "bootstrap",
            table: "",
            headerTemplate: "{content} {icon}",
            widgets: ["uitheme"]
        });
    }
});
