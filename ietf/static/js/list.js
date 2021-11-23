import * as List from "list.js";

var dummy = new List();

function text_sort(a, b, options) {
    return dummy.utils.naturalSort.caseInsensitive($($.parseHTML(a.values()[options.valueName]))
        .text()
        .trim()
        .replaceAll(/\w+/g, ' '), $($.parseHTML(b.values()[options.valueName]))
        .text()
        .trim()
        .replaceAll(/\w+/g, ' '));
}

$(document)
    .ready(function () {
        $("table.tablesorter")
            .each(function () {
                var table = $(this);

                var header_row = $(table)
                    .find("thead > tr:first");

                var fields = $(header_row)
                    .find("*")
                    .map(function () {
                        return $(this)
                            .attr("data-sort");
                    })
                    .toArray();

                if (fields.length == 0) {
                    console.log("No table fields defined, disabling search/sort.");

                } else {

                    $(header_row)
                        .children("[data-sort]")
                        .addClass("sort");

                    if ($(header_row)
                        .text()
                        .trim() == "") {
                        console.log("No headers fields visible, hiding header row.");
                        header_row.addClass("visually-hidden");
                    }

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

                    var list_instance = [];
                    var internal_table = [];

                    $(table)
                        .children("tbody")
                        .addClass("list")
                        .each(function () {
                            var thead = $(this)
                                .siblings("thead:first")
                                .clone();

                            var tbody = $(this)
                                .clone();

                            var parent = $(table)
                                .clone()
                                .empty()
                                .removeClass("tablesorter")
                                .append(thead, tbody);

                            internal_table.push(parent);

                            list_instance.push(
                                new List(parent[0], { valueNames: fields }));
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