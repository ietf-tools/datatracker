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

function replace_with_internal(table, internal_table, i) {
    $(table)
        .children("tbody")
        .eq(i)
        .replaceWith(internal_table[i]
            .children("table")
            .children("tbody")
            .clone());
}

function field_magic(i, e, fields) {
    if ($(e)
        .attr("colspan") === undefined &&
        (fields[i] == "num" || fields[i] == "count" ||
            fields[i] == "percent" || fields[i] == "id" ||
            fields[i].endsWith("-num") || fields[i].endsWith("-date"))) {
        $(e)
            .addClass("text-end");
    }
}

$(document)
    .ready(function () {
        var n = 1;
        var items_per_page = 10;
        $("table.tablesorter")
            .each(function () {
                var table = $(this);

                if ($(table)
                    .hasClass("tablesorter-done")) {
                    // console.log("tablesorter already initialized; list.js probably loaded twice.");
                    return;
                }

                var header_row = $(table)
                    .find("thead > tr:first");

                // we need to strip the trailing whitespace, so the sort chevron doesn't wrap
                $(header_row)
                    .find("th, td")
                    .each(function () {
                        const html = $(this).html().trim();
                        $(this).html(html);
                    });

                // get field classes from first thead row
                var fields = $(header_row)
                    .find("th, td")
                    .map(function () {
                        return $(this)
                            .attr("data-sort") ? $(this)
                            .attr("data-sort") : "";
                    })
                    .toArray();

                if (fields.length == 0 || !fields.filter(field => field != "")) {
                    // console.log("No table fields defined, disabling search/sort.");
                    return;
                }

                $(table)
                    .wrap(`<div id='tablewrapper-${n}'></div`);
                $(header_row)
                    .children("[data-sort]")
                    .addClass("sort");
                // $(header_row)
                //     .children("th, td")
                //     .wrapInner('<span class="tablesorter-th"></span>');
                //     // .each((i, e) => field_magic(i, e, fields));

                if ($(header_row)
                    .text()
                    .trim() == "") {
                    // console.log("No headers fields visible, hiding header row.");
                    header_row.addClass("d-none");
                }

                // only add a search box if the table length warrants it
                var enable_search = $(table).find("tr").length > 5;
                if (enable_search) {
                    // HTML for the search widget
                    var searcher = $.parseHTML(`
                        <div class="input-group input-group-sm">
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
                }

                // TODO: The pager functionality is not working yet
                // var pager = $.parseHTML(`
                //     <nav aria-label="Pagination control" class="d-none">
                //         <ul class="pagination d-flex flex-wrap text-center"></ul>
                //     </nav>`);

                // $(table)
                //     .before(pager);

                var list_instance = [];
                var internal_table = [];

                var pagination = $(table)
                    .children("tbody")
                    .length == 1;

                pagination = false; // FIXME-LARS: pagination not working yet.

                // list.js cannot deal with tables with multiple tbodys,
                // so maintain separate internal "table" copies for
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
                                        field_magic(i, e, fields);
                                    });
                            });

                        // create the internal table and add list.js to them
                        var thead = $(this)
                            .siblings("thead:first")
                            .clone();

                        var tbody = $(this)
                            .clone();

                        var tbody_rows = $(tbody)
                            .find("tr")
                            .length;

                        if (tbody_rows == 0) {
                            // console.log("Skipping empty tbody");
                            return;
                        } else if (tbody_rows <= items_per_page) {
                            pagination = false;
                        }

                        var parent = $(table)
                            .parent()
                            .clone();

                        $(parent)
                            .children("table")
                            .empty()
                            .removeClass("tablesorter")
                            .append(thead, tbody);

                        internal_table.push(parent);

                        var hook = `tablewrapper-${n}`;
                        if (pagination) {
                            // console.log("Enabling pager.");
                            $(pager)
                                .removeClass("d-none");
                            pagination = {
                                innerWindow: 5,
                                left: 1,
                                right: 1,
                                item: '<li class="page-item flex-fill"><a class="page page-link" href="#"></a></li>'
                            };
                        } else {
                            hook = parent[0];
                        }

                        list_instance.push(
                            new List(hook, pagination ? {
                                valueNames: fields,
                                pagination: pagination,
                                page: items_per_page
                            } : {
                                valueNames: fields
                            }));
                    });

                if (enable_search) {
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
                }

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
                        replace_with_internal(table, internal_table, i);
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
                        replace_with_internal(table, internal_table, i);
                    });
                });
                $(table.addClass("tablesorter-done"));
                n++;
                $(table)[0]
                    .dispatchEvent(new Event("tablesorter:done"));
            });

        // if the URL contains a #, scroll to it again, since we modified the DOM
        var id = window.location.hash;
        if (id) {
            $(id)[0].scrollIntoView();
        }
    });
