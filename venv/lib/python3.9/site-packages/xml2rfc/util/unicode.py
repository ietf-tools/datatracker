# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

# ----------------------------------------------------------------------
# Unicode operations

import re
import unicodedata

try:
    from xml2rfc import debug
    assert debug
except ImportError:
    pass

from wcwidth import wcswidth

unicode_content_tags = set([
    'artwork',
    'city',
    'cityarea',
    'code',
    'country',
    'email',
    'extaddr',
    'organization',
    'pobox',
    'postalLine',
    'refcontent',
    'region',
    'sortingcode',
    'sourcecode',
    'street',
    'title',
    'u',
])

# Attribute values should not contain unicode, with some exceptions
unicode_attributes = {
    ('author', 'fullname'),
    ('author', 'surname'),
    ('author', 'initials'),
    ('contact', 'fullname'),
    ('contact', 'surname'),
    ('contact', 'initials'),
    ('organization', 'abbrev'),
    ('seriesInfo', 'name'),
    ('seriesInfo', 'value'),
    ('xref', 'derivedContent'),
}

latinscript_attributes = {
    ('author', 'asciiFullname'),
    ('author', 'asciiSurname'),
    ('author', 'asciiInitials'),
    ('contact', 'asciiFullname'),
    ('contact', 'asciiSurname'),
    ('contact', 'asciiInitials'),
}

# These unicode tags don't require an ascii attribute
bare_unicode_tags = set([
    'artwork',
    'refcontent',
    'sourcecode',
    'u',
    ])

bare_latin_tags = set([
    'city',
    'cityarea',
    'code',
    'country',
    'email',
    'extaddr',
    'organization',
    'pobox',
    'postalLine',
    'region',
    'sortingcode',
    'street',
    'title',
    ])

def is_svg(e):
    '''
    Returns true if an element is a SVG element
    '''

    if str(e.tag).startswith('{http://www.w3.org/2000/svg}'):
        return True
    else:
        return False

for t in bare_unicode_tags:
    assert t in unicode_content_tags

def expand_unicode_element(e, bare=False):
    if not e.text:
        return ''
    format = e.get('format', 'lit-name-num')
    size = len(e.text)
    permitted = ('name', 'num', 'char', 'lit', 'ascii')
    required  = ('num', )
    #
    if not format:
        raise ValueError('Expected <unicode> to have a format attribute, but found none')
    def num(e):
        return ' '.join('U+%04X'%ord(c) for c in e.text)
    def lit(e):
        return '"%s"' % e.text
    def char(e):
        return '%s' % e.text
    def name(e):
        try:
            names = []
            for c in e.text:
                if isinstance(c, bytes):
                    c = c.decode('latin1')
                names.append(unicodedata.name(c, 'U+%04x'%ord(c)))
            return ', '.join(names)
        except ValueError as exc:
            raise ValueError('When looking for the name of "%s", got: %s' % (c, exc))
    def ascii(e):
        ascii = e.get('ascii')
        if not ascii:
            raise ValueError('Expected an ascii value when using "ascii" in the <unicode> expansion, but found none')
        return '"%s"' % ascii
    #
    if size == 0:
        return ''
    #
    simple_regex = '^{part}(-{part})*$'.format(part='(%s)' % '|'.join(permitted))
    full = None
    if re.match(simple_regex, format):
        full = False
        val = format
        parts = format.split('-')
    else:
        full = True
        val = format
        parts = re.findall('{([a-z]+)}', format)
    if len(parts) == 0 or not all(p for p in permitted):
        raise ValueError('Expected <unicode> expansion parts to be one or more of %s, but found format="%s"' % (', '.join(permitted), val))
    if not any(p in parts for p in required):
        if len(required) > 1:
            raise ValueError('Expected <unicode> expansion parts to include at least one of %s, but found format="%s"' % (', '.join(['"%s"'%r for r in required]), val))
        else:
            raise ValueError('Expected <unicode> expansion parts to include at least "%s", but found format="%s"' % (required[0], val))            
    if len(parts) > 3:
        raise ValueError('Expected up to 3 dash-separated <unicode> expansion parts, but found %d: format="%s"' % (len(parts), format))
    #
    values_list = []
    values_dict = {}
    for p in parts:
        if p in locals():
            func = locals()[p]
        else:
            raise RuntimeError('Internal Error: looked for a <unicode> expansion rendering function %s(), but didn\'t find it' % p)
        value = func(e)
        values_list.append(value)
        values_dict[p] = value
    #
    if full:
        text = format.format(**values_dict)
    else:
        if   len(parts) == 1:
            template = '%s'
        elif len(parts) == 2:
            template = '%s (%s)'
        elif len(parts) == 3:
            template = '%s (%s, %s)'
        else:
            raise ValueError('Did not expect to be asked to render <%s> with format="%s"' % (e.tag, format))
        text = template % tuple(values_list)
    return text

def isascii(u):
    if u is None:
        return True
    if isinstance(u, str):
        t = u+''
        for ch in [ '\u00a0', '\u200B', '\u2011', '\u2028', '\u2060', ]:
            if ch in t:
                t = t.replace(ch, ' ')
        try:
            t.encode('ascii')
            return True
        except UnicodeEncodeError:
            return False
    else:
        return True

def textwidth(u):
    "Length of string, disregarding zero-width code points"
    return wcswidth(u)

def downcode_punctuation(str):
    while True:
        match = re.search(punctuation_re, str)
        if not match:
            return str
        str = re.sub(match.group(0), punctuation[match.group(0)], str)

def downcode(str, replacements=None, use_charrefs=True):
    """

    Replaces Unicode characters that we do not use internally with selected
    replacement strings or with str.encode()'s xmlcharrefreplace string.

    Characters used internally, and stripped before emission:

        '\u00a0'                     # non-breaking whitespace
        '\u2060'                     # word joiner
        '\u200B'                     # zero-width space
        '\u2011'                     # non-breaking hyphen
        '\u2028'                     # line separator
        '\uE060'                     # word joiner

    """
    if not replacements:
        replacements = unicode_replacements

    while True:
        match = re.search(u'([^ -\x7e\u2060\u200B\u00A0\u2011\u2028\uE060\r\n\t])', str)
        if not match:
            return str
        if   match.group(1) in replacements:
            str = re.sub(match.group(1), replacements[match.group(1)], str)
        elif match.group(1) in controlchars:
            str = re.sub(match.group(1), controlchars[match.group(1)], str)
        else:
            entity = match.group(1).encode('ascii', 'xmlcharrefreplace').decode('ascii')
            str = re.sub(match.group(1), entity, str)

unicode_space_replacements = {
    u'\u2002': ' ',
    u'\u2003': ' ',
    u'\u2009': ' ',
}

unicode_dash_replacements = {
    u'\u002d': '-',
    u'\u2010': '-',
    u'\u2013': '-',
    u'\u2014': '-',
    u'\u2212': '-',
}

unicode_quote_replacements = {
    u'\u00b4': "'",
    u'\u2018': "'",
    u'\u2019': "'",
    u'\u201a': "'",
    u'\u201c': '"',
    u'\u201d': '"',
    u'\u201e': '"',
    u'\u2032': "'",
}

punctuation = {
    u'\u2026': '...',
}
punctuation.update(unicode_space_replacements)
punctuation.update(unicode_dash_replacements)
punctuation.update(unicode_quote_replacements)
punctuation_re = re.compile(r'[%s]'%''.join(list(punctuation.keys())))

unicode_replacements = {
    # Unicode code points corresponding to (x)html entities, also in
    # rfc2629-xhtml.ent
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

controlchars = dict( (str(chr(i)), ' ') for i in range(0, 32) if not i in [ 9, 10, 13 ] )
    
