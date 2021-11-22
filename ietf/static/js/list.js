import * as List from "list.js";

$(document)
    .ready(function () {
        $("table.tablesorter")
            .each(function () {
                var searcher = $.parseHTML(`
                    <div class="input-group mb-3">
                        <input type="search" class="search form-control" placeholder="Search"/>
                        <button class="btn btn-outline-secondary search-reset" type="button">
                            <i class="bi bi-x"></i>
                        </button>
                    </div>`);

                $(this)
                    .before(searcher);

                var fields = $(this)
                    .find("thead > tr:first")
                    .children("th")
                    .map(function () {
                        return $(this)
                            .attr("data-field");
                    })
                    .toArray();
                console.log(fields);

                var search_field = $(searcher)
                    .find("input.search");

                var reset_search = $(searcher)
                    .find("button.search-reset");

                if (fields.length == 0) {
                    searcher.addClass("visually-hidden");
                } else {
                    console.log($(this)[0]);
                    var list = new List($(this)
                        .parent()[0], { valueNames: fields });

                    reset_search.on("click", function () {
                        search_field.val("");
                        list.search();
                    });

                    search_field.on("keydown", function (e) {
                        if (e.key == "Escape") {
                            reset_search.trigger("click");
                        }
                    });

                    list.on("searchComplete", function () {
                        var last_show_with_children = -1;
                        for (var i = 0; i < list.items.length; i++) {
                            if ($(list.items[i].elm)
                                .hasClass("show-with-children")) {
                                last_show_with_children = i;
                            }

                            if (list.items[i].found &&
                                last_show_with_children >= 0 &&
                                list.items[last_show_with_children].found == false) {
                                list.items[last_show_with_children].found = true;
                                list.items[last_show_with_children].show();
                                last_show_with_children = -1;
                            }

                            if ($(list.items[i].elm)
                                .hasClass("show-always")) {
                                list.items[i].found = true;
                                list.items[i].show();
                            }
                        }
                        list.update();
                    });
                }
            });
    });