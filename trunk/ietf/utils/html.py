# Taken from http://code.google.com/p/soclone/source/browse/trunk/soclone/utils/html.py

"""Utilities for working with HTML."""
import html5lib
import bleach
from html5lib import sanitizer, serializer, tokenizer, treebuilders, treewalkers

from django.utils.functional import allow_lazy
from django.utils import six

acceptable_elements = ('a', 'abbr', 'acronym', 'address', 'b', 'big',
    'blockquote', 'br', 'caption', 'center', 'cite', 'code', 'col',
    'colgroup', 'dd', 'del', 'dfn', 'dir', 'div', 'dl', 'dt', 'em', 'font',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'ins', 'kbd',
    'li', 'ol', 'p', 'pre', 'q', 's', 'samp', 'small', 'span', 'strike',
    'strong', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead',
    'tr', 'tt', 'u', 'ul', 'var')

acceptable_attributes = ('abbr', 'align', 'alt', 'axis', 'border',
    'cellpadding', 'cellspacing', 'char', 'charoff', 'charset', 'cite',
    'cols', 'colspan', 'datetime', 'dir', 'frame', 'headers', 'height',
    'href', 'hreflang', 'hspace', 'lang', 'longdesc', 'name', 'nohref',
    'noshade', 'nowrap', 'rel', 'rev', 'rows', 'rowspan', 'rules', 'scope',
    'span', 'src', 'start', 'summary', 'title', 'type', 'valign', 'vspace',
    'width')


class HTMLSanitizerMixin(sanitizer.HTMLSanitizerMixin):
    allowed_elements = acceptable_elements
    allowed_attributes = acceptable_attributes
    allowed_css_properties = ()
    allowed_css_keywords = ()
    allowed_svg_properties = ()

class HTMLSanitizer(tokenizer.HTMLTokenizer, HTMLSanitizerMixin):
    def __init__(self, *args, **kwargs):
        tokenizer.HTMLTokenizer.__init__(self, *args, **kwargs)

    def __iter__(self):
        for token in tokenizer.HTMLTokenizer.__iter__(self):
            token = self.sanitize_token(token)
            if token:
                yield token

def sanitize_html(html):
    """Sanitizes an HTML fragment."""
    p = html5lib.HTMLParser(tokenizer=HTMLSanitizer,
                            tree=treebuilders.getTreeBuilder("dom"))
    dom_tree = p.parseFragment(html)
    walker = treewalkers.getTreeWalker("dom")
    stream = walker(dom_tree)
    s = serializer.HTMLSerializer(omit_optional_tags=False,
                                  quote_attr_values=True)
    output_generator = s.serialize(stream)
    return u''.join(output_generator)

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
remove_tags = allow_lazy(remove_tags, six.text_type)

def clean_html(html):
    return bleach.clean(html)

