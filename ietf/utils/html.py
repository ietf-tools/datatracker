# Taken from http://code.google.com/p/soclone/source/browse/trunk/soclone/utils/html.py

"""Utilities for working with HTML."""
import bleach
import lxml.html.clean

import debug                            # pyflakes:ignore

from django.utils.functional import keep_lazy
from django.utils import six

acceptable_tags = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
    'blockquote', 'body', 'br', 'caption', 'center', 'cite', 'code', 'col',
    'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'head', 'hr', 'html', 'i', 'ins', 'kbd',
    'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
    'strong', 'sub', 'sup', 'table', 'title', 'tbody', 'td', 'tfoot', 'th', 'thead',
    'tr', 'tt', 'u', 'ul', 'var')

acceptable_protocols = ['http', 'https', 'mailto', 'xmpp', ]

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

# ----------------------------------------------------------------------
# Html fragment cleaning

bleach_cleaner = bleach.sanitizer.Cleaner(tags=acceptable_tags, protocols=acceptable_protocols, strip=True)

def sanitize_fragment(html):
    return bleach_cleaner.clean(html)

# ----------------------------------------------------------------------
# Page cleaning

lxml_cleaner = lxml.html.clean.Cleaner(allow_tags=acceptable_tags, 
                                        remove_unknown_tags=None, style=False, page_structure=False)

def sanitize_document(html):
    return lxml_cleaner.clean_html(html)
