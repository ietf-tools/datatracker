# Copyright The IETF Trust 2010-2020, All Rights Reserved
# -*- coding: utf-8 -*-
# Taken from http://code.google.com/p/soclone/source/browse/trunk/soclone/utils/html.py
"""Utilities for working with HTML."""


import nh3
import html2text
import debug                            # pyflakes:ignore

from django import forms
from django.utils.functional import keep_lazy

from ietf.utils.mime import get_mime_type


# Allow the protocols/tags/attributes we specifically want, plus anything that nh3 declares
# to be safe.

acceptable_protocols = {"http", "https", "mailto", "tel", "xmpp"}
acceptable_tags = nh3.ALLOWED_TAGS.union(
    {
        # fmt: off
        "a", "abbr", "acronym", "address", "b", "big",
        "blockquote", "body", "br", "caption", "center", "cite", "code", "col",
        "colgroup", "dd", "del", "dfn", "dir", "div", "dl", "dt", "em", "font",
        "h1", "h2", "h3", "h4", "h5", "h6", "head", "hr", "html", "i", "ins", "kbd",
        "li", "ol", "p", "pre", "q", "s", "samp", "small", "span", "strike",
        "strong", "sub", "sup", "table", "title", "tbody", "td", "tfoot", "th", "thead",
        "tr", "tt", "u", "ul", "var", "xmp"
        # fmt: on
    }
)
acceptable_attributes = nh3.ALLOWED_ATTRIBUTES | {
    "*": {"id"},
    "ol": {"start"},
}


# Instantiate sanitizer classes
_nh3_cleaner = nh3.Cleaner(
    tags=acceptable_tags,
    attributes=acceptable_attributes,
    url_schemes=acceptable_protocols,
)


_liberal_nh3_cleaner = nh3.Cleaner(
    tags=acceptable_tags.union({"img", "figure", "figcaption"}),
    attributes=acceptable_attributes | {"img": {"src", "alt"}},
    url_schemes=acceptable_protocols,
)


def clean_html(text: str):
    return _nh3_cleaner.clean(text)


def liberal_clean_html(text: str):
    return _liberal_nh3_cleaner.clean(text)


@keep_lazy(str)
def remove_tags(html, tags):
    """Returns the given HTML sanitized, and with the given tags removed."""
    allowed = acceptable_tags - set(t.lower() for t in tags)
    return nh3.clean(html, tags=allowed)


# ----------------------------------------------------------------------
# Text field cleaning

def clean_text_field(text):
    mime_type, encoding = get_mime_type(text.encode('utf8'))
    if   mime_type == 'text/html': #  or re.search(r'<\w+>', text):
        text = html2text.html2text(text)
    elif mime_type in ['text/plain', 'application/x-empty', ]:
        pass
    else:
        raise forms.ValidationError("Unexpected text field mime type: %s" % mime_type)
    return text


def unescape(text):
    """
    Returns the given text with ampersands, quotes and angle brackets decoded
    for use in URLs.

    This function undoes what django.utils.html.escape() does
    """
    return text.replace('&amp;', '&').replace('&#39;', "'").replace('&quot;', '"').replace('&gt;', '>').replace('&lt;', '<' )
