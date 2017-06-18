# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2017, All Rights Reserved

from __future__ import print_function, unicode_literals, division

import re
import textwrap
from pyterminalsize import get_terminal_size
from collections import namedtuple

try:
    import debug
    debug.debug = True
except ImportError:
    pass

Line = namedtuple('Line', ['num', 'txt'])

class Options(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            if not k.startswith('__'):
                setattr(self, k, v)
    pass


def wrap(s):
    cols = min(120, get_terminal_size()[0])

    lines = s.split('\n')
    wrapped = []
    # Preserve any indentation (after the general indentation)
    for line in lines:
        prev_indent = '   '
        indent_match = re.search('^(\W+)', line)
        # Change the existing wrap indentation to the original one
        if (indent_match):
            prev_indent = indent_match.group(0)
        wrapped.append(textwrap.fill(line, width=cols, subsequent_indent=prev_indent))
    return '\n'.join(wrapped)


def strip_pagebreaks(text):
    "Strip ID/RFC-style headers and footers from the given text"
    short_title = None
    stripped = []
    page = []
    line = ""
    newpage = False
    sentence = False
    blankcount = 0
    # We need to get rid of the \f, otherwise those will result in extra lines during line
    # splitting, and the line numbers reported in error messages will be off
    text = text.replace('\f','') 
    lines = text.splitlines()
    # two functions with side effects
    def endpage(page, newpage, line):
        if line:
            page += [ line ]
        return begpage(page, newpage)
    def begpage(page, newpage, line=None):
        if page and len(page) > 5:
            page = []
            newpage = True
        if line:
            page += [ line ]
        return page, newpage
    for lineno, line in enumerate(lines):
        line = line.rstrip()
        match = re.search("(  *)(\S.*\S)(  +)\[?[Pp]age [0-9ivx]+\]?[ \t\f]*$", line, re.I)
        if match:
            mid = match.group(2)
            if not short_title and not mid.startswith('Expires'):
                short_title = mid
            page, newpage = endpage(page, newpage, line)
            continue
        if re.search("\f", line, re.I):
            page, newpage = begpage(page, newpage)
            continue
        if lineno > 25:
            regex = "^(INTERNET.DRAFT|Internet.Draft|RFC \d+)(  +)(\S.*\S)(  +)(Jan|Feb|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|Sep|Oct|Nov|Dec)[a-z]+ (19[89][0-9]|20[0-9][0-9]) *$"
            match = re.search(regex, line, re.I)
            if match:
                short_title = match.group(3)
                page, newpage = begpage(page, newpage, line)
                continue
        if lineno > 25 and re.search(".{58,}(Jan|Feb|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|Sep|Oct|Nov|Dec)[a-z]+ (19[89][0-9]|20[0-9][0-9]) *$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
        if lineno > 25 and re.search("^ *Internet.Draft.+[12][0-9][0-9][0-9] *$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
        if lineno > 25 and re.search("^ *(Internet.Draft|INTERNET.DRAFT)( {16,}).*$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
#        if re.search("^ *Internet.Draft  +", line, re.I):
#            newpage = True
#            continue
        if re.search("^ *Draft.+[12][0-9][0-9][0-9] *$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
        if re.search("^RFC[ -]?[0-9]+.*( +)[12][0-9][0-9][0-9]$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
        if re.search("^RFC[ -]?[0-9]+.*(  +)[12][0-9][0-9][0-9]$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
        if re.search("^draft-[-a-z0-9_.]+.*[0-9][0-9][0-9][0-9]$", line, re.I):
            page, newpage = endpage(page, newpage, line)
            continue
        if newpage and re.search("^ *draft-[-a-z0-9_.]+ *$", line, re.I):
            page, newpage = begpage(page, newpage, line)
            continue
        if re.search("^[^ \t]+", line):
            sentence = True
        if re.search("[^ \t]", line):
            if newpage:
                if sentence:
                    stripped += [ Line(lineno-1, "") ]
            else:
                if blankcount:
                    stripped += [ Line(lineno-1, "") ]
            blankcount = 0
            sentence = False
            newpage = False
        if re.search("[.:+]\)?$", line):    # line ends with a period; don't join with next page para
            sentence = True
        if re.search("^[A-Z0-9][0-9]*\.", line): # line starts with a section number; don't join with next page para
            sentence = True
        if re.search("^ +[o*+-]  ", line): # line starts with a list bullet; don't join with next page para
            sentence = True
        if re.search("^ +(E[Mm]ail): ", line): # line starts with an address component; don't join with next page para
            sentence = True
        if re.search("^ +(Table|Figure)( +\d+)?: ", line): # line starts with Table or Figure label; don't join with next page para
            sentence = True
        if line.strip() and len(line) < 50:              # line is too short; don't join with next page para
            sentence = True
        if line.rstrip() and line.rstrip()[-1] == ',':
            sentence = False
        if re.search("^[ \t]*$", line):
            blankcount += 1
            if blankcount > 7:
                sentence = True
            page += [ line ]
            continue
        page += [ line ]
        stripped += [ Line(lineno, line) ]
    page, newpage = begpage(page, newpage)
    return stripped, short_title
    