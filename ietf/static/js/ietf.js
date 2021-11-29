// Only import what we need:
// https://getbootstrap.com/docs/5.1/customize/optimize/

import "bootstrap/js/dist/alert";
import "bootstrap/js/dist/button";
// import "bootstrap/js/dist/carousel";
import "bootstrap/js/dist/collapse";
import "bootstrap/js/dist/dropdown";
import "bootstrap/js/dist/modal";
// import "bootstrap/js/dist/offcanvas";
// import "bootstrap/js/dist/popover";
import "bootstrap/js/dist/scrollspy";
import "bootstrap/js/dist/tab";
// import "bootstrap/js/dist/toast";
import "bootstrap/js/dist/tooltip";

import jquery from "jquery";

window.$ = window.jQuery = jquery;
if (!process.env.BUILD_DEPLOY) {
    // get warnings for using deprecated jquery features
    require("jquery-migrate");
}

import Cookies from "js-cookie";

// setup CSRF protection using jQuery
function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

jQuery.ajaxSetup({
    crossDomain: false, // obviates need for sameOrigin test
    beforeSend: function (xhr, settings) {
        if (!csrfSafeMethod(settings.type)) {
            xhr.setRequestHeader("X-CSRFToken", Cookies.get("csrftoken"));
        }
    }
});

// Use the Bootstrap tooltip plugin for all elements with a title attribute
$(document)
    .ready(function () {
        $('[title][title!=""]')
            .not("th")
            .attr("data-bs-toggle", "tooltip")
            .tooltip();
    });

$(document)
    .ready(function () {

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
                            menu.push('<li class="dropdown-header">' + g.type + "s</li>");
                            gtype = g.type;
                        }
                        menu.push('<li><a class="dropdown-item" href="' + g.url + '">' +
                            g.acronym + " &mdash; " + g.name + "</a></li>");
                    }
                    menu.push("</ul>");
                    for (i = 0; i < attachTo.length; i++) {
                        attachTo.closest(".dropdown-menu");
                    }
                    attachTo.append(menu.join(""));
                }
            }
        });

        if (!("ontouchstart" in document.documentElement)) {
            $("ul.nav li.dropdown, ul.nav li.dropend")
                .on("mouseenter mouseleave", dropdown_hover);
        }
    });

// Automatically add a navigation pane to long pages
$(document)
    .ready(function () {

        var headings = $("#content")
            .find("h1, h2, h3, h4, h5, h6");

        if ($(headings)
            .length > 0 && $(headings)
            .last()
            .offset()
            .top > $(window)
            .height()) {
            console.log("Enabling nav.");
            var n = 0;
            var last_level;
            var nav;

            $("#content")
                .attr("data-bs-offset", 0)
                .attr("tabindex", 0)
                .after($(`
                 <div class="col-md-2 small">
                     <nav id="righthand-nav" class="position-fixed navbar navbar-light bg-light overflow-auto" style="height: 70vh;">
                     <!--<a class="navbar-brand" href="#">Navbar</a>-->
                     </nav>
                 </div>
                 `))
                .find("h1, h2, h3, h4, h5, h6")
                .each(function () {
                    var id = $(this)
                        .attr("id");

                    if (id === undefined) {
                        id = `autoid-${++n}`;
                        $(this)
                            .attr("id", id);
                    }

                    var text = $(this)
                        .text();

                    if (nav === undefined) {
                        nav = $("#righthand-nav");
                        nav = $(nav)
                            .append(`<nav class="nav nav-pills flex-column align-self-start">`)
                            .children()
                            .last();
                    }

                    var level = parseInt(this.nodeName.substring(1)) - 1;
                    if (last_level == undefined) {
                        last_level = level;
                    }

                    if (level > last_level) {
                        last_level = level;
                    } else
                        while (level < last_level) {
                            last_level--;
                        }

                    $(nav)
                        .append(`<a class="nav-link" href="#${id}">${text}</a>`);
                });

            $(window)
                .on("scroll", function () {
                    var item = $('#righthand-nav')
                        .find(".active")
                        .last();
                    if (item.length) {
                        item[0].scrollIntoView({ block: "center" });
                    }
                });
        }
    });