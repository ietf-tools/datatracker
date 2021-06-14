# Copyright The IETF Trust 2016-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import email
import re
import textwrap
import unicodedata

from django.utils.functional import keep_lazy
from django.utils.safestring import mark_safe

import debug                            # pyflakes:ignore

from .texescape import init as texescape_init, tex_escape_map

@keep_lazy(str)
def xslugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, slash, or hyphens. Converts to
    lowercase.  Also strips leading and trailing whitespace.
    (I.e., does the same as slugify, but also converts slashes to dashes.)
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s/-]', '', value).strip().lower()
    return mark_safe(re.sub(r'[-\s/]+', '-', value))

def strip_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    else:
        return text

def strip_suffix(text, suffix):
    if text.endswith(suffix):
        return text[:-len(suffix)]
    else:
        return text    

def fill(text, width):
    """Wraps each paragraph in text (a string) so every line
    is at most width characters long, and returns a single string
    containing the wrapped paragraph.
    """
    width = int(width)
    paras = text.replace("\r\n","\n").replace("\r","\n").split("\n\n")
    wrapped = []
    for para in paras:
        if para:
            lines = para.split("\n")
            maxlen = max([len(line) for line in lines])
            if maxlen > width:
                para = textwrap.fill(para, width, replace_whitespace=False)
            wrapped.append(para)
    return "\n\n".join(wrapped)

def wordwrap(text, width=80):
    """Wraps long lines without loosing the formatting and indentation
       of short lines"""
    if not isinstance(text, str):
        return text
    def block_separator(s):
        "Look for lines of identical symbols, at least three long"
        ss = s.strip()
        chars = set(ss)
        return len(chars) == 1 and len(ss) >= 3 and ss[0] in set('#*+-.=_~')
    width = int(width)                  # ensure we have an int, if this is used as a template filter
    text = re.sub(" *\r\n", "\n", text) # get rid of DOS line endings
    text = re.sub(" *\r", "\n", text)   # get rid of MAC line endings
    text = re.sub("( *\n){3,}", "\n\n", text) # get rid of excessive vertical whitespace
    lines = text.split("\n")
    filled = []
    wrapped = False
    prev_indent = None
    for line in lines:
        line = line.expandtabs().rstrip()
        indent = " " * (len(line) - len(line.lstrip()))
        ind = len(indent)
        if wrapped and line.strip() != "" and indent == prev_indent and not block_separator(line):
            line = filled[-1] + " " + line.lstrip()
            filled = filled[:-1]
        else:
            wrapped = False
        while (len(line) > width) and (" " in line[ind:]):
            linelength = len(line)
            wrapped = True
            breakpoint = line.rfind(" ",ind,width)
            if breakpoint == -1:
                breakpoint = line.find(" ", ind)
            filled += [ line[:breakpoint] ]
            line = indent + line[breakpoint+1:]
            if len(line) >= linelength:
                break
        filled += [ line.rstrip() ]
        prev_indent = indent
    return "\n".join(filled)


# def alternative_wrap(text, width=80):
#     # From http://blog.belgoat.com/python-textwrap-wrap-your-text-to-terminal-size/
#     textLines = text.split('\n')
#     wrapped_lines = []
#     # Preserve any indent (after the general indent)
#     for line in textLines:
#         preservedIndent = ''
#         existIndent = re.search(r'^(\W+)', line)
#         # Change the existing wrap indent to the original one
#         if (existIndent):
#             preservedIndent = existIndent.groups()[0]
#         wrapped_lines.append(textwrap.fill(line, width=width, subsequent_indent=preservedIndent))
#     text = '\n'.join(wrapped_lines)
#     return text

def wrap_text_if_unwrapped(text, width=80, max_tolerated_line_length=100):
    text = re.sub(" *\r\n", "\n", text) # get rid of DOS line endings 
    text = re.sub(" *\r", "\n", text)   # get rid of MAC line endings 

    width = int(width)                  # ensure we have an int, if this is used as a template filter
    max_tolerated_line_length = int(max_tolerated_line_length)

    contains_long_lines = any(" " in l and len(l) > max_tolerated_line_length 
                              for l in text.split("\n")) 

    if contains_long_lines: 
        text = wordwrap(text, width)
    return text 

def isascii(text):
    try:
        text.encode('ascii')
        return True
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False

def maybe_split(text, split=True, pos=5000):
    if split:
        n = text.find("\n", pos)
        text = text[:n+1]
    return text

def decode(raw):
    assert isinstance(raw, bytes)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        # if this fails, don't catch the exception here; let it propagate
        text = raw.decode('latin-1')
    #
    return text

def text_to_dict(t):
    "Converts text with RFC2822-formatted header fields into a dictionary-like object."
    # ensure we're handed a unicode parameter
    assert isinstance(t, str)
    d = {}
    # Return {} for malformed input
    if not len(t.lstrip()) == len(t):
        return {}
    lines = t.splitlines()
    items = []
    # unfold folded lines
    for l in lines:
        if len(l) and l[0].isspace():
            if items:
                items[-1] += l
            else:
                return {}
        else:
            items.append(l)
    for i in items:
        if re.match('^[A-Za-z0-9-]+: ', i):
            k, v = i.split(': ', 1)
            d[k] = v
        else:
            return {}
    return d

def dict_to_text(d):
    "Convert a dictionary to RFC2822-formatted text"
    t = ""
    for k, v in d.items():
        t += "%s: %s\n" % (k, v)
    return t

def texescape(s):
    if not tex_escape_map:
        texescape_init()
    t = s.translate(tex_escape_map)
    return t

def unwrap(s):
    return s.replace('\n', ' ')
    
def normalize_text(s):
    return re.sub(r'[\s\n\r\u2028\u2029]+', ' ', s, flags=re.U).strip()

def parse_unicode(text):
    "Decodes unicode string from string encoded according to RFC2047"

    decoded_string, charset = email.header.decode_header(text)[0]
    if charset is not None:
        try:
            text = decoded_string.decode(charset)
        except UnicodeDecodeError:
            pass
    else:
        text = decoded_string
    return text
