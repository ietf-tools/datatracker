from __future__ import unicode_literals

import re
import unicodedata
import textwrap
import types

from django.utils.functional import allow_lazy
from django.utils import six
from django.utils.safestring import mark_safe

import debug                            # pyflakes:ignore

def xslugify(value):
    """
    Converts to ASCII. Converts spaces to hyphens. Removes characters that
    aren't alphanumerics, underscores, slash, or hyphens. Converts to
    lowercase.  Also strips leading and trailing whitespace.
    (I.e., does the same as slugify, but also converts slashes to dashes.)
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s/-]', '', value).strip().lower()
    return mark_safe(re.sub('[-\s/]+', '-', value))
xslugify = allow_lazy(xslugify, six.text_type)

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
    if not isinstance(text, (types.StringType,types.UnicodeType)):
        return text
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
        if wrapped and line.strip() != "" and indent == prev_indent:
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


def alternative_wrap(text, width=80):
    # From http://blog.belgoat.com/python-textwrap-wrap-your-text-to-terminal-size/
    textLines = text.split('\n')
    wrapped_lines = []
    # Preserve any indent (after the general indent)
    for line in textLines:
        preservedIndent = ''
        existIndent = re.search(r'^(\W+)', line)
        # Change the existing wrap indent to the original one
        if (existIndent):
            preservedIndent = existIndent.groups()[0]
        wrapped_lines.append(textwrap.fill(line, width=width, subsequent_indent=preservedIndent))
    text = '\n'.join(wrapped_lines)
    return text

def wrap_text_if_unwrapped(text, width=80, max_tolerated_line_length=100):
    text = re.sub(" *\r\n", "\n", text) # get rid of DOS line endings 
    text = re.sub(" *\r", "\n", text)   # get rid of MAC line endings 

    contains_long_lines = any(" " in l and len(l) > max_tolerated_line_length 
                              for l in text.split("\n")) 

    if contains_long_lines: 
        text = wordwrap(text, width)
    return text 

def isascii(text):
    try:
        text.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False
        
