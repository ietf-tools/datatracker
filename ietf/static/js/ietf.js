// Only import what we need:
// https://getbootstrap.com/docs/5.1/customize/optimize/

import "bootstrap/js/dist/alert";
import "bootstrap/js/dist/button";
// import "bootstrap/js/dist/carousel";
import "bootstrap/js/dist/collapse";
import "bootstrap/js/dist/dropdown";
import "bootstrap/js/dist/modal";
// import "bootstrap/js/dist/offcanvas";
import "bootstrap/js/dist/popover";
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

import debounce from "lodash/debounce";

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
            .tooltip();
    });

// Help browser to wrap long link texts (esp. email addresses) more sensibly.
$(document)
    .ready(function () {
        $("#content a")
            .each(function () {
                // get the text of the <a> element
                var text = $(this)
                    .text();
                // insert some <wbr> at strategic places
                var newtext = text.replace(/([@._])/g, "$1<wbr>");
                if (newtext === text) {
                    return;
                }
                // now replace only that text inside the element's HTML
                var newhtml = $(this)
                    .html()
                    .replace(text, newtext);
                $(this)
                    .html(newhtml);
            });

        // $("#content table.tablesorter")
        //     .on("tablesorter:done", function () {
        //         $("#content table.tablesorter .date")
        //             .each(function () {
        //                 // get the text of the <a> element
        //                 var text = $(this)
        //                     .text();
        //                 // insert some <wbr> at strategic places
        //                 var newtext = text.replace(/([-])/g, "$1<wbr>");
        //                 if (newtext === text) {
        //                     return;
        //                 }
        //                 // now replace only that text inside the element's HTML
        //                 var newhtml = $(this)
        //                     .html()
        //                     .replace(text, newtext);
        //                 $(this)
        //                     .html(newhtml);
        //             });
        //     });
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
                    var menu = ['<ul class="dropdown-menu ms-n1 mt-n1">'];
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

                if (!("ontouchstart" in document.documentElement)) {
                    $("ul.nav li.dropdown, ul.nav li.dropend")
                        .on("mouseenter mouseleave", dropdown_hover);
                }
            }
        });
    });

// Automatically add a navigation pane to long pages if #content element has the ietf-auto-nav class.
// The parent of #content must have the row class or the navigation pane will render incorrectly.
$(function () {
    const contentElement = $('#content.ietf-auto-nav');
    if (contentElement.length > 0) {
        const headings = contentElement
            .find("h1:visible, h2:visible, h3:visible, h4:visible, h5:visible, h6:visible, .nav-heading:visible")
            .not(".navskip");

        const contents = (headings.length > 0) &&
            ($(headings)
                .html()
                .split("<")
                .shift()
                .trim());

        const extraNav = contentElement.find('#extra-nav');
        const haveExtraNav = extraNav.length > 0;

        const pageTooTall = !!(contents &&
          (contents.length > 0) &&
          ($(headings)
              .last()
              .offset()
              .top > $(window)
              .height()));

        if (pageTooTall || haveExtraNav) {
            // console.log("Enabling nav.");
            let n = 0;
            let last_level;

            contentElement
                .attr("data-bs-offset", 0)
                .attr("tabindex", 0)
                .after($(`
                 <div class="col-xl-2 ps-0 small">
                     <div id="righthand-panel" class="position-fixed col-xl-2 bg-light d-flex flex-column justify-content-between align-items-start">
                         <nav id="righthand-nav" class="navbar navbar-light w-100 overflow-auto align-items-start flex-fill"></nav>
                     </div>
                 </div>
                 `));

            const nav = $("#righthand-nav")
                .append(`<nav class="nav nav-pills flex-column w-100 px-2">`)
                .children()
                .last();

            contentElement
                .find("h1:visible, h2:visible, h3:visible, h4:visible, h5:visible, h6:visible, .nav-heading:visible")
                .not(".navskip")
                .each(function () {
                    // Some headings have line breaks in them - only use first line in that case.
                    const frag = $(this)
                        .html()
                        .split("<br")
                        .shift();
                    const text = $.parseHTML(frag)
                        .map(x => $(x)
                            .text())
                        .join(" ");

                    if (text === undefined || text === "") {
                        // Nothing to do for empty headings.
                        return;
                    }
                    let id = $(this)
                        .attr("id");

                    if (id === undefined) {
                        id = `autoid-${++n}`;
                        $(this)
                            .attr("id", id);
                    }

                    const level = parseInt(this.nodeName.substring(1)) - 1;
                    if (!last_level) {
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

            if (haveExtraNav) {
                $('#righthand-panel').append('<div id="righthand-extra" class="w-100 py-3"></div>');
                extraNav.children().appendTo('#righthand-extra');
                extraNav.remove();
            }

            $(document)
                // Chrome apparently wants this debounced to something >10ms,
                // otherwise the main view doesn't scroll?
                .on("scroll", debounce(function () {
                    const item = $('#righthand-nav')
                        .find(".active")
                        .last();
                    if (item.length) {
                        item[0].scrollIntoView({ block: "center", behavior: "smooth" });
                    }
                }, 100));

            // offset the scrollspy to account for the menu bar
            const contentOffset = contentElement ? contentElement.offset().top : 0;

            $("body")
                .attr("data-bs-spy", "scroll")
                .attr("data-bs-target", "#righthand-nav")
                .attr("data-bs-offset", contentOffset)
                .scrollspy("refresh");

        }
    }
});

// Replace track/untrack functionality with js.
$(document)
    .ready(function () {
        $('.review-wish-add-remove-doc.ajax, .track-untrack-doc')
            .on("click", function (e) {
                e.preventDefault();
                var trigger = $(this);
                $.ajax({
                    url: trigger.attr('href'),
                    type: 'POST',
                    cache: false,
                    dataType: 'json',
                    success: function (response) {
                        if (response.success) {
                            // hide tooltip after clicking icon
                            trigger.parent()
                                .find(".review-wish-add-remove-doc.ajax, .track-untrack-doc")
                                .tooltip("hide");
                            trigger.addClass("d-none");

                            var target_unhide = null;
                            if (trigger.hasClass('review-wish-add-remove-doc')) {
                                target_unhide = '.review-wish-add-remove-doc';
                            } else if (trigger.hasClass('track-untrack-doc')) {
                                target_unhide = '.track-untrack-doc';
                            }
                            if (target_unhide) {
                                trigger.parent()
                                    .find(target_unhide)
                                    .not(trigger)
                                    .removeClass("d-none");
                            }
                        }
                    }
                });
            });
    });

// Bootstrap doesn't load modals via href anymore, so let's do it ourselves.
// See https://stackoverflow.com/a/48934494/2240756
$(document)
    .ready(function () {
        $('.modal')
            .on('show.bs.modal', function (e) {
                var button = $(e.relatedTarget);
                if (!$(button)
                    .attr("href")) {
                    return;
                }
                var loc = $(button)
                    .attr("href")
                    .trim();
                // load content from value of button href
                if (loc !== undefined && loc !== "#") {
                    $(this)
                        .find('.modal-content')
                        .load(loc);
                }
            });
    });

// Handle history snippet expansion.
$(document)
    .ready(function () {
        $(".snippet .show-all")
            .on("click", function () {
                $(this)
                    .parents(".snippet")
                    .addClass("d-none")
                    .siblings(".full")
                    .removeClass("d-none");
            });
    });
