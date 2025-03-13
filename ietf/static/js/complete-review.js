$(document)
    .ready(function () {
        var form = $("form.complete-review");

        var reviewedRev = form.find("[name=reviewed_rev]");
        reviewedRev.closest(".mb-3")
            .find("a.rev")
            .on("click", function (e) {
                e.preventDefault();
                reviewedRev.val($(this)
                    .text());
            });

        // mail archive search functionality
        var mailArchiveSearchTemplate = form.find(".template .mail-archive-search")
            .parent()
            .html();
        var mailArchiveSearchResultTemplate = form.find(".template .mail-archive-search-result")
            .parent()
            .html();

        form.find("[name=review_url]")
            .closest(".mb-3")
            .before(mailArchiveSearchTemplate);

        var mailArchiveSearch = form.find(".mail-archive-search");
        const isReviewer = mailArchiveSearch.data('isReviewer');
        const searchMailArchiveUrl = mailArchiveSearch.data('searchMailArchiveUrl');

        var retrievingData = null;

        function searchMailArchive() {
            if (retrievingData)
                return;

            var queryInput = mailArchiveSearch.find(".query-input");
            if (queryInput.length == 0 || !queryInput.val().trim())
                return;

            mailArchiveSearch.find(".search")
                .prop("disabled", true);
            mailArchiveSearch.find(".error")
                .addClass("d-none");
            mailArchiveSearch.find(".retrieving")
                .removeClass("d-none");
            mailArchiveSearch.find(".results")
                .addClass("d-none");

            retrievingData = $.ajax({
                    url: searchMailArchiveUrl,
                    method: "GET",
                    data: {
                        query: queryInput.val()
                    },
                    dataType: "json",
                    timeout: 20 * 1000
                })
                .then(function (data) {
                    retrievingData = null;
                    mailArchiveSearch.find(".search")
                        .prop("disabled", false);
                    mailArchiveSearch.find(".retrieving")
                        .addClass("d-none");

                    var err = data.error;
                    if (!err && (!data.messages || !data.messages.length))
                        err = "No messages matching document name found in archive";

                    var non_reply_row = null;
                    if (err) {
                        var errorDiv = mailArchiveSearch.find(".error");
                        errorDiv.removeClass("d-none");
                        errorDiv.find(".content")
                            .text(err);
                        if (data.query && data.query_url && data.query_data_url) {
                            errorDiv.find(".try-yourself .query")
                                .text(data.query);
                            errorDiv.find(".try-yourself .query-url")
                                .prop("href", data.query_url);
                            errorDiv.find(".try-yourself .query-data-url")
                                .prop("href", data.query_data_url);
                            errorDiv.find(".try-yourself")
                                .removeClass("d-none");
                        }
                    } else {
                        mailArchiveSearch.find(".results")
                            .removeClass("d-none");

                        var results = mailArchiveSearch.find(".results .list-group");
                        results.children()
                            .remove();

                        for (var i = 0; i < data.messages.length; ++i) {
                            var msg = data.messages[i];
                            var row = $(mailArchiveSearchResultTemplate)
                                .attr("title", "Click to fill in link and content from this message");
                            row.find(".subject")
                                .text(msg.subject);
                            row.find(".date")
                                .text(msg.utcdate[0]);
                            row.find(".from")
                                .text(msg.splitfrom[0]);
                            row.data("url", msg.url);
                            row.data("content", msg.content);
                            row.data("date", msg.utcdate[0]);
                            row.data("time", msg.utcdate[1]);
                            row.data("revision_guess", msg.revision_guess);
                            results.append(row);
                            if (msg.subject.toUpperCase()
                                .substr(0, 3) !== 'RE:') {
                                non_reply_row = row;
                            }
                        }
                        if (!isReviewer && non_reply_row) {
                            // Automatically select the first non-reply.
                            non_reply_row.click();
                        }
                    }
                }, function () {
                    retrievingData = null;
                    mailArchiveSearch.find(".search")
                        .prop("disabled", false);
                    mailArchiveSearch.find(".retrieving")
                        .addClass("d-none");

                    var errorDiv = mailArchiveSearch.find(".error");
                    errorDiv.removeClass("d-none");
                    errorDiv.find(".content")
                        .text("Error trying to retrieve data from mailing list archive.");
                });
        }

        mailArchiveSearch.find(".search")
            .on("click", function () {
                searchMailArchive();
            });

        mailArchiveSearch.find(".results")
            .on("click", ".mail-archive-search-result", function (e) {
                e.preventDefault();

                var row = $(this);
                if (!row.is(".mail-archive-search-result"))
                    row = row.closest(".mail-archive-search-result");

                form.find("[name=review_url]")
                    .val(row.data("url"));
                form.find("[name=review_content]")
                    .val(row.data("content"))
                    .prop("scrollTop", 0);
                form.find("[name=completion_date]")
                    .val(row.data("date"));
                form.find("[name=completion_time]")
                    .val(row.data("time"));
                form.find("[name=reviewed_rev]")
                    .val(row.data("revision_guess"));
            });

        // review submission selection
        form.find("[name=review_submission]")
            .on("click change", function () {
                var val = form.find("[name=review_submission]:checked")
                    .val();

                var shouldBeVisible = {
                    enter: ['[name="review_content"]', '[name="cc"]'],
                    upload: ['[name="review_file"]', '[name="cc"]'],
                    link: [".mail-archive-search", '[name="review_url"]', '[name="review_content"]']
                };

                for (var v in shouldBeVisible) {
                    for (var i in shouldBeVisible[v]) {
                        var selector = shouldBeVisible[v][i];
                        var row = form.find(selector);
                        if (!row.is(".mb-3"))
                            row = row.closest(".mb-3");

                        if ($.inArray(selector, shouldBeVisible[val]) != -1)
                            row.show();
                        else
                            row.hide();
                    }
                }

                if (val == "link")
                    searchMailArchive();
            })
            .trigger("change");

        if (!isReviewer) {
            // Select mail search by default for secretary completions.
            form.find("[name=review_submission][value=link]")
                .trigger("click");
        }
    });
