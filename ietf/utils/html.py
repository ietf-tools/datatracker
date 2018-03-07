# Taken from http://code.google.com/p/soclone/source/browse/trunk/soclone/utils/html.py

"""Utilities for working with HTML."""
import bleach

from html5lib.filters.base import Filter

import debug                            # pyflakes:ignore

from django.utils.functional import keep_lazy
from django.utils import six

acceptable_tags = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
    'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
    'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'ins', 'kbd',
    'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
    'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
    'tr', 'tt', 'u', 'ul', 'var')

strip_completely = ['style', 'script', ]

class StripFilter(Filter):
    def __iter__(self):
        open_tags = []
        for token in Filter.__iter__(self):
            if token["type"] in ["EmptyTag", "StartTag"]:
                open_tags.append(token["name"])
            if not (set(open_tags) & set(strip_completely)):
                yield token
            if token["type"] in ["EmptyTag", "EndTag"]:
                open_tags.pop()

# Leave the stripping of the strip_completely tags to StripFilter
bleach_tags = list(set(acceptable_tags) | set(strip_completely))
cleaner = bleach.sanitizer.Cleaner(tags=bleach_tags, filters=[StripFilter], strip=True)

def unescape(text):
    """
    Returns the given text with ampersands, quotes and angle brackets decoded
    for use in URLs.

    This function undoes what django.utils.html.escape() does
    """
    return text.replace('&#39;', "'").replace('&quot;', '"').replace('&gt;', '>').replace('&lt;', '<' ).replace('&amp;', '&')

def remove_tags(html, tags):
    """Returns the given HTML sanitized, and with the given tags removed."""
    allowed = set(acceptable_tags) - set([ t.lower() for t in tags ])
    return bleach.clean(html, tags=allowed)
remove_tags = keep_lazy(remove_tags, six.text_type)

def sanitize_html(html):
    return cleaner.clean(html)

