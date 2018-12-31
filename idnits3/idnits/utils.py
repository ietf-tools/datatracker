# Copyright 2018-2019 IETF Trust, All Rights Reserved
# -*- coding: utf-8 indent-with-tabs: 0 -*-

from __future__ import unicode_literals, print_function, division

import re

from collections import namedtuple

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
