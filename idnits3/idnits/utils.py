# Copyright 2018-2019 IETF Trust, All Rights Reserved
# -*- coding: utf-8 indent-with-tabs: 0 -*-

from __future__ import unicode_literals, print_function, division

import re
import textwrap

from collections import namedtuple

try:
    from pyterminalsize import get_terminal_size    
except ImportError:
    get_terminal_size = None


Line = namedtuple('Line', ['num', 'txt'])
Para = namedtuple('Para', ['num', 'txt'])

def build_paragraphs(lines):
    "Build a list of Paras from a list of Lines"
    paras = []
    llist = []
    num = None
    for l in lines:
        if l.txt:
            if num is None:
                num = l.num
            llist.append(l.txt.lstrip()) # already did .rstrip() when collecting lines
        else:                           
            # blank line
            if llist:
                txt = normalize_paragraph(' '.join(llist))
                p = Para(num, txt) 
                paras.append(p)
                llist = []
                num = None
    return paras


def normalize_paragraph(text):
    # The normalizations here are based on experience with the kind of errors
    # people have put into boilerplate text over the years

    # normalize space
    text = re.sub(r'[\t\n\r ]+', ' ', text)
    text = text.strip()
    # normalize adjacent square bracke sets
    text = re.sub(r'\] +\[', '][', text)
    # normalize end-of-sentence
    text = re.sub(r'([^.])(["\'])\.$', r'\1.\2', text)
    text = re.sub(r'([^.])"$', r'\1."', text)
    text = re.sub(r'([^.])\'$', r'\1.\'', text)
    text = re.sub(r'([^\'".])$', r'\1.', text)
    text = text.strip()
    return text

def wrap(s, w=120, i=None):
    termsize = get_terminal_size() if get_terminal_size else (80, 24)
    cols = min(w, max(termsize[0], 60))

    lines = s.split('\n')
    wrapped = []
    # Preserve any indentation (after the general indentation)
    for line in lines:
        prev_indent = ' '*(i or 4)
        indent_match = re.search('^(\W+)', line)
        # Change the existing wrap indentation to the original one
        if (indent_match and not i):
            prev_indent = indent_match.group(0)
        wrapped.append(textwrap.fill(line, width=cols, subsequent_indent=prev_indent))
    return '\n'.join(wrapped)

