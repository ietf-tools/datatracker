# Taken from http://code.google.com/p/soclone/source/browse/trunk/soclone/utils/html.py

"""Utilities for working with HTML."""
import bleach

import debug                            # pyflakes:ignore

from django.utils.functional import keep_lazy
from django.utils import six

acceptable_elements = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
    'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
    'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
    'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
    'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
    'tr', 'tt', 'u', 'ul', 'var')

def unescape(text):
    """
    Returns the given text with ampersands, quotes and angle brackets decoded
    for use in URLs.

    This function undoes what django.utils.html.escape() does
    """
    return text.replace('&#39;', "'").replace('&quot;', '"').replace('&gt;', '>').replace('&lt;', '<' ).replace('&amp;', '&')

def remove_tags(html, tags):
    """Returns the given HTML sanitized, and with the given tags removed."""
    allowed = set(acceptable_elements) - set([ t.lower() for t in tags ])
    return bleach.clean(html, tags=allowed)
remove_tags = keep_lazy(remove_tags, six.text_type)

def sanitize_html(html, tags=acceptable_elements, extra=[], remove=[], strip=True):
    tags = list(set(tags) | set(t.lower() for t in extra) ^ set(t.lower for t in remove))
    return bleach.clean(html, tags=tags, strip=strip)

def clean_html(html):
    return bleach.clean(html)
