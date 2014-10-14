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
            })
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


function to_disp(t) {
	// typehead/tokenfield don't fully deal with HTML entities
	return $('<div/>').html(t).text().replace(/[<>"]/g, function (m) {
		return {
			'<': '(',
			'>': ')',
			'"': ''
		}[m];
	});
}


$(".tokenized-form").submit(function (e) {
 	$(this).find(".tokenized-field").each(function () {
 		var f = $(this);
 		var io = f.data("io");
 		var format = f.data("format");
		var t = f.tokenfield("getTokens");

		var v = $.map(t, function(o) { return o["value"]; })
		if (format === "json") {
			v = JSON.stringify(v);
		} else if (format === "csv") {
			v = v.join(", ");
		} else {
			console.log(io, "unknown format");
			v = v.join(" ");
		}
		f.val(v);
		if (io) {
			$(io).val(v);
		}
 	});
});


$(".tokenized-field").each(function () {
	// autocomplete interferes with the token popup
	$(this).attr("autocomplete", "off");

	// in which field ID are we expected to place the result
	// (we also read the prefill information from there)
	var io = $(this).data("io");
	var raw = "";
	if (io) {
		raw = $(io).val();
	} else {
		io = "#" + this.id;
		raw = $(this).val();
	}
	console.log("io: ", io);
	console.log(io, "raw", raw);
	$(this).data("io", io);

	// which field of the JSON are we supposed to display
	var display = $(this).data("display");
	if (!display) {
		display = "name";
	}
	console.log(io, "display", display);
	$(this).data("display", display)

	// which field of the JSON are we supposed to return
	var result = $(this).data("result");
	if (!result) {
		result = "id";
	}
	console.log(io, "result", result);
	$(this).data("result", result);

	// what kind of data are we returning (json or csv)
	var format = $(this).data("format");
	if (!format) {
		format = "csv";
	}
	console.log(io, "format", format);
	$(this).data("format", format);

	// make tokens to prefill the input
	if (raw) {
		raw = $.parseJSON(raw);
		var pre = [];
		if (!raw[0] || !raw[0][display]) {
			$.each(raw, function(k, v) {
				var obj = {};
				obj["value"] = k;
				obj["label"] = to_disp(v);
				pre.push(obj);
			});
		} else {
			for (var i in raw) {
				var obj = {};
				obj["value"] = raw[i][result];
				obj["label"] = to_disp(raw[i][display]);
				pre.push(obj);
			}
		}
		$(this).val(pre);
	}
	console.log(io, "pre", pre);

	// check if the ajax-url contains a query parameter, add one if not
	var url = $(this).data("ajax-url");
	if (url.indexOf("?") === -1) {
		url += "?q=";
	}
	$(this).data("ajax-url", url)
	console.log(io, "ajax-url", url);

	var bh = new Bloodhound({
		datumTokenizer: function (d) {
			return Bloodhound.tokenizers.nonword(d[display]);
		},
		queryTokenizer: Bloodhound.tokenizers.nonword,
		limit: 20,
		remote: {
			url: url + "%QUERY",
			filter: function (data) {
				return $.map($.grep(data, function (n, i) {
					return true;
				}), function (n, i) {
					n["label"] = to_disp(n[display]);
					n["value"] = n[result];
					return n;
				});
			}
		}
	});
	bh.initialize();
	$(this).tokenfield({
		typeahead: [{
			highlight: true,
			minLength: 3,
			hint: true,
		}, {
			source: bh.ttAdapter(),
			displayKey: "label",
		}],
		beautify: true,
		delimiter: [',', ';']
	}).tokenfield("setTokens", pre);

	// only allow tokens from the popup to be added to the field, no free text
	$(this).on('tokenfield:createtoken', function (event) {
		var existingTokens = $(this).tokenfield('getTokens');
		$.each(existingTokens, function(index, token) {
			if (event.attrs.id === undefined) {
				event.preventDefault();
			}
    	});
    });
});


// Use the Bootstrap3 tooltip plugin for all elements with a title attribute
$('[title][title!=""]').tooltip();
