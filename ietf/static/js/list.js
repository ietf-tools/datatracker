import * as List from "list.js";

// function set_width() {
//     w = $(this)
//         .children("tr:first")
//         .children("th, td")
//         .map(function () {
//             return $(this)
//                 .css("width");
//         });
//     console.log(w);

//     $(tbody)
//         .children("tr:first")
//         .children("th, td")
//         .each(function (i) {
//             console.log(i, w[i]);
//             $(this)
//                 .css("width", w[i]);
//         });
// }

// FIXME sort only works on first table

var table_cnt = 0;

$(document)
    .ready(function () {
        $("table.tablesorter")
            .each(function () {
                var header_row = $(this)
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

                    $(this)
                        .before(searcher);

                    var search_field = $(searcher)
                        .children("input.search");

                    var reset_search = $(searcher)
                        .children("button.search-reset");

                    var instance = [];

                    var first_table;
                    var last_table;
                    $(this)
                        .children("tbody")
                        .addClass("list")
                        .each(function () {
                            var parent;
                            if (first_table === undefined) {
                                first_table = $(this)
                                    .parent();
                                last_table = first_table;
                                parent = first_table[0];
                            } else {
                                var new_table = $(first_table)
                                    .clone()
                                    .empty()
                                    .removeClass("tablesorter");
                                $(last_table)
                                    .after(new_table);
                                var thead = $(this)
                                    .prev("thead")
                                    .detach();
                                var tbody = $(this)
                                    .detach();
                                new_table.append(thead, tbody);
                                parent = $(new_table)[0];
                                last_table = new_table;
                            }

                            $(parent)
                                .addClass("tablesorter-table-" + table_cnt);

                            instance.push(
                                new List(parent, { valueNames: fields }));
                        });

                    table_cnt++;

                    reset_search.on("click", function () {
                        search_field.val("");
                        $.each(instance, (i, e) => {
                            e.search();
                        });
                    });

                    search_field.on("keyup", function (event) {
                        if (event.key == "Escape") {
                            reset_search.trigger("click");
                        } else {
                            $.each(instance, (i, e) => {
                                e.search($(this)
                                    .val());
                            });
                        }
                    });

                    $.each(instance, (i, e) => {
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
                        });
                    });
                }
            });
    });