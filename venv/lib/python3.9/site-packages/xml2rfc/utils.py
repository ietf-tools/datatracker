# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

# Internal utility functions.  Not meant for public usage.

import base64
import re
import sys
import textwrap

from collections import OrderedDict
from lxml.etree import _Comment, _ProcessingInstruction

from urllib.request import quote

try:
    from xml2rfc import debug
    assert debug
except ImportError:
    pass

import xml2rfc.log


# ----------------------------------------------------------------------
# Text wrapping

class TextWrapper(textwrap.TextWrapper):
    """ Subclass that overrides a few things in the standard implementation """
    def __init__(self, **kwargs):
        textwrap.TextWrapper.__init__(self, **kwargs)

        # Override wrapping regex, preserve '/' before linebreak
        self.wordsep_re = re.compile(
            u'('
            u'[ \t\n\r\f\v]+|'                                  # any ASCII whitespace
            u'[^\\s-]*\\w+/(?=[A-Za-z]\\w*)|'                   # forward-slash separated words
            u'[^\\s-]*\\w+[^0-9\\s]-(?=\\w+[^0-9\\s])|'         # hyphenated words
            u'\u200b|'                                          # &zwsp; zero-width space is breakable space
            u'''(?<=[\\w\\!"'\\&\\.\\,\\?])-{2,}(?=\\w))'''     # em-dash
            u'(?![\u00A0|\u2060|\uE060])')                      # UNLESS &nbsp; or &wj; 

        self.wordsep_re_uni = re.compile(self.wordsep_re.pattern, re.U)

        # Override end of line regex, double space after '].'
        self.sentence_end_re = re.compile(r'[A-Za-z0-9\>\]\)\"\']'  # letter, end parentheses
                            r'[\.\!\?]'     # sentence-ending punct.
                            r'[\"\'\)\]]?'  # optional end-of-quote, end parentheses
                            r'\Z'           # end of chunk
                            )

        # Exceptions which should not be treated like end-of-sentence
        self.not_sentence_end_re = re.compile(
            # start of string or non-alpha character
            r'(^|\s)'
            r'('
            # Single uppercase letter, dot, enclosing parentheses or quotes
            r'\.[\]\)\'"]*'
            # Tla with leading uppercase, and special cases
            # (Note: v1 spelled out Fig, Tbl, Mrs, Drs, Rep, Sen, Gov, Rev, Gen, Col, Maj and Cap,
            #  but those are redundant with the Tla regex.)
            r'|([\(\[])?([A-Z][a-z][a-z]|Eq|[Cc]f|vs|resp|viz|ibid|[JS]r|M[rs]|Messrs|Mmes|Dr|Profs?|St|Lt|a\.k\.a|i\.e|e\.g)\.'
            r')\Z' # trailing dot, end of group and end of chunk
            )

        # Start of next sentence regex
        self.sentence_start_re = re.compile("^[\"'([]*[A-Z]")

    def _fix_sentence_endings(self, chunks):
        """_fix_sentence_endings(chunks : [string])

        Correct for sentence endings buried in 'chunks'.  Eg. when the
        original text contains "... foo.\nBar ...", munge_whitespace()
        and split() will convert that to [..., "foo.", " ", "Bar", ...]
        which has one too few spaces; this method simply changes the one
        space to two.
        """
        i = 0
        patsearch = self.sentence_end_re.search
        skipsearch = self.not_sentence_end_re.search
        startsearch = self.sentence_start_re.search
        while i < len(chunks)-2:
            if (chunks[i+1] == " " and patsearch(chunks[i])
                                  and skipsearch(chunks[i])==None
                                  and startsearch(chunks[i+2])):
                chunks[i+1] = "  "
                i += 2
            else:
                i += 1

    def wrap(self, text, initial='', subsequent_indent=None, width=None,
        fix_doublespace=True, fix_sentence_endings=True, drop_whitespace=True):
        """ Mirrored implementation of wrap which replaces characters properly
            and also lets you easily specify indentation on the fly
        """
        # Handle U+2028 LINE SEPARATOR by recursing
        if '\u2028' in text:
            parts = text.split('\u2028')
            wrapped = []
            for part in parts:
                part = part.lstrip()
                if part:
                    wrapped += self.wrap(part, initial=initial, subsequent_indent=subsequent_indent,
                                    width=width, fix_doublespace=fix_doublespace,
                                    fix_sentence_endings=fix_sentence_endings,
                                    drop_whitespace=drop_whitespace) 
                else:
                    wrapped.append(part)
                initial = ''
            return wrapped

        # Set indentation
        _width = self.width
        if width != None:
            self.width = width
        self.initial_indent = initial
        if subsequent_indent == None:
            self.subsequent_indent = initial
        else:
            self.subsequent_indent = subsequent_indent
        self.fix_sentence_endings = fix_sentence_endings
        self.drop_whitespace = drop_whitespace

        # --- Original implementation ----------------------------------
        text = self._munge_whitespace(text)
        # --- End original implementation ------------------------------

        # Maybe remove double (and more) spaces, except when they might be between sentences
        if fix_doublespace:
            text = re.sub("([^.!?])  +", r"\1 ", text)
            text = re.sub("([.!?])   +", r"\1  ", text)

        # prevent breaking "Section N.N" and "Appendix X.X"
        text = re.sub("(Section|Appendix|Figure|Table) ", u"\\1\u00A0", text)

        # Replace some characters after splitting has occurred
        # --- Original implementation ----------------------------------
        chunks = self._split(text)
        # --- End original implementation ------------------------------

        parts = chunks
        chunks = []
        max_word_len = self.width - len(self.subsequent_indent)
        for chunk in parts:
            # remove zero-width characters before looking at length
            chunk2 = re.sub('[\u200B\u200C\u2060\uE060]', '', chunk)
            if len(chunk2) > max_word_len:
                # No use trying not to break when we have a chunk longer
                # than available horizontal space.  Remove wj and nbsp and
                # try again.
                chunk2 = re.sub('[\u2060\uE060]', '', chunk).replace('\u00A0', ' ')
                bits = self._split(chunk2)
                for bit in bits:
                    chunk3 = re.sub('[\u2060\uE060]', '', bit).replace('\u00A0', ' ')
                    if len(chunk3) > max_word_len:
                        chunks += self._split(chunk3)
                    else:
                        chunks += [ chunk3 ]
            else:
                chunks += [ chunk2 ]
        
        # --- Original implementation ----------------------------------
        if self.fix_sentence_endings:
            self._fix_sentence_endings(chunks)
        wrapped = self._wrap_chunks(chunks)
        # --- End original implementation ------------------------------

        self.width = _width
        for i, chunk in enumerate(wrapped):
            wrapped[i] = chunk.replace(u'\uE060', '')
        return wrapped

    def fill(self, *args, **kwargs):
        kwargs.pop('fill', None)
        return "\u2028".join(self.wrap(*args, **kwargs))


class TextSplitter(textwrap.TextWrapper):
    """ Subclass that overrides a few things in the standard implementation """
    def __init__(self, **kwargs):
        hyphen_split = kwargs.pop('hyphen_split', False)
        textwrap.TextWrapper.__init__(self, **kwargs)

        # Override wrapping regex, preserve '/' before linebreak
        if hyphen_split:
            self.wordsep_re = re.compile(
                u'('
                u'[ \t\n\r\f\v]+|'                                  # any ASCII whitespace
                u'[^\\s-]*\\w+/(?=[A-Za-z]\\w*)|'                   # forward-slash separated words
                u'\u200b|'                                          # &zwsp; zero-width space is breakable space
                u'\u2028|'                                          # &br; unicode 'line separator'
                u'[^\\s-]*\\w+[^0-9\\s]-(?=\\w+)|'                  # hyphenated words
                u'''(?<=[\\w\\!"'\\&\\.\\,\\?])-{2,}(?=\\w))'''     # em-dash
                u'(?![\u00A0|\u2060|\uE060])')                      # UNLESS &nbsp; or &wj; 
        else:
            self.wordsep_re = re.compile(
                u'('
                u'[ \t\n\r\f\v]+|'                                  # any ASCII whitespace
                u'[^\\s-]*\\w+/(?=[A-Za-z]\\w*)|'                   # forward-slash separated words
                u'\u200b|'                                          # &zwsp; zero-width space is breakable space
                u'\u2028|'                                          # &br; unicode 'line separator'
                u'''(?<=[\\w\\!"'\\&\\.\\,\\?])-{2,}(?=\\w))'''     # em-dash
                u'(?![\u00A0|\u2060|\uE060])')                      # UNLESS &nbsp; or &wj; 

        self.wordsep_re_uni = re.compile(self.wordsep_re.pattern, re.U)


def justify_inline(left_str, center_str, right_str, width=72):
    """ Takes three string arguments and outputs a single string with the
        arguments left-justified, centered, and right-justified respectively.

        Raises a warning if the combined length of the three strings is
        greater than the width, and trims the longest string
    """
    strings = [left_str.rstrip(), center_str.strip(), right_str.strip()]
    sumwidth = sum( [len(s) for s in strings] )
    if sumwidth > width:
        # Trim longest string
        longest_index = strings.index(max(strings, key=len))
        xml2rfc.log.warn('The inline string was truncated because it was ' \
                         'too long:\n  ' + strings[longest_index])
        strings[longest_index] = strings[longest_index][:-(sumwidth - width)]

    if len(strings[1]) % 2 == 0:
        center = strings[1].center(width)
    else:
        center = strings[1].center(width+1)        
    right = strings[2].rjust(width)
    output = list(strings[0].ljust(width))
    for i, char in enumerate(output):
        if center[i] != ' ':
            output[i] = center[i]
        elif right[i] != ' ':
            output[i] = right[i]
    return ''.join(output)

# ----------------------------------------------------------------------
# Other text operations


def ascii_split(text):
    """ We have unicode strings, but we want to split only on the ASCII
        whitespace characters so that nbsp does not get split.
    """

    if isinstance(text, type('')):
        return text.split()
    return re.split("[ \t\n\r\f\v]+", text)


def urlkeep(text, max=72):
    """ Insert word join XML entities on forward slashes and hyphens
        in a URL so that it stays on one line
    """
    wj_char = u'\uE060'
    def replacer(match):
        url = match.group(0)
        if len(url) > max:
            return url
        else:
            return ( url.replace('/', '/' + wj_char) 
                        .replace('-', '-' + wj_char) 
                        .replace(':', ':' + wj_char)
                    )
    if 'http://' in text:
        text = re.sub(r'http:\S*', replacer, text)
    if 'https://' in text:
        text = re.sub(r'https:\S*', replacer, text)
    return text

# ----------------------------------------------------------------------
# Tree operations

def formatXmlWhitespace(tree):
    """ Traverses an lxml.etree ElementTree and properly formats whitespace
    
        We replace newlines with single spaces, unless it ends with a
        period then we replace the newline with two spaces.
    """
    for element in tree.iter():
        # Preserve formatting on artwork
        if element.tag != 'artwork':
            if element.text is not None:
                element.text = re.sub(r'\s*\n\s*', ' ', \
                               re.sub(r'\.\s*\n\s*', '.  ', \
                               element.text.lstrip()))

            if element.tail is not None:
                element.tail = re.sub(r'\s*\n\s*', ' ', \
                               re.sub(r'\.\s*\n\s*', '.  ', \
                               element.tail))


def safeReplaceUnicode(tree):
    """ Traverses an lxml.etree ElementTree and replaces unicode characters 
        with the proper equivalents specified in rfc2629-xhtml.ent.

        Writers should call this method if the entire RFC document needs to
        be ascii formatted
    """
    for element in tree.iter():
        if element.text:
            try:
                element.text = element.text.encode('ascii')
            except UnicodeEncodeError:
                element.text = _replace_unicode_characters(element.text)
        if element.tail:
            try:
                element.tail = element.tail.encode('ascii')
            except UnicodeEncodeError:
                element.tail = _replace_unicode_characters(element.tail)
        for key in element.attrib.keys():
            try:
                element.attrib[key] = element.attrib[key].encode('ascii')
            except UnicodeEncodeError:
                element.attrib[key] = \
                _replace_unicode_characters(element.attrib[key])


def safeTagSlashedWords(tree):
    """ Traverses an lxml.etree ElementTree and replace words separated
        by slashes if they are on the list
    """
    slashList = {}
    for element in _slash_replacements:
        slashList[element] = re.sub(u'/', u'\uE060/\uE060', element)
        
    for element in tree.iter():
        if element.tag == 'artwork':
            continue
        if element.text:
            element.text = _replace_slashed_words(element.text, slashList)
        if element.tail:
            element.tail = _replace_slashed_words(element.tail, slashList)
        # I do not know that this makes any sense
        # for key in element.attrib.keys():
        #    element.attrib[key] = \
        #        _replace_slashed_words(element.attrib[key], slashList)


def find_duplicate_ids(schema, tree):
    # get attributes specified with data type "ID"
    id_data = schema.xpath("/x:grammar/x:define/x:element//x:attribute/x:data[@type='ID']", namespaces=namespaces)
    attr = set([ i.getparent().get('name') for i in id_data ])
    # Check them one by one
    return find_duplicate_attr_values(attr, tree)

def find_duplicate_html_ids(tree):
    return find_duplicate_attr_values(['id',], tree)

def find_duplicate_attr_values(attr, tree):
    dups = []
    # Check them one by one
    for a in attr:
        seen = set()
        for e in tree.xpath('.//*[@%s]' % a):
            id = e.get(a)
            if id != None and id in seen:
                dups.append((a, id, e))
            else:
                seen.add(id)
    return dups

# ----------------------------------------------------------------------
# Unicode operations


def _replace_unicode_characters(str):
    """ replace those Unicode characters that we do not use internally
        &wj; &zwsp; &nbsp; &nbhy;
    """
    str = str.replace('\uE060', '\u2060')
    while True:
        match = re.search(u'([^ -\x7e\u2060\u200B\u00A0\u2011\r\n])', str)
        if not match:
            return str
        if match.group(1) in _unicode_replacements:
            str = re.sub(match.group(1), _unicode_replacements[match.group(1)], str)
        else:
            entity = match.group(1).encode('ascii', 'xmlcharrefreplace').decode('ascii')
            str = re.sub(match.group(1), entity, str)
            xml2rfc.log.warn('Illegal character replaced in string: ' + entity)


# Ascii representations of unicode chars from rfc2629-xhtml.ent
# Auto-generated from comments in rfc2629-xhtml.ent
_unicode_replacements = {
    u'\x09': ' ',
    u'\xa0': ' ',
    u'\xa1': '!',
    u'\xa2': '[cents]',
    u'\xa3': 'GBP',
    u'\xa4': '[currency units]',
    u'\xa5': 'JPY',
    u'\xa6': '|',
    u'\xa7': 'S.',
    u'\xa9': '(C)',
    u'\xaa': 'a',
    u'\xab': '<<',
    u'\xac': '[not]',
    u'\xae': '(R)',
    u'\xaf': '_',
    u'\xb0': 'o',
    u'\xb1': '+/-',
    u'\xb2': '^2',
    u'\xb3': '^3',
    u'\xb4': "'",
    u'\xb5': '[micro]',
    u'\xb6': 'P.',
    u'\xb7': '.',
    u'\xb8': ',',
    u'\xb9': '^1',
    u'\xba': 'o',
    u'\xbb': '>>',
    u'\xbc': '1/4',
    u'\xbd': '1/2',
    u'\xbe': '3/4',
    u'\xbf': '?',
    u'\xc0': 'A',
    u'\xc1': 'A',
    u'\xc2': 'A',
    u'\xc3': 'A',
    u'\xc4': 'Ae',
    u'\xc5': 'Ae',
    u'\xc6': 'AE',
    u'\xc7': 'C',
    u'\xc8': 'E',
    u'\xc9': 'E',
    u'\xca': 'E',
    u'\xcb': 'E',
    u'\xcc': 'I',
    u'\xcd': 'I',
    u'\xce': 'I',
    u'\xcf': 'I',
    u'\xd0': '[ETH]',
    u'\xd1': 'N',
    u'\xd2': 'O',
    u'\xd3': 'O',
    u'\xd4': 'O',
    u'\xd5': 'O',
    u'\xd6': 'Oe',
    u'\xd7': 'x',
    u'\xd8': 'Oe',
    u'\xd9': 'U',
    u'\xda': 'U',
    u'\xdb': 'U',
    u'\xdc': 'Ue',
    u'\xdd': 'Y',
    u'\xde': '[THORN]',
    u'\xdf': 'ss',
    u'\xe0': 'a',
    u'\xe1': 'a',
    u'\xe2': 'a',
    u'\xe3': 'a',
    u'\xe4': 'ae',
    u'\xe5': 'ae',
    u'\xe6': 'ae',
    u'\xe7': 'c',
    u'\xe8': 'e',
    u'\xe9': 'e',
    u'\xea': 'e',
    u'\xeb': 'e',
    u'\xec': 'i',
    u'\xed': 'i',
    u'\xee': 'i',
    u'\xef': 'i',
    u'\xf0': '[eth]',
    u'\xf1': 'n',
    u'\xf2': 'o',
    u'\xf3': 'o',
    u'\xf4': 'o',
    u'\xf5': 'o',
    u'\xf6': 'oe',
    u'\xf7': '/',
    u'\xf8': 'oe',
    u'\xf9': 'u',
    u'\xfa': 'u',
    u'\xfb': 'u',
    u'\xfc': 'ue',
    u'\xfd': 'y',
    u'\xfe': '[thorn]',
    u'\xff': 'y',
    u'\u0152': 'OE',
    u'\u0153': 'oe',
    u'\u0161': 's',
    u'\u0178': 'Y',
    u'\u0192': 'f',
    u'\u02dc': '~',
    u'\u2002': ' ',
    u'\u2003': ' ',
    u'\u2009': ' ',
    u'\u2013': '-',
    u'\u2014': u'-\u002D',
    u'\u2018': "'",
    u'\u2019': "'",
    u'\u201a': "'",
    u'\u201c': '"',
    u'\u201d': '"',
    u'\u201e': '"',
    u'\u2020': '*!*',
    u'\u2021': '*!!*',
    u'\u2022': 'o',
    u'\u2026': '...',
    u'\u2030': '[/1000]',
    u'\u2032': "'",
    u'\u2039': '<',
    u'\u203a': '>',
    u'\u2044': '/',
    u'\u20ac': 'EUR',
    u'\u2122': '[TM]',
    u'\u2190': '<-\u002D',
    u'\u2192': '\u002D->',
    u'\u2194': '<->',
    u'\u21d0': '<==',
    u'\u21d2': '==>',
    u'\u21d4': '<=>',
    u'\u2212': '-',
    u'\u2217': '*',
    u'\u2264': '<=',
    u'\u2265': '>=',
    u'\u2329': '<',
    u'\u232a': '>',

    # rfc2629-other.ent
    u'\u0021': '!',
    u'\u0023': '#',
    u'\u0024': '$',
    u'\u0025': '%',
    u'\u0028': '(',
    u'\u0029': ')',
    u'\u002a': '*',
    u'\u002b': '+',
    u'\u002c': ',',
    u'\u002d': '-',
    u'\u002e': '.',
    u'\u002f': '/',
    u'\u003a': ':',
    u'\u003b': ';',
    u'\u003d': '=',
    u'\u003f': '?',
    u'\u0040': '@',
    u'\u005b': '[',
    u'\u005d': ']',
    u'\u005e': '^',
    u'\u005f': '_',
    u'\u0060': '`',
    u'\u007b': '{',
    u'\u007c': '|',
    u'\u007d': '}',
    u'\u017d': 'Z',
    u'\u017e': 'z',
    u'\u2010': '-',
}

def parse_pi(pi, pis):
    """ Add a processing instruction to the current state 

        Will also return the dictionary containing the added instructions
        for use in things like ?include instructions
    """
    if pi.text:
        # Split text in the format 'key="val"'
        chunks = re.split(r'=[\'"]([^\'"]*)[\'"]', pi.text)
        # Create pairs from this flat list, discard last element if odd
        tmp_dict = dict(zip(chunks[::2], chunks[1::2]))
        for key, val in tmp_dict.items():
            # Update main PI state
            pis[key] = val
        # Return the new values added
        return tmp_dict
    return {}


def _replace_slashed_words(str, slashList):
    """ replace slashed separated words the list with
        <word1> &nbsp; / &nbsp; <word 2>
    """
    match = re.findall(r'(\w+(/\w+)+)', str)
    for item in match:
        if item[0] in slashList:
            str = re.sub(item[0], slashList[item[0]], str)
    return str


_slash_replacements = [
    u'PDF/A',
    u'PDF/UA',
    u'PDF/VT',
    u'S/MIME',
    # If you remove me the regression test fails
    u'this/is/a/long/test',
];

            
def build_dataurl(mime, data, base64enc=False):
    if base64enc:
        data = quote(base64.b64encode(data), safe='/~')
        url = "data:%s;base64,%s" % (mime, data)
    else:
        data = quote(data, safe='/~')
        url = "data:%s,%s" % (mime, data)
    return url

namespaces={
    'x':    'http://relaxng.org/ns/structure/1.0',
    'a':    'http://relaxng.org/ns/compatibility/annotations/1.0',
    'xi':   'http://www.w3.org/2001/XInclude',
    'svg':  'http://www.w3.org/2000/svg',
    'xml':  'http://www.w3.org/XML/1998/namespace',
    'xlink':'http://www.w3.org/1999/xlink',
}


def sdict(d):
    "Create an ordered dict from the given dict, with sorted initial insertion"
    # For python 3.6 and later, lxml obeys dictionary insertion order for
    # attributes, for earlier it sorts initial attributes, so we need to
    # use a regular dict for 3.6 and later
    if sys.version_info.major == 3 and sys.version_info.minor >= 6:
        return dict( (k, d[k]) for k in sorted(list(d.keys())) )
    else:
        if isinstance(d, OrderedDict):
            return d
        return OrderedDict( (k, d[k]) for k in sorted(list(d.keys())) )

# ----------------------------------------------------------------------
# Element operations


def isempty(e):
    "Return True if e has no children and no text content"
    return not (len(e) or (e.text and e.text.strip()) or (e.tail and e.tail.strip()))

def isblock(e):
    "Return True if e is a block level element"
    from xml2rfc.writers.base import block_tags
    return e.tag in block_tags

def iscomment(e):
    "Return True if e is a comment or PI"
    return isinstance(e, (_Comment, _ProcessingInstruction))

def hastext(e, ignore=[]):
    "Return a list of text-level immediate children"
    head = [ e.text ] if e.text and e.text.strip() else []
    ignore = set(ignore + ['t'])
    items = ( head + [ c for c in e.iterchildren() if not (isblock(c) or iscomment(c) or (c.tag in ignore))]
                   + [ c.tail for c in e.iterchildren() if c.tail and c.tail.strip() ] )
    return items

def clean_text(s):
    """Replace internal use code points and various other special code points with plain equivalents"""
    # spaces
    s = re.sub(r'[\u00a0\u2028]', ' ', s)
    # hyphens
    s = s.replace(r'\u2011', '-')
    # zero-width
    s = re.sub(r'[\u200B\u2060\ue060]', '', s)
    return s.strip()

def is_htmlblock(h):
    return h.tag in set([ 'address', 'article', 'aside', 'blockquote', 'div', 'dl', 'figure',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'nav', 'ol', 'p', 'pre', 'script', 'section',
        'table', 'ul', ])

def slugify(s):
    s = s.strip().lower()
    s = re.sub(r'[^\w\s/|@=-]', '', s)
    s = re.sub(r'[-_\s/|@=]+', '_', s)
    s = s.strip('_')
    return s
