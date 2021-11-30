import * as List from "list.js";

var dummy = new List();

function text_sort(a, b, options) {
    // sort by text content
    return dummy.utils.naturalSort.caseInsensitive($($.parseHTML(a.values()[options.valueName]))
        .text()
        .trim()
        .replaceAll(/\s+/g, ' '), $($.parseHTML(b.values()[options.valueName]))
        .text()
        .trim()
        .replaceAll(/\s+/g, ' '));
}

$(document)
    .ready(function () {
        $("table.tablesorter")
            .each(function () {
                var table = $(this);

                var header_row = $(table)
                    .find("thead > tr:first");

                // get field classes from first thead row
                var fields = $(header_row)
                    .find("*")
                    .map(function () {
                        return $(this)
                            .attr("data-sort") ? $(this)
                            .attr("data-sort") : "";
                    })
                    .toArray();

                if (fields.length == 0 || !fields.filter(field => field != "")) {
                    console.log("No table fields defined, disabling search/sort.");

                } else {

                    $(header_row)
                        .children("[data-sort]")
                        .addClass("sort")
                        .each((i, e) => {
                            if (fields[i] == "date" || fields[i] == "num") {
                                // magic
                                $(e)
                                    .addClass("text-end");
                            }
                        });

                    if ($(header_row)
                        .text()
                        .trim() == "") {
                        console.log("No headers fields visible, hiding header row.");
                        header_row.addClass("visually-hidden");
                    }

                    // HTML for the search widget
                    var searcher = $.parseHTML(`
                    <div class="input-group my-3">
                        <input type="search" class="search form-control" placeholder="Search"/>
                        <button class="btn btn-outline-secondary search-reset" type="button">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>`);

                    $(table)
                        .before(searcher);

                    var search_field = $(searcher)
                        .children("input.search");

                    var reset_search = $(searcher)
                        .children("button.search-reset");

                    // var pager = $.parseHTML(`
                    // <nav aria-label="Pagination control" class="visually-hidden">
                    //     <ul class="pagination"></ul>
                    // </nav>`);

                    // $(table)
                    //     .after(pager);

                    var list_instance = [];
                    var internal_table = [];

                    // var pagination = $(table)
                    //     .children("tbody")
                    //     .length == 1;

                    // list.js cannot deal with tables with multiple tbodys,
                    // so maintain separate internal "tables" for
                    // sorting/searching and update the DOM based on them
                    $(table)
                        .children("tbody, tfoot")
                        .addClass("list")
                        .each(function () {
                            // add the required classes to the cells
                            $(this)
                                .children("tr")
                                .each(function () {
                                    $(this)
                                        .children("th, td")
                                        .each((i, e) => {
                                            $(e)
                                                .addClass(fields[i]);
                                            if (fields[i] == "date" || fields[i] == "num") {
                                                // magic
                                                $(e)
                                                    .addClass("text-end");
                                            }
                                        });
                                });

                            // create the internal table and add list.js to them
                            var thead = $(this)
                                .siblings("thead:first")
                                .clone();

                            var tbody = $(this)
                                .clone();

                            if ($(tbody)
                                .find("tr")
                                .length == 0) {
                                console.log("Skipping empty tbody");
                                return;
                            }

                            var parent = $(table)
                                .clone()
                                .empty()
                                .removeClass("tablesorter")
                                .wrap("<div id='abc'></div")
                                .append(thead, tbody);

                            internal_table.push(parent);

                            // if (pagination) {
                            //     console.log("Enabling pager.");
                            //     $(pager)
                            //         .removeClass("visually-hidden");
                            //     pagination = {
                            //         item: '<li class="page-item"><a class="page-link" href="#"></a></li>'
                            //     };
                            // }

                            list_instance.push(
                                new List(parent[0], {
                                    valueNames: fields,
                                    // pagination: pagination,
                                    // page: 10
                                }));
                        });

                    reset_search.on("click", function () {
                        search_field.val("");
                        $.each(list_instance, (i, e) => {
                            e.search();
                        });
                    });

                    search_field.on("keyup", function (event) {
                        if (event.key == "Escape") {
                            reset_search.trigger("click");
                        } else {
                            $.each(list_instance, (i, e) => {
                                e.search($(this)
                                    .val());
                            });
                        }
                    });

                    $(table)
                        .find(".sort")
                        .on("click", function () {
                            var order = $(this)
                                .hasClass("asc") ? "desc" : "asc";
                            $.each(list_instance, (i, e) => {
                                e.sort($(this)
                                    .attr("data-sort"), { order: order, sortFunction: text_sort });
                            });
                        });

                    $.each(list_instance, (i, e) => {
                        e.on("sortComplete", function () {
                            $(table)
                                .children("tbody")
                                .eq(i)
                                .replaceWith(internal_table[i]
                                    .children("tbody")
                                    .clone());

                            if (i == list_instance.length - 1) {
                                $(table)
                                    .find("thead:first tr")
                                    .children("th, td")
                                    .each((idx, el) => {
                                        var cl = internal_table[i].find("thead:first tr")
                                            .children("th, td")
                                            .eq(idx)
                                            .attr("class");
                                        $(el)
                                            .attr("class", cl);

                                    });
                            }
                        });

                        e.on("searchComplete", function () {
                            var last_show_with_children = {};
                            e.items.forEach((item) => {
                                if ($(item.elm)
                                    .hasClass("show-with-children")) {
                                    var kind = $(item.elm)
                                        .attr("class")
                                        .split(/\s+/)
                                        .join();
                                    last_show_with_children[kind] = item;
                                }

                                if (item.found) {
                                    Object.entries(last_show_with_children)
                                        .forEach(([key, val]) => {
                                            val.found = true;
                                            val.show();
                                            delete last_show_with_children[key];
                                        });
                                }

                                if ($(item.elm)
                                    .hasClass("show-always")) {
                                    item.found = true;
                                    item.show();
                                }
                            });

                            e.update();
                            $(table)
                                .children("tbody")
                                .eq(i)
                                .replaceWith(internal_table[i]
                                    .children("tbody")
                                    .clone());
                        });
                    });
                }
            });
    });