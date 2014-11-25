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
			return advanced;
		}
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
	$('.addtolist a').click(function(e) {
		e.preventDefault();
		var trigger = $(this);
		$.ajax({
			url: trigger.attr('href'),
			type: 'GET',
			cache: false,
			dataType: 'json',
			success: function(response){
				if (response.success) {
					trigger.replaceWith('<span class="fa fa-tag text-danger"></span>');
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


// This used to be in js/history.js
$(".snippet .show-all").click(function () {
	$(this).parents(".snippet").addClass("hidden").siblings(".full").removeClass("hidden");
});


// This used to be in js/iesg-discusses.js
// AND IT'S BROKEN: causes document history to be hidden
// $("label.btn:has(input)").click(function () {
//	val = $(this).children().attr("value");
//	if (val == "all") {
//		$("tr").show();
//	} else {
//		$("tr").filter("." + val).show();
//		$("tr").not("." + val).hide();
//	}
// });

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

function setupSelect2Field(e) {
    var url = e.data("ajax-url");
    if (!url)
        return;

    var maxEntries = e.data("max-entries");
    var multiple = maxEntries != 1;
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
                    more: results.length == 10
                };
            }
        },
        escapeMarkup: function (m) {
            return m;
        },
        initSelection: function (element, cb) {
            if (!multiple && prefetched.length > 0)
                cb(prefetched[0]);
            else
                cb(prefetched);

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

// Use the Bootstrap3 tooltip plugin for all elements with a title attribute
$('[title][title!=""]').tooltip();
