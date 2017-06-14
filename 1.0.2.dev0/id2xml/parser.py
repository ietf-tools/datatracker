#!/bin/env python
# -*- coding: utf-8 -*-
# Copyright The IETF Trust 2017, All Rights Reserved

"""
Parse IETF-format drafts in text format, and generate XML output.
"""

from __future__ import print_function, unicode_literals, division

import os
import re
import six
import sys
import copy
import lxml
import inspect
import textwrap
from xml2rfc.writers.base import BaseRfcWriter
from collections import deque
from lxml.etree import Element, ElementTree, ProcessingInstruction, CDATA, Entity

from id2xml.utils import Options, Line, wrap, strip_pagebreaks

try:
    import debug
    debug.debug = True
except ImportError:
    pass

try:
    from pprint import pformat
except ImportError:
    pformat = lambda x: x

# ----------------------------------------------------------------------

ns={
    'x':'http://relaxng.org/ns/structure/1.0',
    'a':'http://relaxng.org/ns/compatibility/annotations/1.0',
}

boilerplate = BaseRfcWriter.boilerplate
approvers = BaseRfcWriter.approvers

#status_of_memo = "Status of This Memo"
appendix_prefix = "^Appendix:? "
#
code_re = (r'(?m)(^\s*[A-Za-z][A-Za-z0-9_-]*\s*=(\s*\S|\s*$)|[{}] *$|^ *[{}]|::=|'
            '//\s|\s//|\s/\*|/\*\s|</[a-z0-9:-]+>|\S+\s*=\s*\S+.*;$)')
#

section_names = {
    'front': [
        'abstract',
        'copyright notice',
        'status of this memo',
        'table of contents',
    ],
    'middle': [
        'acknowledegments',
        'acknowledgments',
        'contributors',
    ],
    'refs': [
        'references',
        'normative references',
        'normative',
        'informative references',
        'informative',
        'informational references',
        'uris',
    ],
    'back': [
        'acknowledgements',
        'acknowledgments',
        'annex',
        'appendix',
        "author's address",
        "authors' addresses",
        'contributors',
        'index',
    ],
}

section_names['all'] = [ n for p in section_names for n in section_names[p] ]

section_name_start = copy.deepcopy(section_names)
for part in section_name_start:
    for i in range(len(section_name_start[part])):
        section_name_start[part][i] = section_name_start[part][i].split()[0]

section_start_re = {
    'front':    r'^%s'%('|'.join(section_names['front'])),
    'middle':   r"^([0-9]+\.([0-9]+(\.[0-9]+)*\.?) |%s)" % ('|'.join(section_names['middle'])),
    'refs':     r"^(([0-9]+\.([0-9]+(\.[0-9]+)*\.?)? +)?(%s))" % ('|'.join(section_names['refs'])),
    'back':     r'^([A-Za-z](\.[0-9]+)*\.?|%s)' % ('|'.join(section_names['back'])),
}

# ----------------------------------------------------------------------
#
one_ref_re = r"(([0-9A-Z-]|I-?D.)[0-9A-Za-z-]*( [0-9A-Z-]+)?|(IEEE|ieee)[A-Za-z0-9.-]+|(ITU ?|ITU-T ?|G\\.)[A-Za-z0-9.-]+)";
ref_ref_re =  r"\[{ref}(, *{ref})*\]".format(ref=one_ref_re)
# 
day_re =        r'(?:[1-9]|0[1-9]|1[0-9]|2[0-9]|30|31)'
month_re =      r'(?:Jan(\.|uary)?|Feb(\.|ruary)?|March|April|May|June|July|Aug(\.|ust)?|Sep(\.|tember)?|Oct(\.|ober)?|Nov(\.|ember)?|Dec(\.|ember)?)'
uri_re =        r'^<?\s*(?P<target>(http|https|ftp)://[^>\s]+)\s*>?$'

# Elements of a reference item
ref_anchor_re = r'\[(?P<anchor>[^]]+)\]'
ref_name_re =   r'[-\' 0-9\w]+, (?:\w-?\w?\.)+(?:, Ed\.)?'
ref_last_re =   r'(?:\w-?\w?\.)+ [-\' 0-9\w]+(?:, Ed\.)?'
ref_org_re =   r'(?P<organization>[-/\w]+(?: [-/\w,.]+)*(, )?)'
ref_auth_re =   r'(?P<authors>({name})(, {name})*(,? and {last})?)'.format(name=ref_name_re, last=ref_last_re)
ref_title_re =  r'(?P<title>.+)'
ref_series_one =r'(?:(?:(?:RFC|STD|BCP|FYI|DOI|Internet-Draft) [^,]+|draft-[a-z0-9-]+)(?: \(work in progress\)|, work in progress)?)'
ref_series_re = r'(?P<series>{item}(?:, {item})*)'.format(item=ref_series_one)
ref_docname_re= r'(?P<docname>[^,]+(, [Vv ]ol\.? [^\s,]+)?(, pp\.? \d+(-\d+)?)?)'
ref_date_re =   r'(?P<date>({day} )?({month} )?[12]\d\d\d)'.format(day=day_re, month=month_re)
ref_url_re =    r'<? ?(?P<target>(http|https|ftp)://[^ >]+[^. >])>?'
#
chunks = dict(
    anchor  = ref_anchor_re,
    authors = ref_auth_re,
    organiz = ref_org_re,
    title   = ref_title_re,
    series  = ref_series_re,
    docname = ref_docname_re,
    date    = ref_date_re,
    url     = ref_url_re,
)

reference_patterns = [
    re.compile(r'{anchor}  *{authors}, "{title}", {series}, {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{authors}, "{title}", {series}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{authors}, "{title}", {series}, {date}, Work.in.progress(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{authors}, "{title}", {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{authors}, "{title}", {docname}, {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{organiz}, "{title}", {docname}, {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{authors}, "{title}", {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{organiz}, "{title}", {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{authors}, "{title}", {date}, Work.in.progress(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{organiz}, "{title}", {url}(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *"{title}", Work in Progress ?, {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *"{title}", Work in Progress ?, {url}(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *"{title}", {docname}, {date}(, {url})?(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *"{title}", {date}, {url}(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *"{title}", {url}(\.|$)'.format(**chunks)),
    re.compile(r'{anchor}  *{url}(\.|$)'.format(**chunks)),
## Lines commented out below are for debugging, when the full regex doesn't match (is buggy).
#    r'{anchor}  *{authors}, "{title}", {series}, {date}(, {url})?'.format(**chunks),
#    r'{anchor}  *{organiz}, "{title}", {docname}, {date}'.format(**chunks),
#    r'{anchor}  *{authors}, "{title}", {series}, {date}'.format(**chunks),
#    r'{anchor}  *{organiz}, "{title}", {docname}'.format(**chunks),
#    r'{anchor}  *{authors}, "{title}", {series}'.format(**chunks),
#    r'{anchor}  *{organiz}, "{title}"'.format(**chunks),
#    r'{anchor}  *{authors}, "{title}"'.format(**chunks),
#    r'{anchor}  *{organiz},'.format(**chunks),
#    r'{anchor}  *{authors}'.format(**chunks),
#    r'{anchor}  *'.format(**chunks),
#    r'{anchor}'.format(**chunks),
]

address_details = {
    'Phone:':   'phone',
    'Fax:':     'facsimile',
    'EMail:':   'email',
    'Email:':   'email',
    'URI:':     'uri',
}

# ----------------------------------------------------------------------


def space(s):
    if s is None or type(s) is lxml.etree.CDATA:
        return s
    nlt = '\n\t'
    if not s.startswith(nlt):
        s = nlt + s.lstrip()
    if not s.endswith(nlt):
        s = s.rstrip() + nlt
    return s


def split_on_large_whitespace(line):
    """
    Split on the largest contiguous whitespace.  If that is at the start
    or end of the line, then check if there is large whitespace at the
    opposite end of the line, too, and return the stripped line as centered.
    """
    left = center = right = ""
    pos = 0
    prev = 0
    count = 0
    bestp = 0
    bestc = 0
    for i, c in enumerate(line):
        if c == ' ':
            if prev+1 == i:
                count += 1
                prev = i
            else:

                pos = i
                prev = i
                count = 1
        if count > bestc:
            bestp = pos
            bestc = count
    # 
    if bestc < 2 or bestp == 0 or bestp == len(line.rstrip()):
        rwhite = len(line)-len(line.rstrip())
        lwhite = len(line)-len(line.lstrip())
        if abs(rwhite-lwhite) < max(2, min(rwhite, lwhite)):
            center = line.strip()
    if not center:
        left, right = line[:bestp].rstrip(), line[bestp:].strip()
    return left, center, right

def indentation(line):
    return len(line.txt) - len(line.txt.lstrip())

def parse_section_start(line, numlist, level, appendix):
    text = line.txt
    if appendix:
        match = re.search(appendix_prefix, text)
        if match:
            text = text[len(match.group(0)):]
    parts = text.strip().split(None, 1)
    if len(parts) == 2:
        number, title = parts
    elif len(parts) == 1:
        number, title = parts[0], ""
    else:
        return None, ""
    return number, title

def clean_name(txt):
    if txt.endswith('.txt'):
        txt = txt[:-4]
    if re.search('-[0-9][0-9]$', txt):
        txt = txt[:-3]
    return txt

def slugify(s):
    s = s.strip().lower()
    s = re.sub(r'[^\w\s./-]', '', s)
    s = re.sub(r'[-\s/]+', '-', s)
    s = s.strip('-')
    return s

def flatten(l):
    def flatgen(l):
        for i in l:
            if not type(i) is list:
                yield i
            else:
                for j in flatten(i):
                    yield j
    return list(flatgen(l))

def strip(para):
    para = para[:]
    while para and para[0].txt.strip() == '':
        del para[0]
    while para and para[-1].txt.strip() == '':
        del para[-1]
    return para

def para2str(para):
    s = ''
    for ll in [ l.txt.strip() for l in para ]:
        s += ll if not s or not ll or re.search('\S[/-]$', s) else ' '+ll
    return s

def para2text(para):
    return '\n'.join([ l.txt for l in para ]).rstrip()

def colsplit(pos, txt):
    slices = [ (pos[i-1], pos[i]) for i in range(1,len(pos)) ]
    columns = [ txt[l:r].strip() for l,r in slices ]
    return columns

def parse_date(text):
    month_names = [ 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december' ]
    month_names_abbrev3 = [ n[:3] for n in month_names ]
    month_names_abbrev4 = [ n[:4] for n in month_names ]
    date_regexes = [
        r'^(?P<month>\w+)\s(?P<day>\d{1,2})(,|\s)+(?P<year>\d{4})',
        r'^(?P<day>\d{1,2})(,|\s)+(?P<month>\w+)\s(?P<year>\d{4})',
        r'^(?P<day>\d{1,2})-(?P<month>\w+)-(?P<year>\d{4})',
        r'^(?P<month>\w+)\s(?P<year>\d{4})',
        r'\s{3,}(?P<month>\w+)\s(?P<day>\d{1,2})(,|\s)+(?P<year>\d{4})',
        r'\s{3,}(?P<day>\d{1,2})(,|\s)+(?P<month>\w+)\s(?P<year>\d{4})',
        r'\s{3,}(?P<day>\d{1,2})-(?P<month>\w+)-(?P<year>\d{4})',
        # RFC 3339 date (also ISO date)
        r'\s{3,}(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})',
        # 'October 2008' - default day to today's.
        r'\s{3,}(?P<month>\w+)\s(?P<year>\d{4})',
    ]

    for regex in date_regexes:
        match = re.search(regex, text)
        if match:
            break
    else:
        raise RuntimeError("Unrecognized date format: '%s'" % text)

    md = match.groupdict()
    mon = md['month'].lower()
    day = int( md.get( 'day', 0 ) )
    year = int( md['year'] )
    if   mon in month_names:
        month = month_names.index( mon ) + 1
    elif mon in month_names_abbrev3:
        month = month_names_abbrev3.index( mon ) + 1
    elif mon in month_names_abbrev4:
        month = month_names_abbrev4.index( mon ) + 1
    elif mon.isdigit() and int(mon) in range(1,13):
        month = int(mon)
    else:
        raise RuntimeError("Cound not resolve the month name in '%s'" % text)

    date = {
        'year': str(year),
        'month': month_names[month-1].capitalize(),
    }
    if day:
        date['day'] = str(day)
    return date

def make_author_regex(name):
    aux = {
        "honor" : r"(?:[A-Z]\.|Dr\.?|Dr\.-Ing\.|Prof(?:\.?|essor)|Sir|Lady|Dame|Sri)",
        "prefix": r"([Dd]e|Hadi|van|van de|van der|Ver|von|[Ee]l)",
        "suffix": r"(jr.?|Jr.?|II|2nd|III|3rd|IV|4th)",
        #"first" : r"([A-Z][-A-Za-z]*)(( ?\([A-Z][-A-Za-z]*\))?(\.?[- ]{1,2}[A-Za-z]+)*)",
        #"last"  : r"([-A-Za-z']{2,})",
        }
    #
    def dotexp(s):
        s = re.sub(r"\. ",    r"\w* ", s)
        s = re.sub(r"\.$",    r"\w*", s)
        s = re.sub(r"\.(\w)", r"\w* \1", s)
        return s
    #
    # remove any suffix from the name before building the pattern
    suffix_match = re.search(" %(suffix)s$" % aux, name)
    if suffix_match:
        suffix = suffix_match.group(1)
        name = name[:-len(suffix)].strip()
    else:
        suffix = None
    #
    # Check if we have a comma, and reversed order first/last name
    if "," in name:
        last, first = name.split(",",1)
        name = "%s %s" % (first.strip(), last.strip())
    #
    # Check if the name consists of initials scrunched right up to surname,
    # or just a surname without any first name or initials
    if not " " in name:
        if "." in name:
            first, last = name.rsplit(".", 1)
            first += "."
        else:
            name = "[A-Z].+ " + name
            first, last = name.rsplit(" ", 1)
    else:
        first, last = name.rsplit(" ", 1)
        if "." in first and not ". " in first:
            first = first.replace(".", ". ").strip()
    first = first.strip()
    last = last.strip()
    #
    # did we manage to get a 'von ', 'van ', 'de ' etc. as part of the
    # first name instead of the surname?  If so, 
    prefix_match = re.search(" %(prefix)s$" % aux, first)
    if prefix_match:
        prefix = prefix_match.group(1)
        first = first[:-len(prefix)].strip()
        last = prefix+" "+last
    #
    # Replace abbreviation dots with regexp
    first = dotexp(first)
    last = dotexp(last)
    first = re.sub("[()]", " ", first)
    if " " in first:
        # if there's a middle part, let it be optional
        first, middle = first.split(" ", 1)
        first = "%s( +%s)?" % (first, middle)
    #
    # Double names (e.g., Jean-Michel) are abbreviated as two letter
    # connected by a dash -- let this expand appropriately
    first = re.sub(r"^([A-Z])-([A-Z])\\w\*", r"\1.*-\2.*", first) 
    #
    # Some chinese names are shown with double-letter(latin) abbreviated given names, rather than
    # a single-letter(latin) abbreviation:
    first = re.sub(r"^([A-Z])[A-Z]+\\w\*", r"\1[-\w]+", first) 
    #
    # permit insertion of middle names between first and last, and
    # add possible honorific and suffix information
    regex = r"(?:^| and )(?:%(hon)s ?)?(%(first)s\S*( +[^ ]+)* +%(last)s)( *\(.*|,( [A-Z][-A-Za-z0-9]*)?| %(suffix)s| [A-Z][a-z]+)?" % {"hon":aux['honor'], "first":first, "last":last, "suffix":suffix,}
    return regex

#@debug.trace
def match_name(name, authors):
    """
    Check the full name 'name' against the initials+surname in the list
    of dictionaries in 'authors', and return the matching author item.
    """
    #----------
    # If there's a comma, we have revered name order (last, first)
    for author in authors:
        if not 'regex' in author:
            briefname = author['initials']+' '+author['surname']
            author['regex'] = make_author_regex(briefname)
        regex = author['regex']
        if re.match(regex, name):
            return author

def symbol_ratio(text):
    wc = sum( c.isspace() for c in text )
    ac = sum( c.isalnum() for c in text )
    # symbol count is total minus whitespace and alphanumerics
    sc = len(text) - wc - ac
    sr = float(sc)/ac if ac else sc
    return sr

def count_lines(text, width):
    "Return a fractional line count (filled lines plus fraction of last line)"
    lines = text.splitlines()
    count = len(lines[:-1])+len(lines[-1])/width
    return count

def indentation_levels(para):
    ind = []
    for line in strip(para):
        if len(line.txt):
            i = indentation(line)
            if not i in ind:
                ind.append(i)
    ind.sort()
    return ind

def table_borders(para):
    symbols = ['-','=','|','+',]
    borders = []
    for line in para:
        if line.txt:
            l = ''.join([ ( c if c in symbols else ' ' ) for c in line.txt ]).strip()
            # get rid of solitary dashes which could occur in table cell text
            if re.search('[A-Za-z0-9]', line.txt):
                l = re.sub(' [-+]( |$)', r'  \1', l)
            if l:
                borders.append(l)
    borders.sort()
    return borders
#@debug.trace
def guess_list_style(line, slice=None):
    list_styles = [
        # Check these in order:
        ('numbers', r'^[1-9][0-9]?\.$'),
        ('letters', r'^[a-z]\.$'),
        ('symbols', r'^[o*+-]$'),
        ('hanging', r'\S.+'),
        ('empty',   r'^$'),
    ]
    text = line.txt
    strp = text.strip()
    ind = indentation(line)
    if (   re.search('^\S+  ', strp)        # doublespace after one nonspace chunk
        or re.search('^.+[^.]  ', strp)):   # doublespace after arbitrary characters, but no period before spaces
        if slice:
            b, e = slice
        else:
            b = ind
            e = text.find('  ', b)+2
        marker = text[b:e].rstrip()
        text =   text[e:]
    elif re.search(r'^[1-9a-z]\. ', strp):
        marker, text = strp.split(None, 1)
    elif re.search(r'^[o*+-] \S', strp):
        marker, text = strp.split(None, 1)
    else:
        marker = strp
        text = ''
    style = None
    for name, regex in list_styles:
        if re.search(regex, marker):
            style = name
            break
    return style, marker, ind, text


def unindent(text, amount):
    prefix = ' '*amount
    fixed = []
    for line in text.splitlines():
        if line.strip() != '' and not line.startswith(prefix):
            return textwrap.dedent(text)
        fixed.append(line[amount:])
    return '\n'.join(fixed)

def match_boilerplate(bp, txt):
    if txt.startswith(bp):
        return True
    else:
        return False

def dtrace(fn):
    # From http://paulbutler.org/archives/python-debugging-with-decorators,
    # substantially modified
    """
    Decorator to print information about a method call for use while
    debugging.  Prints method name, arguments, and call number when
    the function is called. Prints this information again along with the
    return value when the method returns.

    This implementation expects a 'self' argument, so won't do the right
    thing for most functions.
    """
    from decorator import decorator
    import traceback as tb

    def fix(s,n=64):
        import re
        s = re.sub(r'\\t', ' ', s)
        s = re.sub(r'\s+', ' ', s)
        if len(s) > n+3:
            s = s[:n]+"..."
        return s
    def dtrace(fn, self, *params,**kwargs):
        call = dtrace.callcount = dtrace.callcount + 1
        if self.options.debug and (self.options.trace_all or fn.__name__ in self.options.trace_methods):
            indent = ' ' * self.options.logindent[0]
            filename, lineno, caller, code = tb.extract_stack()[-3]
            fc = "%s(%s)" % (fn.__name__, ', '.join(
                [fix(repr(a)) for a in params] +
                ["%s = %s" % (a, fix(repr(b))) for a,b in kwargs.items()]
            ))
            sys.stderr.write("%s* %s [#%s] From %s(%s) L%s\n" % (indent, fc, call, caller, lineno, self.l))
            #
            prevfunc = self.funcname
            self.funcname = fn.__name__
            self.options.logindent[0] += 2
            ret = fn(self, *params,**kwargs)
            self.options.logindent[0] -= 2
            self.funcname = prevfunc
            #
            sys.stderr.write("%s  %s [#%s] ==> %s\n" % (indent, fc, call, fix(repr(ret))))
        else:
            ret = fn(self, *params,**kwargs)

        return ret
    dtrace.callcount = 0
    return decorator(dtrace, fn)


class Stack(deque):
    def __init__(self, text):
        sep = r'(\s+|[][<>(),;\'"])'
        tokens = re.split(sep, text)
        super(Stack, self).__init__(tokens)
    def pop(self):
        try:
            return super(Stack, self).popleft()
        except IndexError:
            return None
    def push(self, x):
        return super(Stack, self).appendleft(x)

class Base(object):
    options = Options(debug=False, trace_all=False, trace_methods=[])
    funcname = None

    def emit(self, msg):
        sys.stderr.write(wrap(msg))
        if not msg.endswith('\n'):
            sys.stderr.write('\n')

    def dsay(self, s):
        if self.options.debug:
            if self.options.trace_all or self.funcname in self.options.trace_methods:
                frame, filename, lineno, funcname, lines, lineindex = inspect.stack()[1]
                indent = ' ' * self.options.logindent[0]
                sys.stderr.write("%s%s(%s): %s\n" % (indent, funcname, lineno, s))

    def dshow(self, name):
        if self.options.debug:
            if self.options.trace_all or self.funcname in self.options.trace_methods:
                frame, filename, lineno, funcname, lines, lineindex = inspect.stack()[1]
                value = eval(name, frame.f_globals, frame.f_locals)
                indent = ' ' * self.options.logindent[0]
                sys.stderr.write("%s%s(%s).%s: '%s'\n" % (indent, funcname, lineno, name, value))

    def dpprint(self, name):
        if self.options.debug:
            if self.options.trace_all or self.funcname in self.options.trace_methods:
                frame, filename, lineno, funcname, lines, lineindex = inspect.stack()[1]
                value = eval(name, frame.f_globals, frame.f_locals)
                indent = ' ' * self.options.logindent[0]
                sys.stderr.write("%s%s(%s).%s:\n" % (indent, funcname, lineno, name))
                lines = pformat(value).split('\n')
                for line in lines:
                    sys.stderr.write("%s  %s\n"%(indent, line))

    def warn(self, lnum, text):
        # compose message.  report 1-based line numbers, rather than 0-based.
        msg = "\n%s(%s): Warning: %s" % (self.name, lnum+1, text)
        self.emit(msg)

    def err(self, lnum, text):
        msg = "\n%s(%s): Error: %s" % (self.name, lnum+1, text)
        if self.options.debug:
            raise RuntimeError(wrap(msg))
        else:
            self.emit(msg)
            sys.exit(1)

class TextParser(Base):
    """
    This class parses plain text, nothing else.  Any lists or figures must
    have been split off before using this parser.  Plain text handled here
    can contain strings which can be converted to eref elements (urls) and
    xref elements ([REFERENCE] or Section X.y or combinations thereof).
    """

    quotes = {
        '"': '"',
    }
    angles = {
        '<': '>',
    }
    squares = {
        '[': ']'
    }
    endq = dict( (k,v) for (k,v) in quotes.items()+angles.items()+squares.items() )
    #
    prev = None
    
    def __init__(self, docparser, text):
        self.docparser = docparser
        self.stack = Stack(text)
        # These are for dtrace and friends:
        self.options = docparser.options
        self.l = docparser.l

    @dtrace
    def pop(self):
        "Almost the same as self.stack.pop(), but hides '\n'."
        tok = self.stack.pop()
        if tok and tok[0] == '\n':
            tok = self.nl()
        self.prev = tok
        return tok

    def drop(self, n):
        for i in range(n):
            self.stack.pop()

    @dtrace
    def push(self, tok):
        return self.stack.appendleft(tok)

    def peek(self, n):
        chunks = []
        for i in range(n):
            try:
                chunks.append(self.stack[i])
            except IndexError:
                break
        # get rid of empty chunks (but keep whitespace)
        chunks = [ c for c in chunks if c ]
        return chunks

    @dtrace
    def nl(self):
        "Found a newline.  Process following whitespace and return an appropriate token."
        self.dshow('self.prev')
        while True:
            tok = self.stack.pop()
            if tok is None:
                break
            if tok.strip() != '':
                self.stack.push(tok)
                break
        tok = '' if self.prev and re.search(r'\w[-/]$', self.prev) else ' '
        return tok

    @dtrace
    def get_quoted(self, tok):
        """
        Get quoted or bracketed string. Does not handle nested instances.
        """
        chunk = tok
        qbeg = tok
        qend = self.endq[tok]
        while True:
            tok = self.pop()
            if tok is None:
                break
            elif tok == qbeg and not tok in self.quotes:
                tok = self.get_quoted(tok)
            chunk += tok
            if tok == qend:
                break
        return chunk

    @dtrace
    def get_section_quotation(self):
        parts = self.peek(3)
        self.dshow('parts')
        if not len(parts) == 3:
            return self.stack.pop()
        keyword, space, number = parts
        self.dshow('number')
        if not re.search('^[0-9.]+$', number):
            return self.stack.pop()
        else:
            section = number.rstrip('.')
            target = 'section-%s'%slugify(section)
            self.dshow('target')
            # check if this is a section of something else
            parts = self.peek(3+6)
            # see if we have [' ', 'of', ' ', 'RFCnnnn', ]
            # or maybe  [' ', 'of', ' ', '[', 'RFCnnnn', ']', ]
            if parts and len(parts)>=7 and parts[4] == 'of' and not parts[5] == 'this':
                # It would have been nice to insert erefs here, but xml2rfc
                # don't provide the option of rendering an eref only with
                # the given text, without a '[1]' type URIs section
                # citation string.
                return self.stack.pop()

                #self.dpprint('parts')
                #if parts[6].startswith('RFC'):
                #    doc = parts[6].lower()
                #    number = doc[3:]
                #    if not number.isdigit():
                #        return self.stack.pop()
                #    target=self.options.rfc_url.format(number=number, fragment=target)
                #    text = ''.join(parts[:6])
                #    self.drop(6)
                #    return self.docparser.element('eref', text, target=target)
                #elif parts[6].startswith('draft-'):
                #    doc = parts[6].lower()
                #    target=self.options.draft_url.format(draft=doc, fragment=target)
                #    text = ''.join(parts[:6])
                #    self.drop(6)
                #    return self.docparser.element('eref', text, target=target)
                #elif parts[6] == '[' and parts[7].startswith('RFC'):
                #    doc = parts[7].lower()
                #    number = doc[3:]
                #    if not number.isdigit():
                #        return self.stack.pop()
                #    target=self.options.rfc_url.format(number=number, fragment=target)
                #    text = ''.join(parts[:3])
                #    self.drop(3)
                #    return self.docparser.element('eref', text, target=target)
                #elif parts[6] == '[' and parts[7].startswith('draft-'):
                #    doc = parts[7].lower()
                #    target=self.options.draft_url.format(draft=doc, fragment=target)
                #    text = ''.join(parts[:3])
                #    self.drop(3)
                #    return self.docparser.element('eref', text, target=target)
                #else:
                #    return self.stack.pop()
            else:
                if target in self.docparser.section_anchors:
                    self.drop(3)
                    if number != section:
                        assert number.startswith(section)
                        self.stack.push(number[len(section):]) # trailing punctuation
                    return self.docparser.element('xref', target=target)
                else:
                    return self.stack.pop()

    @dtrace
    def parse_text(self):
        "A sequence of text, xref, and eref elements."
        chunks = []
        while True:
            tok = self.stack.pop()
            if tok is None:
                break
            if tok in self.quotes:
                tok = self.get_quoted(tok)
            elif tok == 'Section':
                self.push(tok)
                # handle Section N.n (of RFCxxxx)
                tok = self.get_section_quotation()
            elif tok in self.squares:
                tok = self.get_quoted(tok)
                ref = tok[1:-1]
                if ref.isdigit():
                    target = "ref-%s" % ref
                else:
                    target = ref
                if target in self.docparser.reference_anchors:
                    tok = self.docparser.element('xref', target=target)
            elif tok in self.angles:
                tok = self.get_quoted(tok)
                match = re.search(uri_re, tok)
                if match:
                    target= match.group('target')
                    tok = self.docparser.element('eref', target=target)
            elif re.search(uri_re, tok):
                uri = tok
                tok = self.pop()
                if tok == '':
                    tok = self.pop()
                    uri += tok
                else:
                    self.push(tok)
                self.dshow('uri')
                match = re.search(uri_re, uri)
                target= match.group('target')
                tok = self.docparser.element('eref', target=target)
            elif tok == '\n':
                tok = self.nl()
            chunks.append(tok)
        t = self.docparser.element('t')
        if chunks:
            e = None
            text = []
            for chunk in chunks:
                if isinstance(chunk, six.string_types):
                        text.append(chunk)
                else:
                    if e is None:
                        t.text = ''.join(text)
                    else:
                        e.tail = ''.join(text)
                    text = []
                    e = chunk
                    t.append(e)
            if text:
                if e is None:
                    t.text = ''.join(text)
                else:
                    e.tail = ''.join(text)
        self.docparser.dshow('t.text')
        return t


class DraftParser(Base):

    text = None
    root = None
    name = None
    schema = None
    entities = []
    pi = {}
    #
    _identify_paragraph_cache = {}
    figure_and_table_anchors = {}
    section_anchors = []
    reference_anchors = []

    rfc_pi_defaults = {
        'strict': 'yes',
        'compact': 'yes',
        'subcompact': 'no',
        # we start out with symrefs="no", then change the setting to
        # "yes" if we find a non-numeric reference anchor:
        'symrefs': 'no',
        'sortrefs': 'no',
        'text-list-symbols': '        ',
    }

    def __init__(self, name, text, options):
        self.options = options
        self.name = name
        self.is_draft = name.startswith('draft-')
        self.is_rfc = name.lower().startswith('rfc')
        if not (self.is_draft or self.is_rfc):
            self.err(0, "Expected the input document name to start with either 'draft-' or 'rfc'")
        assert type(text) is six.text_type # unicode in 2.x, str in 3.x.  
        self.raw = text
        schema_file = os.path.join(os.path.dirname(__file__), 'data', self.options.schema+'.rng')
        self.schema = ElementTree(file=schema_file)
        self.rfc_attr = self.schema.xpath("/x:grammar/x:define/x:element[@name='rfc']//x:attribute", namespaces=ns)
        self.rfc_attr_defaults = dict( (a.get('name'), a.get("{%s}defaultValue"%ns['a'], None)) for a in self.rfc_attr )

    @dtrace
    def get_tabstop(self, line):
        """
        Disregarding leading whitespace, return the start column
        of any text which follows more than one space, relative
        to the left margin at column 3.
        """
        match = re.search(r'^(\s*\S+(\s\S+)*\s\s+)(\S.*)$', line.txt)
        if match:
            # return co
            return max(2, len(match.group(1)) - 3)
        else:
            self.warn(line.num, "Expected a line with tabstop, found '%s'" % (line.txt, ))

    def set_pi(self, e, k, v):
        if not k in self.pi or self.pi[k] != v:
            self.pi[k] = v
            pi = ProcessingInstruction('rfc', text='%s="%s"'%(k,v))
            pi.tail = '\n\t'
            e.append(pi)
            return pi
        else:
            return None
            
    @dtrace
    def set_symbols_pi(self, symbol, level):
        if self.pi['text-list-symbols'][level] == ' ':
            assert len(symbol) == 1
            symlist = list(self.pi['text-list-symbols'])
            symlist[level] = symbol
            self.pi['text-list-symbols'] = ''.join(symlist)
        return self.pi['text-list-symbols']

    def parse_to_xml(self, **kwargs):
        # fix some bloopers
        self.lines, self.short_title = strip_pagebreaks(self.raw.expandtabs())
        self.l = -1
        self.p = None

        # Set up the <rfc/> element as root
        self.root = self.element('rfc', None)
        for attr in self.rfc_attr_defaults:
            if not ':' in attr:
                val = self.rfc_attr_defaults[attr]
                if val:
                    self.root.set(attr, val)
        for attr in kwargs:
            if attr in self.rfc_attr_defaults:
                val = kwargs[attr]
                self.root.set(attr, val)

        # Default PI settings (at least some which differes from the xml2rfc
        # defaults)
        for k,v in self.rfc_pi_defaults.items():
            pi = self.set_pi(self.root, k, v)
            if k == 'symrefs':
                self.symrefs_pi = pi
            elif k == 'sortrefs':
                self.sortrefs_pi = pi
            elif k == 'text-list-symbols':
                self.symbols_pi = pi


        # Parse the document
        doc = self.document()

        # Return the xml document (if any)
        if len(doc):
            doctype = '<!DOCTYPE rfc SYSTEM "rfc2629.dtd"'
            if self.entities:
                doctype += ' [\n'
                for entity in self.entities:
                    doctype += '<!ENTITY {name} SYSTEM "{url}">\n'.format(**entity)
                doctype += ']'
            doctype +='>'

            return lxml.etree.tostring(
                doc,
                xml_declaration=True,
                encoding='utf-8',
                doctype=doctype,
                pretty_print=True,
            ).decode('utf-8')
        else:
            self.err(self.lines[self.l].num, "Failed producing an xml tree, bailing out")
            return None

    def document(self):
        self.root.append(self.front())
        self.root.append(self.middle())
        self.root.append(self.back())
        self.postprocess()
        return self.root

    @dtrace
    def element(self, tag, *args, **kwargs):
        "A wrapper method which lets us hook in debug output and massage it a bit."
        e = Element(tag, **kwargs)
        if tag in ['front', 'middle', 'back', 'section', 'author', 't', ]:
            e.tail = '\n\n\t'
        else:
            e.tail = '\n\t'
        if tag in ['xml', 'front', 'middle', 'back', 'section', 'author', 'abstract', 'references', ]:
            e.text = '\n\t'
        if args:
            assert len(args) == 1
            text = args[0]
            e.text = text
        return e

    # ------------------------------------------------------------------------
    # front
    # ------------------------------------------------------------------------
    @dtrace
    def front(self):
        # (title , author+ , date , area* , workgroup* , keyword* , abstract? , note*)
        lines_left, lines_right, lines_title, lines_name = self.get_first_page_top()
        #
        if self.is_draft and lines_name:
            self.root.set('docName', lines_name.txt)
        #

        workgroup, stream, series_number, rfc_number, obsoletes, updates, category, expires = self.parse_top_left(lines_left)

        authors, date = self.parse_top_right(lines_right)

        authornames = [ a['fullname'] for a in authors ] + [ a['organization'] for a in authors ]
        
        # fixups
        if not stream and category in ['std', 'bcp']:
            stream = 'IETF'
        if not stream and 'Internet Architecture Board' in authornames:
            stream = 'IAB'

        if stream:
            self.root.set('submissionType', stream)
        if rfc_number:
            self.root.set('number', rfc_number)
        if category:
            self.root.set('category', category)
            if series_number:
                self.root.set('seriesNo', series_number)
        if obsoletes:
            self.root.set('obsoletes', ', '.join(obsoletes))
        if updates:
            self.root.set('updates', ', '.join(updates))

        front = self.element('front')
        title = self.element('title', para2str(lines_title))
        if not self.short_title and len(title.text) > 40:
            self.short_title = title.text[:40]

        if self.short_title and self.short_title.strip() != title.text.strip():
            title.set('abbrev', self.short_title)
        front.append(title)
        #
        for item in authors:
            author = {}
            # pick out the elements which are valid as <author> attributes
            author_attrib_elem = self.schema.xpath("/x:grammar/x:define/x:element[@name='author']//x:attribute", namespaces=ns)
            author_attributes = [ a.get('name') for a in author_attrib_elem ]

            for key in author_attributes:
                if key in item:
                    author[key] = item[key]
            e = self.element('author', **author)
            if 'organization' in item:
                e.append(self.element('organization', item.get('organization')))
            front.append(e)
        #
        front.append(self.element('date', **date))
        #
        if workgroup:
            front.append(self.element('workgroup', workgroup))
        #
        abstract = self.section(numlist=["Abstract"], tag='abstract', part='front')
        if not abstract is None:
            front.append(abstract)
        #
        while True:
            note = self.note()
            if note is None:
                break
            front.append(note)
        #
        self.read_status_of_memo(workgroup, stream, rfc_number, category, date)
        line = self.skip_blank_lines()
        if re.search('Copyright Notice', line.txt.strip()):
            self.read_copyright(date)

        line = self.skip_blank_lines()
        if line.txt == 'Table of Contents':
            self.section(['Table'], tag='toc', part='front')
            self.set_pi(self.root, 'toc', 'yes')
        return front

    @dtrace
    def get_first_page_top(self):
        lines_left = []
        lines_right = []
        lines_title = []
        lines_name = []
        pad_len = 64                    # a bit less than 72, to accomodate some older documents
        found_rightleft = False
        #
        self.skip_blank_lines()
        while True:
            self.dshow('self.l')
            self.dshow('self.lines[self.l]')
            line, p = self.get_line()
            if line.txt.strip() == "":
                if lines_title and lines_name and found_rightleft:
                    break
                else:
                    continue
            # maybe pad line, to let us recognize centered text
            if len(line.txt) > pad_len:
                pad_len = min(len(line.txt), 72)
                padded = line.txt
            else:
                padded = (line.txt + ' '*pad_len)[:pad_len]
            left, center, right = split_on_large_whitespace(padded)
            if left.lower() in section_names['front']:
                self.dsay('found section name, breaking off')
                self.push_line(line, p)
                break
            if center:
                self.dsay('found centered line: %s' % (center, ))
                if 'draft-' in center and not ' ' in center:
                    lines_name = Line(line.num, center.strip("[]<>"))
                    assert lines_name[1].startswith('draft-')
                else:
                    lines_title.append(Line(line.num, center))
            else:
                self.dsay('found left/right line: %s | %s' % (left, right))
                found_rightleft = True
                lines_left.append(Line(line.num, left))
                lines_right.append(Line(line.num, right))
        return lines_left, lines_right, lines_title, lines_name

    @dtrace
    def skip_blank_lines(self):
        """
        Skip over blank lines, ending up before the first non-blank line,
        or at end of text.  Return the coming non-blank line.
        """
        while True:
            line, p = self.get_line()
            if line is None:
                break
            if not line.txt.strip() == "":
                self.push_line(line, p)
                break
        return line
    next_line = skip_blank_lines

    def get_line(self):
        "Get the next line, whether blank or not, or None if no more lines."
        if self.p == None:
            self.l += 1
        line = self.lines[self.l] if self.l < len(self.lines) else None
        p = self.p
        if self.p:
            line = Line(line.num, line.txt[self.p:])
            self.p = None
        if self.options.debug:
            if self.options.trace_start_regex and not self.options.trace_all:
                if line and re.search(self.options.trace_start_regex, line.txt.strip()) != None:
                    self.options.trace_all = True
            if self.options.trace_start_line and not self.options.trace_all:
                if line and line.num == self.options.trace_start_line:
                    self.options.trace_all = True
            if self.options.trace_all:
                if line and (line.num == self.options.trace_start_line
                             or (self.options.trace_start_regex
                                 and re.search(self.options.trace_start_regex, line.txt.strip())) != None):
                    # reset the tail count on every new ocurrence of the start pattern
                    self.options.trace_tail = -1
                #
                if self.options.trace_tail > 0:
                    self.options.trace_tail -= 1
                elif self.options.trace_tail == 0:
                    self.options.trace_tail -= 1
                    self.options.trace_all = False
                elif (line and self.options.trace_stop_line == line.num
                      or (line and self.options.trace_stop_regex
                          and re.search(self.options.trace_stop_regex, line.txt.strip()) != None)):
                    self.options.trace_tail = self.options.trailing_trace_lines

        self.dshow('line')
        return line, p

    def get_text_line(self):
        "Skip blank lines if any, and return the first non-blank line or None if no more lines"
        while True:
            line, p = self.get_line()
            if not line or not line.txt.strip() == "":
                return line, p

    def prev_line(self):
        return self.lines[self.l-1]

    @dtrace
    def get_para(self):
        para = []
        # skip blank lines
        while True:
            line, p = self.get_line()
            if line is None:
                return para
            if not line.txt.strip() == "":
                break
        # collect non-blank lines
        while True:
            para.append(line)
            line, p = self.get_line()
            if line is None:
                break
            if line.txt.strip() == "":
                para.append(line)
                break
        return para


    def next_para(self):
        saved_l = self.l
        saved_p = self.p
        para = self.get_para()
        self.l = saved_l
        self.p = saved_p
        return para

    def next_text(self):
        "Skip blank lines if any, then read lines until new blank line, and return text."
        return para2str(self.next_para())

    def push_line(self, push, pos):
        self.dshow('push')
        if not self.lines[self.l].txt[pos:] == push.txt:
            if True:
                debug.show('pos')
                debug.show('self.lines[self.l]')
                debug.show('self.lines[self.l].txt[pos:]')
                debug.show('push')
            assert self.lines[self.l].txt[pos:] == push.txt
        if pos:
            self.p = pos
        else:
            self.l -= 1

    def push_part(self, push, pos):
        if not self.lines[self.l] == push:
            if True:
                debug.show('self.lines[self.l]')
                debug.show('self.lines[self.l].txt[self.p:]')
                debug.show('push')
            assert self.lines[self.l] == push
        self.p = pos

    def push_para(self, para):
        para.reverse()
        for line in para:
            self.push_line(line, 0)

    @dtrace
    def parse_top_left(self, lines):
        """
        Parse the top left of a draft or RFC.

        Xml2Rfc renders top left elements in this order:
        - workgroup or 'Network Working Group' if draft else stream-name
        - 'Internet-Draft' or RFC number
        - maybe series_name: series_number
        - maybe obsoletes note
        - maybe updates note
        - intended status or category
        - expiration note if draft
        - maybe ISSN number if rfc
        """
        class Result(object):
            workgroup=None
            stream=None
            series_number=None
            rfc_number=None
            obsoletes=[]
            updates=[]
            status=None
            expires=None
        res = Result()

        @dtrace
        def get_stream(self, lines, res, entries):
            # Get workgroup or stream
            submission_types = {
                'Network Working Group':                    None,
                'Internet Engineering Task Force (IETF)':   'IETF',
                'Internet Architecture Board (IAB)':        'IAB',
                'Internet Research Task Force (IRTF)':      'IRTF',
                'Independent Submission':                   'independent',
            }
            line = lines.pop(0) if lines else Line(None, "")
            self.dshow('line')
            if line.txt in submission_types.keys():
                res.stream = submission_types[line.txt]
                if self.is_draft and res.stream != None:
                    self.warn(line.num, "The input document is named '%s' but has an RFC stream type:\n  '%'" % (self.name, line.txt))
            elif self.is_draft:
                # check all the possible top left keywords:
                for k in entries:
                    regex = entries[k]['regex']
                    if regex and re.search(regex, line.txt):
                        # no explicit workgroup.  remember line, and move on
                        res.workgroup = ""
                        lines.insert(0, line)
                        self.dsay("pushing '%s'" % line.txt)
                        break
                else:
                    res.workgroup = line.txt
                    res.stream = None
            else:
                self.warn(line.num, "Unrecognized stream indicator in document top left: '%s'" % line.txt)
                
        @dtrace
        def get_label(self, lines, res):
            # get internet-draft or RFC number
            line = lines.pop(0) if lines else Line(None, "")
            self.dshow('line')
            if self.is_draft and not line.txt.lower() == 'internet-draft':
                self.warn(line.num, "Expected to see 'Internet-Draft', found '%s'" % line.txt)
                lines.insert(0, line)
                self.dsay("pushing '%s'" % line.txt)
            elif self.is_rfc:
                rfc_string = 'Request for Comments:'
                if not line.txt.startswith(rfc_string):
                    self.warn(line.num, "Expected to see '%s ...', found '%s'" % (rfc_string, line.txt))
                    res.rfc_number = "XXXX"
                    lines.insert(0, line)
                    self.dsay("pushing '%s'" % line.txt)
                else:
                    res.rfc_number = line.txt.split()[3]
                    if not res.rfc_number.isdigit():
                        self.warn(line.num, "Expected a numeric RFC number, found '%s'" % res.rfc_number)
            
        @dtrace
        def get_series(self, lines, res):
            # maybe get series name and number
            series_names = {
                'STD:': 'std',
                'BCP:': 'bcp',
                'FYI:': 'fyi',
            }
            if self.is_rfc:
                line = lines.pop(0) if lines else Line(None, "")
                self.dshow('line')
                w = line.txt.split()[0]
                if w in series_names:
                    res.series_number = line.txt.split(None, 1)[-1]
                else:
                    lines.insert(0, line)
                    self.dsay("pushing '%s'" % line.txt)

        @dtrace
        def get_modifies(self, lines, res):
            # maybe obsoletes and/or updates note
            self.dsay('Looking for Obsoletes: and Updates:')
            while True:
                line = lines.pop(0) if lines else Line(None, "")
                if line.txt.strip() == '':
                    break
                w = line.txt.lower().split()[0].rstrip(':')
                W = w.capitalize()
                if w in ['obsoletes', 'updates']:
                    if not line.txt.startswith('%s:' % W):
                        self.warn(line.num, "Expected the %s notice to start with '%s:', found '%s'" % (w, W, line.txt))
                    # get continuation lines
                    clause = line.txt
                    self.dshow('clause')
                    while True:
                        line = lines.pop(0) if lines else Line(None, '')
                        self.dshow('line')
                        # 3 spaces here is arbitraty; this should maybe be ' '*min([len('obsoletes'), len('updates')]) or just ' '
                        if line.txt.startswith('   '):
                            clause += ' '+line.txt.strip()
                        else:
                            lines.insert(0, line)
                            self.dsay("pushing '%s'" % line.txt)
                            break
                    if self.is_draft and not '(if approved)' in clause:
                        self.warn(line.num, "Expected the %s notice to end with '(if approved)', found '%s'" % (w, clause))
                    clause = clause.replace('(if approved)', '')
                    numbers = clause.split()[1:]
                    num_list = [ n for n in numbers if n.isdigit() ]
                    if w == 'obsoletes':
                        res.obsoletes = num_list
                    if w == 'updates':
                        res.updates += num_list
                else:
                    break
            lines.insert(0, line)
            self.dsay("pushing '%s'" % line.txt)

        @dtrace
        def get_category(self, lines, res):
            # maybe intended status or category
            category_names = {
                'Standards Track':          'std',
                'Standard Track':           'std',
                'Proposed Standard':        'std',
                'Draft Standard':           'std',
                'Internet Standard':        'std',
                'Standard Track':           'std',
                'Best Current Practice':    'bcp',
                'Experimental':             'exp',
                'Informational':            'info',
                'Historic':                 'historic',
            }
            line = lines.pop(0) if lines else Line(None, '')
            self.dshow('line')
            if self.is_draft:
                if line.txt.lower().startswith('intended status: '):
                    status_text = line.txt.split(None, 2)[-1].strip()
                    if not status_text in category_names:
                        self.warn(line.num, "Expected a recognized status name, found '%s'" % (line.txt, ))
                    else:
                        res.status = category_names[status_text]
                else:
                    self.warn(line.num, "Expected 'Intended status: ', found '%s'" % (line.txt, ))
                    lines.insert(0, line)
                    self.dsay("pushing '%s'" % line.txt)
            else:
                if line.txt.startswith('Category: '):
                    status_text = line.txt.split(None, 1)[-1].strip()
                    if not status_text in category_names:
                        self.warn(line.num, "Expected a recognized category, found '%s'" % (line.txt, ))
                    else:
                        res.status = category_names[status_text]
                else:
                    self.warn(line.num, "Expected 'Category: ', found '%s'" % (line.txt, ))
                    lines.insert(0, line)
                    self.dsay("pushing '%s'" % line.txt)

        @dtrace
        def get_expiration(self, lines, res):
            # maybe expiration date
            if self.is_draft:
                line = lines.pop(0) if lines else Line(None, '')
                self.dshow('line')
                if line.txt.startswith('Expires: '):
                    try:
                        res.expires = parse_date(line.txt.split(None, 1)[-1])
                    except RuntimeError as e:
                        self.warn(line.num, e)
                    line = lines.pop(0) if lines else Line(None, "")
                    self.dshow('line')
                else:
                    self.warn(line.num, "Expected an expiration date, found '%s'" % (line.txt,))

        @dtrace
        def get_issn(self, lines, res):
            if self.is_rfc and lines[0].txt:
                line = lines.pop(0) if lines else Line(None, '')
                self.dshow('line')
                if line.txt.strip() == 'ISSN: 2070-1721':
                    pass
                else:
                    self.warn(line.num, "Expected an ISSN number, found '%s'" % (line.txt, ))

        entries = {
            'stream':   dict(order=0, needed=True, function=get_stream,     regex=None, help='' ),
            'label':    dict(order=1, needed=True, function=get_label,      regex=r"(?i)^(Internet-Draft|Request for Comments: )",
                        help='such as Internet-Draft or Request for Comments'),
            'series':   dict(order=2, needed=False,function=get_series,     regex=r"^(STF|BCP|FYI): ", help='' ),
            'modifies': dict(order=3, needed=False,function=get_modifies,   regex=r"^(Updates|Obsoletes)", help='' ),
            'category': dict(order=4, needed=True, function=get_category,   regex=r"^(Intended [Ss]tatus|Category)", help='' ),
            'expires':  dict(order=5, needed=True, function=get_expiration, regex=r"^Expires", help='' ), 
            'issn':     dict(order=6, needed=True, function=get_issn,       regex=r"^ISSN: ", help='' ), 
        }
        if self.is_rfc:
            entries['expires']['needed'] = False
        if self.is_draft:
            entries['issn']['needed'] = False
        # There's no regex for 'stream', so we need to handle that before we loop:
        get_stream(self, lines, res, entries)
        entries['stream']['needed'] = False
        while any([ v['needed'] for v in entries.values() ]):
            next = lines[0]
            self.dshow('next')
            for k in entries:
                v = entries[k]
                regex = v['regex']
                if regex and re.search(regex, next.txt):
                    v['function'](self, lines, res)
                    v['needed'] = False
                    break
            else:
                self.dsay(' - no regex match, breaking loop')
                break
            if not lines:
                self.dsay(' - no more lines, breaking loop')
                break

        for k in entries:
            if not entries[k]['needed'] == False:
                if k[0] in 'aeiou':
                    self.warn(self.lines[self.l].num, "Expected an %s indication top left, found none" % k)
                else:
                    self.warn(self.lines[self.l].num, "Expected a %s indication top left, found none" % k)

        for line in lines:
            if line.txt.strip():
                self.warn(line.num, "Did not expect any more top left text, found '%s'" % (line.txt, ))

        return res.workgroup, res.stream, res.series_number, res.rfc_number, res.obsoletes, res.updates, res.status, res.expires

    @dtrace
    def parse_top_right(self, lines):
        aux = {
            "honor" : r"(?:[A-Z]\.|Dr\.?|Dr\.-Ing\.|Prof(?:\.?|essor)|Sir|Lady|Dame|Sri)",
            "prefix": r"([Dd]e|Hadi|van|van de|van der|Ver|von|[Ee]l)",
            "suffix": r"(jr.?|Jr.?|II|2nd|III|3rd|IV|4th)",
            #"first" : r"([A-Z][-A-Za-z]*)(( ?\([A-Z][-A-Za-z]*\))?(\.?[- ]{1,2}[A-Za-z]+)*)",
            "first" : r"((?:[A-Z](?:-?[A-Z])?\. ?)+)",
            #"last"  : r"([-A-Za-z']{2,})",
            "last"  : r"((%(prefix)s )?[A-Z][a-z]+([- ]?[A-Z][a-z]+)?)",
            "months": r"(January|February|March|April|May|June|July|August|September|October|November|December)",
            "mabbr" : r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?",
            }
        authorformats = [
           r"^(%(first)s%(last)s)$" % aux,
            #r"^((%(first)s[ \.]{1,3})+((%(prefix)s )?%(last)s)( %(suffix)s)?)(, ([^.]+\.?|\([^.]+\.?|\)))?,?$" % aux,
            #r"^(((%(prefix)s )?%(last)s)( %(suffix)s)?, %(first)s)$" % aux,
            #r"^(%(last)s)$" % aux,
        ]
        editorformats = [
            r"(?:, | )([Ee]d\.?|\([Ee]d\.?\)|[Ee]ditor)$",
        ]

        dateformat = r"(((%(months)s|%(mabbr)s) |(%(months)s|%(mabbr)s) \d+, |\d+ (%(months)s|%(mabbr)s),? |\d+/\d+/)\d\d\d\d|\d\d\d\d-\d\d-\d\d)$" % aux
        #
        self.authors = []
        date = None
        #debug.pprint('lines')
        for line in lines:
            #debug.show('line')
            txt = line.txt
            is_editor = False
            if date and txt.strip() != '':
                self.warn(line.num, "Unexpected text; expected blank lines after document date, found '%s'" % (line, ))
                continue
            for regex in editorformats:
                if re.search(regex, txt):
                    txt = re.sub(regex, "", txt)
                    #debug.say('found editor')
                    #debug.show('txt')
                    is_editor = True
                    break
            for regex in authorformats:
                match = re.search(regex, txt)
                if match:
                    author = {
                        'fullname': match.group(1).strip(),
                        'initials': match.group(2).strip(),
                        'surname':  match.group(3).strip(),
                    }
                    if is_editor:
                        author['role'] = 'editor'
                    #debug.show('author')
                    #debug.show('regex')
                    self.authors.append(author)
                    break
            else:
                if re.search(dateformat, txt):
                    date = parse_date(txt)
                    continue
                else:
                    organization = txt
                    #debug.show('organization')
                    #debug.show('len(self.authors)')
                    for i in range(len(self.authors)-1, 0-1, -1):
                        #debug.show('i')
                        #debug.show('self.authors[i]')
                        a = self.authors[i]
                        if a.get('organization') != None:
                            break
                        self.authors[i]['organization'] = organization
        #debug.show('authors')
        #debug.show('date')
        return self.authors, date

    @dtrace
    def note(self):
        "An element similar to section, but simpler; containing only t+"
        note = None
        line = self.skip_blank_lines()
        text = line.txt.strip()
        if text.lower() in section_names['front']:
            return None
        # Advance past the line we peeked at above
        line, p = self.get_line()
        note = self.element('note', title=text)
        while True:
            paragraph = self.get_block('front')
            if paragraph is None:
                break
            elif paragraph.tag != 't':
                self.err(self.l, "Unexpected content: expected content mapping to <t>, found <%s>" % paragraph.tag)
            else:
                note.append(paragraph)
        return note

    @dtrace
    def read_status_of_memo(self, workgroup, stream, rfc_number, category, date):
        line = self.skip_blank_lines()
        if line.txt.strip().lower() == 'status of this memo':
            self.skip(line.txt)
        else:
            self.skip('Status of This Memo')
        if self.is_rfc:
            if not stream:
                self.err(line.num,
                        "Cannot parse 'Status of This Memo' without knowing the appropriate stream.  "
                        "To process an old rfc without stream info and up-to-date Status of Memo "
                        "section, please manually edit the text file to show the correct stream "
                        "and status text, then run it through this program again.")
            if not rfc_number:
                self.err(line.num, "Cannot parse 'Status of This Memo' without an RFC number.")
            if not category:
                self.err(line.num, "Cannot parse 'Status of This Memo' without the correct category information.")
            consensus = None
            # Status of memo paragraph 1
            self.skip(boilerplate['status'][category].get('p1', ""))
            # Status of memo paragraph 2, first sentence
            self.skip(boilerplate['status'][category].get('p2', ""))
            # Status of memo paragraph 2, middle part
            text = self.next_text()
            for part in boilerplate['status'].keys():
                if part.startswith(stream):
                    bp = boilerplate['status'][part]
                    if '_workgroup' in part:
                        bp = bp % workgroup
                    if match_boilerplate(bp, text):
                        consensus = '_consensus' in part
                        self.skip(bp)
                        break
            if not consensus is None:
                self.root.set('consensus', 'yes' if consensus else 'no')

            # Status of memo paragraph 2, last sentence
            text = self.next_text()
            repl = 'RFC 5741' if 'RFC 5741' in text else 'RFC 7841'
            if stream == 'IETF' and category == 'std':
                self.skip(boilerplate['status']['p2end_ietf_std'].replace('RFC 7841', repl))
            elif stream == 'IETF' and category == 'bcp':
                self.skip(boilerplate['status']['p2end_ietf_bcp'].replace('RFC 7841', repl))
            elif stream == 'IETF':
                self.skip(boilerplate['status']['p2end_ietf_other'].replace('RFC 7841', repl))
            else:
                self.skip(boilerplate['status']['p2end_other'].replace('RFC 7841', repl) % approvers.get(stream, ''))

            self.skip(boilerplate['status']['p3'] % rfc_number)
        else:
            text = self.next_text()
            if text:
                for part, d in [ ('ipr_200902_status', '200902'), ('ipr_200811_status', '200811'), ]:
                    bp = boilerplate[part]
                    if match_boilerplate(bp, text):

                        self.skip(bp)
                        break
            for text in boilerplate['status']['draft']:
                self.skip(text)
            text = self.next_text()
            bp = boilerplate['draft_expire'][:-3]
            if match_boilerplate(bp, text):
                expires = text[len(bp):-1]
                parse_date(expires)
                self.skip(boilerplate['draft_expire'] % expires)

    @dtrace
    def read_copyright(self, date):
        assert date
        self.skip('Copyright Notice')
        self.skip(boilerplate['base_copyright_header'] % date['year'])
        self.skip(boilerplate['base_copyright_body'])
        text = self.next_text()
        if text and text.startswith(boilerplate['ipr_200902_copyright_ietfbody'][:32]):
            self.skip(boilerplate['ipr_200902_copyright_ietfbody'])
        text = self.next_text()
        if text and text.startswith(boilerplate['ipr_pre5378Trust200902_copyright'][:32]):
            self.skip(boilerplate['ipr_pre5378Trust200902_copyright'])
            self.root.set('ipr', 'pre5378Trust200902')

    @dtrace
    def read_authors_addresses(self):
        line = self.skip_blank_lines()
        first = line
        if line and (line.txt.startswith("Author's Address") or  line.txt.startswith("Authors' Addresses")):
            self.skip(line.txt)
        else:
            self.err(line.num, "Expected an Authors' Addresses section, found '%s'" % (line.txt, ))
            return
        while True:
            # Fullname (Role)
            # [Organization]
            # [Address]
            #                       # (blank line)
            # [Phone: number]
            # [Fax: number]
            # [Email: address]      # or EMail
            # [URI: uri]
            #
            line = self.skip_blank_lines()
            if not line or self.is_section_start(line, part='back'):
                break
            #
            item = self.read_author_name()
            self.maybe_author_org(item)
            self.maybe_author_address(item)
            line, p = self.get_line()
            assert not line or line.txt.strip() == ''
            while True:
                found = self.maybe_address_detail(item)
                if not found:
                    break
        #
        for author in self.authors:
            auth = self.root.find(".//author[@surname='{surname}'][@initials='{initials}']".format(**author))
            if auth is None:
                self.warn(self.l, "This author is listed in the %s section, but was not found "
                                  " on the first page: %s"%(first.txt, author['fullname']))
                continue
            auth.set('fullname', author['fullname'])
            addr = self.element('address')
            auth.append(addr)
            for key in ['postal', 'phone', 'facsimile', 'email', 'uri', ]:
                if key in author['address']:
                    value = author['address'][key]
                    if key == 'postal':
                        e = self.element(key, None)
                        for line in value:
                            street = self.element('street', line)
                            e.append(street)
                        addr.append(e)
                    else:
                        e = self.element(key, value)
                        addr.append(e)

    @dtrace
    def skip(self, expect):
        "Read, match, and skip over the given text."
        self.skip_blank_lines()
        line, p = self.get_line()
        text = line.txt
        l = len(text)
        text = text.lstrip()
        strip_count = l - len(text)
        expect = expect.lstrip()
        def fail(l, e, t):
            self.err(l.num, "Unexpected text: expected '%s', found '%s'" % (e, t))
        while True:
            el = len(expect)
            tl = len(text)
            #debug.show('el')
            #debug.show('expect')
            #debug.show('tl')
            #debug.show('text')
            if   el < tl:
                if expect == text[:el]:
                    self.push_part(line, el+strip_count)
                    break
                else:
                    fail(line, expect, text)
            elif tl < el:
                if expect[:tl] == text:
                    line, p = self.get_line()
                    text = line.txt
                    l = len(text)
                    text = text.strip()
                    strip_count = l - len(text)
                    expect = expect[tl:].lstrip()
                else:
                    fail(line, expect, text)
            else:                       # el == tl
                if expect[:tl] == text:
                    break
                else:
                    fail(line, expect, text)
        return True

    @dtrace
    def is_section_start(self, line, numlist=None, part=None):
        assert part != None
        if not line:
            return True
        text = line.txt
        if part == 'back':
            match = re.search(appendix_prefix, text)
            if match:
                text = text[len(match.group(0)):]
        return re.search('^%s([. ]|$)'%'.'.join(numlist), text) != None if numlist else re.search(section_start_re[part], text.lower()) != None

    @dtrace
    def read_author_name(self):
        line, p = self.get_line()
        if line is None:
            self.err(self.lines[-1].num, "Expected an author's name, found end of file")
        name = line.txt.strip()
        self.dpprint('self.authors')
        item = match_name(name, self.authors)
        if not item:
            item = {'fullname': name, }
            parts = name.split()
            item['surname'] = parts[-1]
            if len(parts) > 1:
                item['initials'] = ' '.join([ '%s.'%n[0] for n in parts[:-1] ])
            self.dpprint('item')
            self.authors.append(item)
        if item:
            item['fullname'] = name.replace(' (editor)','')
        return item

    @dtrace
    def maybe_author_org(self, item):
        line, p = self.get_line()
        if line is None:
            return None
        text = line.txt.strip()
        if text == '':
            self.push_line(line, p)
        
    @dtrace
    def maybe_author_address(self, item):
        address = []
        while True:
            line, p = self.get_line()
            if line is None:
                break
            text = line.txt.strip()
            if text == '' or text.split()[0] in address_details:
                self.push_line(line, p)
                break
            address.append(line.txt.strip())
        item['address'] = {}
        if address:
            item['address']['postal'] = address
        return item
        
    @dtrace
    def maybe_address_detail(self, item):
        line, p = self.get_line()
        if line is None:
            return None
        text = line.txt.strip()
        if text == '':
            self.push_line(line, p)
            return None
        try:
            label, value = text.split(None, 1)
        except ValueError:
            self.push_line(line, p)
            return None
        if label in address_details:
            key = address_details[label]
            item['address'][key] = value
        else:
            self.push_line(line, p)
            return None
        return item

    # ------------------------------------------------------------------------
    # middle
    # ------------------------------------------------------------------------
    @dtrace
    def middle(self):
        # section+
        middle = self.element('middle')
        self.section_number = 1
        while True:
            self.dsay('Get a regular middle section')
            section = self.section(numlist=[ str(self.section_number) ], part='middle')
            self.dshow('section')
            if section is None:
                break
            middle.append(section)
            self.section_number += 1

        while True:
            # other sections
            line = self.skip_blank_lines()
            word = line.txt.split()[0]
            if word.lower() in section_name_start['middle']:
                section = self.section([word], part='middle')
                #section.set('anchor', word.lower())
                #section.set('title', word)
                middle.append(section)
            else:
                break
        #

        return middle

    @dtrace
    def section(self, numlist=["1"], level=0, tag='section', appendix=False, part=None ):
        # (t | figure | texttable | iref)*, section*
        # figure out what a section number for this section is expected to
        # look like:
        #
        self.dpprint('numlist, level, tag, appendix, part')
        assert part != None
        section = None
        line, p = self.get_text_line()
        if line is None:
            return None
        # Expect the start of a section: section number and title
        number, title = parse_section_start(line, numlist, level, appendix)
        if self.is_section_start(line, numlist, part):
            if len(numlist) == 1 and title.lower() in section_names['refs']:
                self.push_line(line, p)
                return None
            if number.lower() in section_name_start[part]:
                title = line.txt
                number = ""
            # Get title continuation lines
            titleindent = line.txt.find(title)
            while True:
                next, p = self.get_line()
                if next.txt.strip() == '':
                    self.push_line(next, p)
                    break
                if indentation(next) == titleindent:
                    title += ' ' + next.txt.strip()
                else:
                    self.err(next.num, "Unexpected indentation: Expected a title continuation line with indentation %s, but got '%s'" % (titleindent, next.txt))
            section = self.element(tag, None)
            if tag == 'section':
                section.set('title', title)
                if number:
                    anchor = 'section-%s'%slugify(number.rstrip('.'))
                else:
                    anchor = '%s'%slugify(title)
                    section.set('numbered', 'no')
                section.set('anchor', anchor)
                self.section_anchors.append(anchor)
        else:
            if number.lower() in section_name_start['all']:
                self.push_line(line, p)
                return None
            else:
                self.err(line.num, "Unexpected section number; expected '%s' or a subsection, found '%s'" % ('.'.join(numlist), line.txt))
        #
        blank_line, p = self.get_line()
        if not blank_line.txt.strip() == '':
            self.warn(blank_line.num, "Unexpected text; expected a blank line after section title, found '%s'" % (blank_line, ))
            self.push_line(line, p)
        while True:
            paragraph = self.get_block(part)
            if paragraph is None:
                break
            else:
                section.append(paragraph)
        num = 0
        while True:
            # section*
            num += 1
            sublist = numlist + [ str(num) ]
            line, p = self.get_text_line()
            if not line:
                break
            if self.is_section_start(line, sublist, part):
                self.push_line(line, p)
                subsection = self.section(sublist, level+1, appendix=appendix, part=part)
                if subsection is None:
                    break
                else:
                    section.append(subsection)
            else:
                self.push_line(line, p)
                break

        return section


    @dtrace
    def get_block(self, part):
        """
        This method does not parse and return one specific element type;
        it encapsulates the (t | figure | texttable | iref) alternatives
        which occur in <section>.
        """
        self.dshow('part')
        tag2label = {
            'figure': 'Figure',
            'texttable': 'Table',
        }
        #
        ##self.skip_blank_lines()
        block = []
        # Collect related sections with embedded blank lines, like lists
        tag = None
        element = None
        ind = None
        while True:
            # collect one block worth of text
            para = self.get_para()
            if not para:
                return None
            line = para[0]
            this_ind = indentation(line)
            first = line.txt.strip()
            this_tag, text, linecount = self.identify_paragraph(para, part)
            #if not this_tag in ['t', 'figure', 'texttable', 'list', ]:
            if not this_tag in ['t', 'figure', 'texttable', 'list', 'code', ]:
                self.dsay('Break for %s (not part of <t>)' % this_tag)
                self.push_para(para)
                break
            if this_tag == 'code':
                this_tag = 'figure'
                while True:
                    block.append(para)
                    if '<CODE ENDS>' in text:
                        break
                    para = self.get_para()
                    text = para2text(para)
                break
            elif tag in ['figure', 'texttable']:
                expected = tag2label[tag]
                othertag = 'figure' if tag=='texttable' else 'texttable'
                unexpected = tag2label[othertag]
                if first.startswith(expected):
                    self.dsay('Break for label')
                    block.append(para)
                    break
                elif first.startswith(unexpected):
                    self.warn(para[0].num, "Unexpected title: expected '%s ...', found '%s'.  This looks like a %s that has been entered as a %s.  The generated XML will need adjustment." % (expected, first, tag, othertag))
                    block.append(para)
                    break
                elif linecount == 1 and (tag=='figure' or len(block) == 1) and not '  ' in first:
                    this_tag = tag
                elif tag and this_tag != tag:
                    self.dsay('Tag changed; push back para and break')
                    self.push_para(para)
                    break
            elif tag=='list' and this_tag=='t' and ind and this_ind > ind:
                self.dsay('new t para in list')
                block[-1] += para
                para = None
                this_tag = 'list'
            elif tag and this_tag != tag:
                self.dsay('Tag changed; push back para and break')
                self.push_para(para)
                break
            if para:
                block.append(para)
            #
            if not tag:
                tag = this_tag
            if not ind:
                ind = this_ind
            # break here unless this is a type with embedded blank lines:
            if not this_tag in ['figure', 'texttable', 'list', ]:
                self.dsay('Break for "%s"' % this_tag)
                break
            if tag in ['texttable'] and len(block) >= 2:
                self.dsay('Break for "%s" length %s' % (tag, len(block)))
                break
        if not tag:
            tag = this_tag
        self.dshow('tag')
        self.dpprint('block')
        if block and tag:
            self.dsay('Have block and tag')
            flat = flatten(block)
            text = '\n'+para2text(flat)
            if tag == 'list':
                for b in block:
                    if re.search(code_re, para2text(b)):
                        # in vocabulary v3 this will be 'sourcecode'
                        tag = 'figure'
                        block = [ flat ]
                        #debug.pprint('block')
                        break
            if tag in ['figure', 'texttable']:
                label = para2str(block[-1])
                if label.startswith(tag2label['figure']) or label.startswith(tag2label['texttable']):
                    block.pop()
                else:
                    label = None
            if tag == 't':
                ind = indentation(para[0])
                if ind != 3:
                    t = self.element('t', text)
                    l = self.element('list', style='hanging', hangIndent=str(ind-3))
                    l.append(t)
                    element = self.element('t')
                    element.append(l)
                else:
                    element = self.element('t', text)
            elif tag == 'list':
                element = self.element('t')
                element.append(self.make_list(block))
            elif tag == 'section':
                self.push_para(para)
            elif tag == 'texttable':
                element = self.make_table(block, label)
            elif tag == 'figure':
                element = self.make_figure(block, label)
        return element

    @dtrace
    def identify_paragraph(self, para, part):
        tag = None
        text = None

        linecount = 0
        if para and para[0].txt:
            line = para[0]
            text = para2text(para)
        if not text in self._identify_paragraph_cache:
            self.dpprint('para')
            # we want to distinguish between:
            # * figure
            # * list
            #   - numbers
            #   - letters
            #   - symbols
            #   - hanging
            #   - empty
            # * texttable
            #   - none      no borders
            #   - headers   border between headers and data, and beg/end
            #   - full      like headers + frame + vertical borders
            #   - all       like full + horizontal between data cells
            # * plain text, <t>
            if self.is_section_start(line, part=part):
                self.dsay('... section')
                tag = 'section'
            elif not line.txt.startswith('   '):
                self.dsay('... figure or None')
                if line.txt.startswith(' '):
                    tag = 'figure'
                else:
                    tag = None
            elif '<CODE BEGINS>' in text:
                self.dsay('... figure (code begins)')
                tag = 'code'
            else:
                indents = indentation_levels(para)
                border_set = set(table_borders(para))
                linecount = len(text.split('\n'))
                sym_ratio = symbol_ratio(text)
                if not '----' in text and (sym_ratio < 0.3 or (sym_ratio < 0.8 and linecount==1)):
                    self.dsay('... list, t, or figure')
                    self.dshow('sym_ratio')
                    self.dshow('linecount')
                    self.dshow('len(indents)')
                    next = self.next_line()
                    if re.search(code_re, line.txt):
                        self.dsay('... figure (matches code regex)')
                        tag = 'figure'
                    elif len(re.findall('\S   +\S', text)) > 2:
                        self.dsay('... figure (matches odd whitespace regex)')
                        tag = 'figure'
                    elif (
                        len(indents) > 1
                        or (linecount == 1 and line.txt.strip()[:2] in ['o ', '* ', '+ ', '- ', ]) 
                        or (linecount == 1 and re.search('^[0-9a-z][ivx]*\. ', line.txt.strip()))
                        or (next and indentation(next) > indentation(para[0]) and linecount == 1)
                        or ('  ' in line.txt.strip() and not '.  ' in line.txt.strip())
                        ):
                        self.dsay('... list (for some reason)')
                        tag = 'list'
                    else:
                        if (linecount > 1 and '  ' in line.txt.strip() and not '.  ' in line.txt.strip()):
                            self.warn(line.num, "Not marking this as a list: '%s'" % (line.txt, ))
                        # try to differentiate between plain text and code/figure, based on
                        # ratio between character count and line count
                        if linecount == 1:
                            self.dsay('... t (single line)')
                            tag = 't'
                        else:
                            width = 72-indents[0]
                            wrapped = textwrap.fill(text, width)
                            filled  = count_lines(wrapped, width)
                            actual = count_lines(text, width)
                            # change in last line length when filling
                            fill_change = (actual - filled)*width
                            # 15 is a somewhat arbitrary character count larger than a common
                            # word size and smaller than the regular line length
                            if fill_change > 15 and linecount > 1:
                                self.dsay('... figure (lines not properly filled)')
                                tag = 'figure'
                            else:
                                self.dsay('... t (lines reasonably filled)')
                                tag = 't'
                elif len(indents) > 1:
                    self.dsay('... figure (found several indentation levels)')
                    # uneven indentation; it's not a table (well, could
                    # be texttable with style none|headers and center or
                    # righ align on the first column, but we ignore that)
                    tag = 'figure'
                else:
                    if len(border_set) == 2 and not '+-+-+' in text and line.txt.strip() in border_set:
                        self.dsay('... texttable (found start border)')
                        tag = 'texttable'
                    else:
                        self.dsay('... figure (last remaining option)')
                        tag = 'figure'
            self._identify_paragraph_cache[text] = (tag, text, linecount)
        return self._identify_paragraph_cache[text]

    @dtrace
    def make_figure(self, block, title):
        figure = self.element('figure')
        if title and (title.startswith('Figure') or title.startswith('Table')):
            parts = title.split(None, 2)
            if len(parts) > 1:
                num = parts[1]
                num = num.replace(':','')
                ref = "%s-%s"%(parts[0].lower(),num)
                anchor = "ref-%s"%ref
            if len(parts) > 2:
                title = parts[2]
                figure.set('title', title)
                anchor = "ref-%s"%slugify(title)
            figure.set('anchor', anchor)
            self.figure_and_table_anchors[ref] = anchor
        text = para2text(flatten(block))
        artwork = self.element('artwork', CDATA('\n'+unindent(text, 3)+'\n'))
        figure.append(artwork)
        return figure

    @dtrace
    def make_table(self, block, title):
        self.dpprint('block')
        paragraph = block.pop(0)
        first_line = paragraph[0]
        # figure out the table characteristics
        borders = table_borders(paragraph)
        # styles:
        #   none:
        #       Foo  Bar  Baz
        #       One  2    Three
        #       Two  2    Four
        #
        #   headers:
        #       ---- ---- -----
        #       Foo  Bar  Baz
        #       ---- ---- -----
        #       One  2    Three
        #       Two  2    Four
        #
        #   full:
        #       +-----+-----+------+
        #       | Foo | Bar | Baz  |
        #       +-----+-----+------+
        #       | One | 2   | Three|
        #       | Two | 2   | Four |
        #       +-----+-----+------+
        #
        #   all:
        #       +-----+-----+------+
        #       | Foo | Bar | Baz  |
        #       +-----+-----+------+
        #       | One | 2   | Three|
        #       +-----+-----+------+
        #       | Two | 2   | Four |
        #       +-----+-----+------+
        #
        if   borders[0][0] == '-':
            style = 'headers'
        else:
            style = 'full'
        ## Ignore 'none' and 'all' for now
        # find a horizontal border
        for border in borders:
            if '-' in border:
                break
        # find a line with that border, and the table column start positions
        columns = None
        for line in paragraph:
            if border in line.txt:
                ind = line.txt.find(border)
                sep = '+' if '+' in border else ' '
                if sep == '+':
                    columns = line.txt.split(sep)[1:-1]
                else:
                    columns = border.split(sep)
                break
        if not columns:
            self.err(first_line.num, "Malformed table, expected table to start with a border, found '%s'"%(first_line.txt, ))
        colwidth = [ len(c)+1 for c in columns ]
        colpos = [ ind ]
        pos = ind
        for w in colwidth:
            pos += w
            colpos.append(pos)
        # --- Process the table, generate xml elements ---
        texttable = self.element('texttable')
        if title and (title.startswith('Table') or title.startswith('Figure')):
            parts = title.split(None, 2)
            if len(parts) > 1:
                num = parts[1]
                num = num.replace(':','')
                ref = "%s-%s"%(parts[0].lower(),num)
                anchor = "ref-%s"%ref
            if len(parts) > 2:
                title = parts[2]
                texttable.set('title', title)
                anchor = "ref-%s"%slugify(title)
            texttable.set('anchor', anchor)
            self.figure_and_table_anchors[ref] = anchor
        texttable.set('style', style)
        # skip top border
        line = paragraph.pop(0)
        assert border in line.txt
        # collect header text until next border
        headers = ['']*len(columns)
        while True:
            line = paragraph.pop(0)
            if border in line.txt:
                break
            txt = line.txt.replace('|', ' ')
            columns = colsplit(colpos, txt)
            headers = [ ' '.join(t) for t in zip(headers, columns) ]
        # generate <ttcol>
        for h in headers:
            ttcol = self.element('ttcol', h)
            texttable.append(ttcol)
        # collect table cells and generate <c>
        while paragraph:
            line = paragraph.pop(0)
            if border in line.txt:
                continue
            txt = line.txt.replace('|', ' ')
            columns = colsplit(colpos, txt)
            if any( t for t in columns ):
                for t in columns:
                    c = self.element('c', t)
                    texttable.append(c)
        if block:
            text = para2text(block.pop())
            postamble = self.element('postamble', text)
            texttable.append(postamble)
        assert block == []
        return texttable

    @dtrace
    def make_list(self, block, base_indentation=3, level=0):
        #list[style, hangIndent, counter] : t+
        # style = (numbers|letters|symbols|hanging|empty|format:...)
        # t[hangText] 
        #
        #indents = indentation_levels(flatten(block))
        #debug.show('len(indents)')
        #if len(indents) > 2:
        assert block != []
        #
        saved_pi = {}
        def set_subcompact(list, item):
            last = item[-1]
            k, v = ('subcompact', 'yes' if last.txt.strip() != '' else 'no')
            if not k in saved_pi:
                saved_pi[k] = self.pi[k]
            self.set_pi(list, k, v)
        #
        @dtrace
        def make_list_item_text(self, item):
            """
            Split a list of lines on blank lines, and build a sequence of
            <vspace/> elements to generate blank lines where needed.
            """
            self.dshow('item')
            para = []
            paras = []
            for line in item:
                if line.txt.strip() == '':
                    paras.append(para)
                    para = [ ]
                else:
                    para.append(line)
            paras.append(para)
            self.dshow('paras')
            text = para2text(paras.pop(0)) if paras else ''
            self.dshow('text')
            elements = []
            if paras and paras[-1] == []:
                paras.pop()
            for para in paras:
                vspace = self.element('vspace', blankLines="1")
                vspace.tail = space(para2text(para))
                self.dshow('vspace.tail')
                elements.append(vspace)
            return text, elements
        #
        items = self.normalize_list_block(block)
        #debug.pprint('items')
        indents = indentation_levels(flatten(block))
        list = self.element('list', style='empty')
        # Handle temporary processing instruction settings
        #
        item = items[0]
        self.dpprint('indentation_levels(item)')
        if indents[0] > base_indentation: # and (len(item) == 1 or len(indentation_levels(item)) > 2):
            # handle extra indentation by adding an extra level of <t/><list/>
            self.dsay('list wrapper for indentation')
            list.set('hangIndent', str(indents[0]-base_indentation))
            list.text = '\n\t'
            t = self.element('t')
            t.append(self.make_list(block, base_indentation=indents[0], level=level+1))
            list.append(t)
        else:
            t = None
            item = items[0]
            first = item[0]
            if not type(first) is type([]):
                set_subcompact(list, item)
            for i, item in enumerate(items):
                self.dpprint('item')
                if type(item[0]) is type([]):                # check for sublist
                    self.dsay('sublist')
                    assert t is not None
                    line = item[0][0]
                    t.append(self.make_list(item, base_indentation=indentation(line), level=level+1))
                else:
                    self.dsay('list item')
                    self.dshow('len(items)>(i+1)')
                    if len(items)>(i+1):
                        self.dshow('items[i+1]')
                        self.dshow('type(items[i+1][0])')
                    next = flatten(items[i+1]) if len(items)>(i+1) else None
                    next_indent = indentation(next[0]) if next else None
                    line = item[0]
                    item_indents = indentation_levels(item)
                    style, marker, ind, rest = guess_list_style(line)
                    self.dshow('style')
                    self.dshow('marker')
                    self.dshow('rest')
                    if style and i == 0:
                        self.dpprint('item_indents')
                        list.set('style', style)
                        if style == 'hanging':
                            if len(item_indents) > 1:
                                hang_indent = item_indents[1] - item_indents[0]
                            elif next and len(strip(item)) == 1:
                                hang_indent = next_indent - item_indents[0]
                            elif '  ' in line.txt.strip() and not '.  ' in line.txt and not '?  ' in line.txt:
                                hang_indent = self.get_tabstop(line)
                            else:
                                hang_indent = 0
                            if hang_indent == 0:
                                # work around bug in xml2rfc:
                                hang_indent = -1
                            list.set('hangIndent', str(hang_indent))
                        elif style == 'symbols':
                            self.set_symbols_pi(marker, level)
                    if style == 'hanging':
                        self.dsay('hanging')
                        if item_indents[0] == indents[0]:
                            self.dsay('same indentation')
                            t = self.element('t', space(rest))
                            t.set('hangText', marker)
                            vspace = self.element('vspace', blankLines="0")
                            t.append(vspace)
                            #
                            if len(item) > 1:
                                text, elements = make_list_item_text(self, item[1:])
                                vspace.tail = space(text)
                                for e in elements:
                                    t.append(e)
                            list.append(t)
                        else:
                            text, elements = make_list_item_text(self, item)
                            t = self.element('t', text)
                            for e in elements:
                                t.append(e)
                            list.append(t)
                    elif style == None:
                        text, elements = make_list_item_text(self, item)
                        t = self.element('t', text)
                        for e in elements:
                            t.append(e)
                        list.append(t)
                    else:
                        text, elements = make_list_item_text(self, [ Line(item[0].num, rest) ]+item[1:])
                        t = self.element('t', text)
                        for e in elements:
                            t.append(e)
                        list.append(t)
            for k,v in saved_pi.items():
                self.set_pi(list, k, v)
        return list

    @dtrace
    def normalize_list_block(self, block):
        "Join and split items as needed, to produce one item per list item."
        #debug.pprint('block')
        assert type(block) is list and all([type(b) is list for b in block]) and all([ type(l) is Line for b in block for l in b ])
        if self.options.debug:
            orig = copy.deepcopy(block)
        items = []
        widow = []                          # candidate for merge with following blocks
        #debug.pprint('0, block')
        for b in block:
            s = strip(b)
            #debug.pprint('b')
            #debug.pprint('s')
            if widow:
                sw, mw, iw, __ = guess_list_style(widow[0])
                sb, mb, ib, __ = guess_list_style(s[0])
                if ib > iw:
                    if sb in [None, 'hanging']:
                        widow += b
                        items.append(widow)
                        widow = []
                    else:
                        items.append(widow)
                        widow = []
                        items.append(b)
                elif ib == iw:
                    items.append(widow)
                    widow = copy.copy(b)
                else:
                    items.append(widow)
                    widow = []
                    items.append(b)
            else:
                if len(s) == 1:
                    widow = copy.copy(b)
                else:
                    items += self.split_at_sublist_end(b)
        if widow:
            items.append(widow)
        items = self.normalize_sublists(items)
        items = self.split_compact_lists(items)
        if self.options.debug:
            assert block == orig
        return items

    @dtrace
    def split_at_sublist_end(self, block):
        "Split a block if it contains a transition to a lower indentation level"
        #debug.pprint('block')
        assert type(block) is list and type(block[0]) is Line
        if self.options.debug:
            orig = copy.deepcopy(block)
        item = []
        items = []
        i0 = 0
        for line in block:
            s, m, i, __ = guess_list_style(line)
            if line.txt.strip() and i < i0:
                items.append(item)
                item = [ line ]
    #         elif line.txt.strip() and i0 and i > i0 and s != s0:
    #             items.append(item)
    #             item = [ line ]
            else:
                item.append(line)
            i0 = i
        if item:
            items.append(item)
        if self.options.debug:
            assert block == orig
        return items

    @dtrace
    def normalize_sublists(self, block):
        """
        If a list block seems to contain a sublist, split that out and
        replace it with one sublist block.
        """
        #debug.pprint('block')
        assert type(block) is list and all([type(b) is list for b in block]) and all([ type(l) is Line for b in block for l in b ])
        if self.options.debug:
            orig = copy.deepcopy(block)
        sub = []
        items = []
        line = block[0][0]
        style, marker, ind, __ = guess_list_style(line)
        # first, separate out blocks with different indentations
        for b in block:
            line = b[0]
            s, m, i, __ = guess_list_style(line)
            if i == ind and s == style:
                if sub:
                    items.append(sub)
                    sub = []
                items.append(b)
            else:
                sub.append(b)
        if sub:
            items.append(sub)
            sub = []
        #
        temp = copy.deepcopy(items)
        items = []
        # then see if a block contains a sublist, and split that off
        for b in temp:
            #debug.pprint('b')
            if isinstance(b[0], list):
                items.append(b)
                continue
            indents = indentation_levels(b)
            if len(indents) > 1:
                s0, m0, i0, __ = guess_list_style(b[0])
                for i, l in enumerate(b):
                    if indentation(l) != indents[0]:
                        s1, m1, i1, __ = guess_list_style(l)
                        break
                if s1 in ['numbers', 'letters', 'symbols', ]:
                    #debug.show('i, l')
                    #debug.show('s1, m1')
                    items.append(b[:i])
                    items.append([ b[i:] ])
                else:
                    items.append(b[:])
            else:
                items.append(b[:])
#        if self.options.debug and orig != temp:
#            self.dpprint('orig')
#            self.dpprint('temp')
        if temp != items:
            self.dpprint('temp')
            self.dpprint('items')
        if self.options.debug:
            assert block == orig
        return items

    @dtrace
    def split_compact_lists(self, block):
        items = []
        #debug.pprint('block')
        if self.options.debug:
            orig = copy.deepcopy(block)
        for b in block:
            if type(b[0]) is list:
                items.append(self.split_compact_lists(b))
            else:
                assert type(b[0]) == Line
                item = []
                line0 = b[0]
                style0, mark0, ind0, __ = guess_list_style(line0)
                if style0 in ['numbers', 'letters', 'symbols', ]:
                    for line in b:
                        if line.txt.strip() == '':
                            item.append(line)
                            continue
                        style, mark, ind, __ = guess_list_style(line)
                        if ind == ind0 and style == style0:
                            if item:
                                items.append(item)
                                item = []
                            item.append(line)
                        elif ind > ind0:
                            if style in ['numbers', 'letters', 'symbols', ]:
                                self.warn(line.num, "Found unexpected sublist to a compact list: '%s'" % (line.txt, ))
                                if item:
                                    items.append(item)
                                    item = []
                                item.append(line)
                            else:
                                item.append(line)
                        elif ind == ind0 and style != style0:
                            self.warn(line.num, "Found unexpected list style change: expected style %s, found '%s'" % (style0, line.txt))
                            if item:
                                items.append(item)
                                item = []
                            item.append(line)
                        else:
                            self.warn(line.num, "Found unexpected inentation change: worked on '%s', found '%s'" % (line0.txt, line.txt))
                            if item:
                                items.append(item)
                                item = []
                            item.append(line)
                    if item:
                        items.append(item)
                        item = []
                else:
                    items.append(b)
        if items != block:
            self.dsay('** items changed **')
            #debug.pprint('block')
            self.dpprint('items')
        if self.options.debug:
            assert block == orig
        return items





    # ------------------------------------------------------------------------
    # back
    # ------------------------------------------------------------------------
    @dtrace
    def back(self):
        back = self.element('back')

        num = ord('A')
        prev = None
        while True:
            line = self.skip_blank_lines()
            if not line:
                break
            if line == prev:
                # we didn't process this and following lines on the previous round, so bail out
                self.err(line.num, "Expected a back section, found '%s'" % (line.txt))
            if self.is_section_start(line, part='refs'):
                self.dsay('Reference section: %s' % line.txt)
                while True:
                    references = self.references([ str(self.section_number) ])
                    if references is None:
                        break
                    for refs in references:
                        back.append(refs)
                    self.section_number += 1
            elif self.is_section_start(line, part='back'):
                self.dsay('Back section: %s' % line.txt)
                word = line.txt.split()[0]
                if line.txt.strip().lower().startswith('author'):
                    self.dsay("Authors' Addresses")
                    self.read_authors_addresses()
                elif word.lower() == 'appendix':
                    self.dsay("Appendix")
                    section = self.section(numlist=[ chr(num) ], appendix=True, part='back')
                    if not section is None:
                        back.append(section)
                        num += 1
                else:
                    self.dsay('Section: %s'%word)
                    section = self.section([word], part='back')
                    if not section is None:
                        back.append(section)
            else:
                self.warn(line.num, "Expected a back section, found '%s'" % (line.txt))
                break
            prev = line
        return back

    @dtrace
    def references(self, numlist, level=0):
        refs = []
        # peek at the first nonblank line
        line, p = self.get_text_line()
        if self.is_section_start(line, numlist, part='refs') is None:
            self.push_line(line, p)
            return None
        #
        number, title = parse_section_start(line, numlist, level, appendix=False)
        if not title in ['References', 'Normative References', 'Informative References', 'Informational References', 'Normative', 'Informative', 'URIs', ]:
            self.push_line(line, p)
            return None
        # peek at the next nonblank line
        line = self.skip_blank_lines()
        if self.is_section_start(line, part='refs'):
            num = 1
            while True:
                sublist = numlist + [ str(num) ]
                references = self.references(sublist, level+1)
                if references is None:
                    break
                refs += references
                num += 1
            return refs
        else:
            references = self.element('references', title=title)
            refs.append(references)
            # a series of reference entries
            while True:
                ref, entity = self.reference()
                if ref is None:
                    break
                if entity is None:
                    references.append(ref)
                else:
                    references.append(entity)
            return refs
        return None

    @dtrace
    def reference(self):
        entity = None
        line = self.skip_blank_lines()
        if self.is_section_start(line, part='refs') or self.is_section_start(line, part='back'):
            return None, None
        reference = self.element('reference')
        front = self.element('front')
        reference.append(front)
        para = self.get_para()
        line = para[0]
        if not para:
            return None, None
        text = para2str(para)
        self.dshow('text')
        faild = None
        for regex in reference_patterns:
            match = re.search(regex, text)
            if match:
                if faild:
                    self.dshow('faild')
                    self.dshow('regex')
                    self.dpprint('match.groupdict()')
                #
                refinfo = match.groupdict()
                # Attributes
                anchor = refinfo.get('anchor')
                if anchor:
                    if anchor.isdigit():
                        anchor = "ref-%s" % anchor
                        refinfo['anchor'] = anchor
                    reference.set('anchor', anchor)
                    self.reference_anchors.append(anchor)
                target = refinfo.get('target')
                if target:
                    reference.set('target', target)
                # Front matter
                key = 'title'
                value = refinfo.get(key)
                if value:
                    e = self.element(key, value)
                else:
                    e = self.element(key)
                front.append(e)
                # Author info
                if 'authors' in refinfo:
                    authors = refinfo.get('authors')
                    if authors:
                        ed = ', Ed.'
                        if ' and ' in authors:
                            first, last = authors.split(' and ', 1)
                        else:
                            first, last = authors, None
                        for author in re.findall(ref_name_re, first):
                            editor = author.endswith(ed)
                            if editor:
                                author = author[:-len(ed)]
                            surname, initials = [ n.strip() for n in author.split(', ', 1) ]
                            e = self.element('author', initials=initials, surname=surname, fullname=' '.join([initials, surname]))
                            if editor:
                                e.set('role', 'editor')
                            front.append(e)
                        if last:
                            author = last
                            editor = author.endswith(ed)
                            if editor:
                                author = author[:-len(ed)]
                            initials, surname = [ n.strip() for n in author.split(None, 1) ]
                            e = self.element('author', initials=initials, surname=surname, fullname=' '.join([initials, surname]))
                            if editor:
                                e.set('role', 'editor')
                            front.append(e)
                elif 'organization' in refinfo:
                    organization = refinfo.get('organization')
                    e = self.element('author')
                    org = self.element('organization', organization)
                    e.append(org)
                    front.append(e)
                else:
                    e = self.element('author')
                    front.append(e)
                key = 'date'
                value = refinfo.get(key)
                if value:
                    if ' ' in value:
                        month, year = value.split(None, 1)
                        e = self.element(key, month=month, year=year)
                    else:
                        e = self.element(key, year=value)                        
                else:
                    e = self.element(key)
                front.append(e)
                # Document / Series
                if 'series' in refinfo:
                    series  = refinfo.get('series')
                    if series:
                        ename = None
                        for item in re.findall(ref_series_one, series):
                            self.dshow('item')
                            parts = item.split(None, 1)
                            if len(parts) == 1:
                                if item.startswith('draft-'):
                                    item = item.split(' ')[0].split(',')[0]
                                    name, value = 'Internet-Draft', item
                                else:
                                    name, value = '(Unknown)', item
                            else:
                                if item.startswith('draft-'):
                                    item = parts[0].split(' ')[0].split(',')[0]
                                    name, value = 'Internet-Draft', item
                                else:
                                    name, value = parts
                            self.dshow('name')
                            self.dshow('value')
                            e = self.element('seriesInfo', name=name, value=value)
                            reference.append(e)
                            if name == 'RFC':
                                anchor = refinfo.get('anchor')
                                ename  = 'RFC%04d'%int(value)
                                if anchor == ename:
                                    entity = Entity(ename)
                                    entity.tail = '\n\t'
                                self.entities.append({'name': ename,
                                    'url': 'https://xml2rfc.ietf.org/public/rfc/bibxml/reference.RFC.%04d.xml'%int(value), })
                            if name == 'Internet-Draft':
                                anchor = refinfo.get('anchor')
                                if (   anchor == 'I-D.%s'%value
                                    or anchor == 'I-D.%s'%value[len('draft-'):]
                                    or anchor == 'I-D.%s'%value[:-3]
                                    or anchor == 'I-D.%s'%value[len('draft-'):-3] ):
                                    ename = anchor
                                else: 
                                    ename = 'I-D.%s'%value[len('draft-'):]
                                    if ename[-3] == '-' and ename[-2:].isdigit():
                                        ename = ename[:-3]
                                if anchor == ename:
                                    entity = Entity(ename)
                                    entity.tail = '\n\t'
                                self.entities.append({'name': ename,
                                    'url': 'https://xml2rfc.ietf.org/public/rfc/bibxml3/reference.I-D.%s.xml'%value, })
                            reference.append(e)
                elif 'docname' in refinfo:
                    docname = refinfo.get('docname')
                    if docname:
                        name, value = docname.split(None, 1)
                        e = self.element('seriesInfo', name=name, value=value)
                        reference.append(e)
                #
                break
            else:
                faild = regex
        else:
            if not line or self.is_section_start(line, part='back'):
                self.push_para(para)
                return None, None
            else:
                self.warn(line.num, "Failed parsing a reference:\n%s" % para2text(para))
                return reference, entity

        return reference, entity

    # ------------------------------------------------------------------------
    # postprocess
    # ------------------------------------------------------------------------

    def postprocess(self):
        self.add_text_refs()
        self.update_symrefs_pi()
        self.update_sortrefs_pi()
        self.update_symbols_pi()

    def add_text_refs(self):
        """
        Iterate through all <t> elements, and if they have .text, process
        that to generate a new <t> element with <xref>s and <eref>s.
        """
        self.section_anchors = [ r.get('anchor') for r  in self.root.findall('.//section') ]
        for old in self.root.findall('.//t'):
            if old.text:
                new = TextParser(self, old.text).parse_text()
                for key in old.keys():
                    value = old.get(key)
                    new.set(key, value)
                for child in old:
                    new.append(child)
                old.getparent().replace(old, new)
        for vspace in self.root.findall('.//vspace'):
            if vspace.tail:
                tmp = TextParser(self, vspace.tail).parse_text()
                vspace.tail = tmp.text
                t = vspace.getparent()
                i = t.index(vspace)
                for child in tmp:
                    t.insert(i+1, child)
                    i += 1

    def update_symrefs_pi(self):
        if not hasattr(self, 'reference_anchors'):
            self.err(0, "Internal error: set_symref_pi() called without reference_anchors having been set")
        symrefs = "no"
        for anchor in self.reference_anchors:
            if anchor and not re.search('^ref-\d+$', anchor):
                symrefs = "yes"
        self.pi['symrefs'] = symrefs
        pi = ProcessingInstruction('rfc', 'symrefs="%s"'%symrefs)
        pi.tail = '\n\t'
        self.root.replace(self.symrefs_pi, pi)

    def update_sortrefs_pi(self):
        if not hasattr(self, 'reference_anchors'):
            self.err(0, "Internal error: set_symref_pi() called without reference_anchors having been set")
        sortrefs = "yes"
        prev = None
        for anchor in self.reference_anchors:
            if prev and anchor.startswith('RFC') and len(anchor) > 6 and anchor < prev:
                sortrefs = "no"
                break
            prev = anchor
        self.pi['sortrefs'] = sortrefs
        pi = ProcessingInstruction('rfc', 'sortrefs="%s"'%sortrefs)
        pi.tail = '\n\t'
        self.root.replace(self.sortrefs_pi, pi)

    def update_symbols_pi(self):
        symbols = list(self.pi['text-list-symbols'].rstrip())
        for s in "o*+-":
            if not s in symbols:
                if ' ' in symbols:
                    for i, sym in enumerate(symbols):
                        if sym == ' ':
                            symbols[i] = s
                            break
                else:
                    symbols.append(s)
        self.pi['text-list-symbols'] = ''.join(symbols)
        pi = ProcessingInstruction('rfc', 'text-list-symbols="%s"'%self.pi['text-list-symbols'])
        pi.tail = '\n\t'
        self.root.replace(self.symbols_pi, pi)
