// Only import what we need:
// https://getbootstrap.com/docs/5.1/customize/optimize/

// import "bootstrap/js/dist/alert";
import "bootstrap/js/dist/button";
// import "bootstrap/js/dist/carousel";
import "bootstrap/js/dist/collapse";
import "bootstrap/js/dist/dropdown";
// import "bootstrap/js/dist/modal";
// import "bootstrap/js/dist/offcanvas";
// import "bootstrap/js/dist/popover";
// import "bootstrap/js/dist/scrollspy";
import "bootstrap/js/dist/tab";
// import "bootstrap/js/dist/toast";
// import "bootstrap/js/dist/tooltip";

import jquery from "jquery"

window.$ = window.jQuery = jquery;
if (!process.env.BUILD_DEPLOY) {
    // get warnings for using deprecated jquery features
    require("jquery-migrate")
}

function dropdown_hover() {
    var navbar = $(this)
        .closest(".navbar");
    if (navbar.length === 0 || navbar.find(".navbar-toggler")
        .is(":hidden")) {
        $(this)
            .children(".dropdown-toggle")
            .dropdown("toggle");
    }
}

if (!("ontouchstart" in document.documentElement)) {
    $("ul.nav li.dropdown, ul.nav li.dropend")
        .on("mouseenter mouseleave", dropdown_hover);
}

// load data for the menu
$.ajax({
    url: $(document.body)
        .data("group-menu-data-url"),
    type: "GET",
    dataType: "json",
    success: function (data) {
        for (var parentId in data) {
            var attachTo = $(".group-menu.group-parent-" + parentId);
            if (attachTo.length == 0) {
                console.log("Could not find parent " + parentId);
                continue;
            }
            attachTo.find(".dropdown-menu")
                .remove();
            var menu = ['<ul class="dropdown-menu ms-n1">'];
            var groups = data[parentId];
            var gtype = "";
            for (var i = 0; i < groups.length; ++i) {
                var g = groups[i];
                if (g.type != gtype) {
                    if (i > 0)
                        menu.push('<li class="dropdown-divider"></li>');
                    menu.push('<li class="dropdown-header">' + g.type + 's</li>');
                    gtype = g.type;
                }
                menu.push('<li><a class="dropdown-item" href="' + g.url + '">' +
                    g.acronym + ' &mdash; ' + g.name + '</a></li>');
            }
            menu.push("</ul>");
            for (var i = 0; i < attachTo.length; i++) {
                attachTo.closest(".dropdown-menu");
            }
            attachTo.append(menu.join(""));
        }
    }
});

// This used to be in doc-search.js; consolidate all JS in one file.
$(document)
    .ready(function () {
        // search form
        var form = $("#search_form");

        function anyAdvancedActive() {
            var advanced = false;
            var by = form.find("input[name=by]:checked");

            if (by.length > 0) {
                by.closest(".search_field")
                    .find("input,select")
                    .not("input[name=by]")
                    .each(function () {
                        if (String.prototype.trim(this.value)) {
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
            var nameSearch = $("#id_name")
                .val()
                .trim();
            form.find("button[type=submit]")
                .get(0)
                .disabled = !nameSearch && !anyAdvancedActive();
        }

        function updateAdvanced() {
            form.find("input[name=by]:checked")
                .closest(".search_field")
                .find("input,select")
                .not("input[name=by]")
                .each(function () {
                    this.disabled = false;
                    this.focus();
                });

            form.find("input[name=by]")
                .not(":checked")
                .closest(".search_field")
                .find("input,select")
                .not("input[name=by]")
                .each(function () {
                    this.disabled = true;
                });

            toggleSubmit();
        }

        if (form.length > 0) {
            form.find(".search_field input[name=by]")
                .closest(".search_field")
                .find("label,input")
                .on("click", updateAdvanced);

            form.find(".search_field input,select")
                .on("change click keyup", toggleSubmit);

            form.find(".toggle_advanced")
                .on("click", function () {
                    var advanced = $(this)
                        .next();
                    advanced.find('.search_field input[type="radio"]')
                        .attr("checked", false);
                    updateAdvanced();
                });

            updateAdvanced();
        }
    });