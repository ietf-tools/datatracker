// Copyright The IETF Trust 2026, All Rights Reserved
// Tabs on the past meetings page (meeting/past.html)

$(document)
    .ready(function () {
        // The interim table is large, so fetch it the first time its tab is shown.
        // list.js sets up searchable, sortable tables when it loads, so load it
        // after the table is in place.
        var interimsRequested = false;
        $('#interim-tab')
            .on('show.bs.tab', function () {
                if (interimsRequested) {
                    return;
                }
                interimsRequested = true;
                var pane = $('#interim');
                $.get(pane.data('src'))
                    .done(function (html) {
                        pane.html(html);
                        // list.js scrolls to the URL hash after setting up tables;
                        // keep the reader where they were instead
                        var scrollY = window.scrollY;
                        var script = document.createElement('script');
                        script.onload = function () {
                            // list.js's ready handler runs asynchronously, so restore after it
                            setTimeout(function () {
                                window.scrollTo(0, scrollY);
                            });
                        };
                        script.src = pane.data('listjs-src');
                        document.body.appendChild(script);
                    })
                    .fail(function () {
                        interimsRequested = false;
                        pane.html('<p class="alert alert-danger my-3">Could not load the interim meetings. Select the tab again to retry.</p>');
                    });
            });

        // Show the tab named in the URL hash, including when the site menu links
        // here while this page is already open
        function showTabForHash() {
            var url = document.location.toString();
            if (url.match('#')) {
                $('.nav-tabs button[data-bs-target="#' + url.split('#')[1] + '"]')
                    .tab('show');
            }
        }
        showTabForHash();
        $(window)
            .on('hashchange', showTabForHash);

        // Keep the selected tab in the URL, so a reload shows it again
        $('.nav-tabs button')
            .on('shown.bs.tab', function (e) {
                history.replaceState(null, null, e.currentTarget.dataset.bsTarget);
            });
    });
