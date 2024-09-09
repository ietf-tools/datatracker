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

import { populate_nav } from "./nav.js";

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
        $("[title]:not([title=''])")
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
                var newtext = text.replace(/(\S)([@._+])(\S)/g, "$1$2<wbr>$3");
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

function overflowShadows(el) {
    function handleScroll(){
        const canScrollUp = el.scrollTop > 0
        const canScrollDown = el.offsetHeight + el.scrollTop < el.scrollHeight
        el.classList.toggle("overflow-shadows--both", canScrollUp && canScrollDown)
        el.classList.toggle("overflow-shadows--top-only", canScrollUp && !canScrollDown)
        el.classList.toggle("overflow-shadows--bottom-only", !canScrollUp && canScrollDown)
    }

    el.addEventListener("scroll", handleScroll, {passive: true})
    handleScroll()

    const observer = new IntersectionObserver(handleScroll)
    observer.observe(el) // el won't have scrollTop etc when hidden, so we need to recalculate when it's revealed

    return () => {
        el.removeEventListener("scroll", handleScroll)
        observer.unobserve(el)
    }
}

$(document)
    .ready(function () {
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
                    var menu = ['<ul class="dropdown-menu ms-n1 mt-n1 overflow-shadows">'];
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

                    attachTo.find(".overflow-shadows").each(function(){ overflowShadows(this)})
                }
            }
        });
    });

// Automatically add a navigation pane to long pages if #content element has the ietf-auto-nav class.
// The parent of #content must have the row class or the navigation pane will render incorrectly.
$(function () {
    const contentElement = $('#content.ietf-auto-nav');
    if (contentElement.length > 0) {
        const heading_selector = ":is(h2, h3, h4, h5, h6, .h2, .h3, .h4, .h5, .h6, .nav-heading):not([style='display:none']):not(.navskip)";
        const headings = contentElement
            .find(heading_selector)
            .filter((i, el) => !el.closest(".navskip,.modal"));

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

            contentElement
                .attr("data-bs-offset", 0)
                .attr("tabindex", 0)
                .after($(`
                 <div class="col-xl-2 ps-0 small">
                     <div id="righthand-panel" class="position-fixed col-xl-2 bg-light-subtle d-flex flex-column justify-content-between align-items-start">
                         <nav id="righthand-nav" class="navbar w-100 overflow-auto align-items-start flex-fill"></nav>
                     </div>
                 </div>
                 `));

            const nav = $("#righthand-nav")
                .append(`<nav class="nav nav-pills flex-column w-100 px-2">`)
                .children()
                .last();

            populate_nav(nav[0], headings.toArray());

            if (haveExtraNav) {
                $('#righthand-panel').append('<div id="righthand-extra" class="w-100 py-3"></div>');
                extraNav.children().appendTo('#righthand-extra');
                extraNav.remove();
            }

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
// Instead of attaching to the modal elements as in that example, though,
// listen on document and filter with the .modal selector. This allows handling
// of modals that are added dynamically (e.g., list.js apparently replaces DOM 
// elements with identical copies, minus any attached listeners).
$(document)
    .on('show.bs.modal', '.modal', function (e) {
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
