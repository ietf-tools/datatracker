$(function () {
    var $input = $('#navbar-doc-search');
    var $results = $('#navbar-doc-search-results');
    var ajaxUrl = $input.data('ajax-url');
    var debounceTimer = null;
    var highlightedIndex = -1;
    var keyboardHighlight = false;
    var currentItems = [];

    function showDropdown() {
        $results.addClass('show');
    }

    function hideDropdown() {
        $results.removeClass('show');
        highlightedIndex = -1;
        keyboardHighlight = false;
        updateHighlight();
    }

    function updateHighlight() {
        $results.find('.dropdown-item').removeClass('active');
        if (highlightedIndex >= 0 && highlightedIndex < currentItems.length) {
            $results.find('.dropdown-item').eq(highlightedIndex).addClass('active');
        }
    }

    function doSearch(query) {
        if (query.length < 2) {
            hideDropdown();
            return;
        }
        $.ajax({
            url: ajaxUrl,
            dataType: 'json',
            data: { q: query },
            success: function (data) {
                currentItems = data;
                highlightedIndex = -1;
                $results.empty();
                if (data.length === 0) {
                    $results.append('<li><span class="dropdown-item text-muted">No results found</span></li>');
                } else {
                    data.forEach(function (item) {
                        var $li = $('<li>');
                        var $a = $('<a class="dropdown-item" href="' + item.url + '">' + item.text + '</a>');
                        $li.append($a);
                        $results.append($li);
                    });
                }
                showDropdown();
            }
        });
    }

    $input.on('input', function () {
        clearTimeout(debounceTimer);
        var query = $(this).val().trim();
        debounceTimer = setTimeout(function () {
            doSearch(query);
        }, 250);
    });

    $input.on('keydown', function (e) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (highlightedIndex < currentItems.length - 1) {
                highlightedIndex++;
                keyboardHighlight = true;
                updateHighlight();
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (highlightedIndex > 0) {
                highlightedIndex--;
                keyboardHighlight = true;
                updateHighlight();
            }
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (keyboardHighlight && highlightedIndex >= 0 && highlightedIndex < currentItems.length) {
                window.location.href = currentItems[highlightedIndex].url;
            } else {
                var query = $(this).val().trim();
                if (query) {
                    window.location.href = '/doc/search/?name=' + encodeURIComponent(query) + '&rfcs=on&activedrafts=on&olddrafts=on';
                }
            }
        } else if (e.key === 'Escape') {
            hideDropdown();
            $input.blur();
        }
    });

    // Hover highlights (visual only — Enter still submits the text)
    $results.on('mouseenter', '.dropdown-item', function () {
        highlightedIndex = $results.find('.dropdown-item').index(this);
        keyboardHighlight = false;
        updateHighlight();
    });

    $results.on('mouseleave', '.dropdown-item', function () {
        highlightedIndex = -1;
        updateHighlight();
    });

    // Click outside closes dropdown
    $(document).on('click', function (e) {
        if (!$(e.target).closest('#navbar-doc-search-wrapper').length) {
            hideDropdown();
        }
    });
});
