#!/usr/bin/python
# Copyright The IETF Trust 2009-2022, All Rights Reserved
# -*- coding: utf-8 -*-
# -*- python -*-


"""
NAME
        %(program)s - Extract meta-information from an IETF draft.

SYNOPSIS
        %(program)s [OPTIONS] DRAFTLIST_FILE

DESCRIPTION
        Extract information about authors' names and email addresses,
        intended status and number of pages from Internet-Drafts.
        The information is emitted in the form of a line containing
        xml-style attributes, prefixed with the name of the draft.

%(options)s

AUTHOR
        Written by Henrik Levkowetz, <henrik@levkowetz.com>

COPYRIGHT
        Copyright 2008 Henrik Levkowetz

        This program is free software; you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation; either version 2 of the License, or (at
        your option) any later version. There is NO WARRANTY; not even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
        PURPOSE. See the GNU General Public License for more details.

"""



import debug     # pyflakes: ignore

import datetime
import getopt
import io
import os
import os.path
import re
import stat
import sys
import time

from typing import Dict, List       # pyflakes:ignore

from .timezone import date_today


version = "0.35"
program = os.path.basename(sys.argv[0])
progdir = os.path.dirname(sys.argv[0])

# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------


opt_debug = False
opt_timestamp = False
opt_trace = False
opt_authorinfo = False
opt_attributes = False
# Don't forget to add the option variable to the globals list in _main below


# The following is an alias list for short forms which starts with a
# different letter than the long form.

longform = {
    "Beth": "Elizabeth",
    "Bill": "William",
    "Bob": "Robert",
    "Dick": "Richard",
    "Fred": "Alfred",
    "Jerry": "Gerald",
    "Liz": "Elizabeth",
    "Lynn": "Carolyn",
    "Ned": "Edward",
    "Ted":"Edward",
}
longform = dict([ (short+" ", longform[short]+" ") for short in longform ])


month_names = [ 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december' ]
month_names_abbrev3 = [ n[:3] for n in month_names ]
month_names_abbrev4 = [ n[:4] for n in month_names ]

# ----------------------------------------------------------------------
# Functions
# ----------------------------------------------------------------------
def _debug(string):
    if opt_debug:
        sys.stderr.write("%s\n" % (string))

# ----------------------------------------------------------------------
def _note(string):
    sys.stdout.write("%s: %s\n" % (program, string))
    
# ----------------------------------------------------------------------
def _warn(string):
    sys.stderr.write("%s: Warning: %s\n" % (program, string))
    
# ----------------------------------------------------------------------
def _err(string):
    sys.stderr.write("%s: Error: %s\n" % (program, string))
    sys.exit(1)

# ----------------------------------------------------------------------
def _gettext(file):
    file = io.open(file)
    text = file.read()
    file.close()

    text = re.sub(".\x08", "", text)    # Get rid of inkribbon backspace-emphasis
    text = text.replace("\r\n", "\n")   # Convert DOS to unix
    text = text.replace("\r", "\n")     # Convert MAC to unix
    text = text.expandtabs()
    text = text.strip()

    return text

def acronym_match(s, l):
    acronym = re.sub("[^A-Z]", "", l)
    #_debug(" s:%s; l:%s => %s; %s" % (s, l, acronym, s==acronym)) 
    return s == acronym

def get_status_from_draft_text(text):

    # Take prefix to shortcut work over very large drafts
    # 5000 is conservatively much more than a full page of characters and we
    # only want the first 10 lines.
    text = text.strip()[:5000] # Take prefix to shortcut work over very large drafts 
    text = re.sub(".\x08", "", text)    # Get rid of inkribbon backspace-emphasis
    text = text.replace("\r\n", "\n")   # Convert DOS to unix
    text = text.replace("\r", "\n")     # Convert MAC to unix
    lines = text.split("\n")[:10]
    status = None
    for line in lines:
        status_match = re.search(r"^\s*Intended [Ss]tatus:\s*(.*?)   ", line)
        if status_match:
            status = status_match.group(1)
            break
    return status

class Draft:
    """Base class for drafts

    Extracted from PlaintextDraft, formerly named Draft. If I missed part of its public interface
    that is relevant for other draft formats, those should be added to this base class.
    """
    REF_TYPE_NORMATIVE = 'norm'
    REF_TYPE_INFORMATIVE = 'info'
    REF_TYPE_UNKNOWN = 'unk'

    def get_abstract(self):
        raise NotImplementedError

    def get_author_list(self):
        """Get detailed author list

        Returns a list of dicts with the following keys:
            full_name, first_name, middle_initial, last_name,
            name_suffix, email, country, company
        Values will be None if not available
        """
        raise NotImplementedError

    def get_authors(self):
        """Get simple author list

        Get as list of strings with author name and email within angle brackets
        """
        raise NotImplementedError

    def get_authors_with_firm(self):
        """Get simple list of authors with firm (company) info

        Get as list of strings with author name and email within angle brackets and
        company in parentheses
        """
        raise NotImplementedError

    def get_creation_date(self):
        raise NotImplementedError

    def get_formal_languages(self):
        raise NotImplementedError

    def get_pagecount(self):
        raise NotImplementedError

    def get_refs(self):
        raise NotImplementedError

    def get_status(self):
        raise NotImplementedError

    def get_title(self):
        raise NotImplementedError

    def get_wordcount(self):
        raise NotImplementedError
    
# ----------------------------------------------------------------------

class PlaintextDraft(Draft):

    def __init__(self, text, source, name_from_source=False):
        """Initialize a Draft instance

        :param text: plaintext draft contents
        :param source: name of file containing the contents
        :param name_from_source: if True, fall back to source to determine draft name not found from text
        """
        super().__init__()
        assert isinstance(text, str)
        self.source = str(source)
        self.rawtext = text
        self.name_from_source = name_from_source

        text = re.sub(".\x08", "", text)    # Get rid of inkribbon backspace-emphasis
        text = text.replace("\r\n", "\n")   # Convert DOS to unix
        text = text.replace("\r", "\n")     # Convert MAC to unix
        text = text.strip()
        self.text = text
        self.errors = {}

        self.rawlines = self.text.split("\n")
        self.lines, self.pages = self._stripheaders()
        # Some things (such as the filename) has to be on the first page.  If
        # we didn't get back a set of pages, only one single page with the
        # whole document, then we need to do an enforced page split in order
        # to limit later searches to the first page.
        if len(self.pages) <= 1:
            self.pages = []
            for pagestart in range(0, len(self.lines), 56):
                self.pages += [ "\n".join(self.lines[pagestart:pagestart+56]) ]


        self.filename, self.revision = self._parse_draftname()

        self._authors = None
        self._authors_with_firm = None
        self._author_info = None
        self._abstract = None
        self._pagecount = None
        self._status = None
        self._creation_date = None
        self._title = None

    @classmethod
    def from_file(cls, source, *args, **kwargs):
        with open(source, 'r', encoding='utf8') as f:
            return cls(text=f.read(), source=source, *args, **kwargs)

    # ------------------------------------------------------------------
    def _parse_draftname(self):
        draftname_regex = r"(draft-[a-z0-9-]*)-(\d\d)(\w|\.txt|\n|$)"
        draftname_match = re.search(draftname_regex, self.pages[0])
        if not draftname_match and self.name_from_source:
            draftname_match = re.search(draftname_regex, self.source)
        rfcnum_regex = r"(Re[qg]uests? [Ff]or Commm?ents?:? +|Request for Comments: RFC |RFC-|RFC )((# ?)?[0-9]+)( |,|\n|$)"
        rfcnum_match = re.search(rfcnum_regex, self.pages[0])
        if not rfcnum_match and self.name_from_source:
            rfcnum_match = re.search(rfcnum_regex, self.source)
        if draftname_match:
            return (draftname_match.group(1), draftname_match.group(2) )
        elif rfcnum_match:
            return ("rfc"+rfcnum_match.group(2), "")
        else:
            self.errors["draftname"] = "Could not find the draft name and revision on the first page."
            filename = ""
            revision = ""
            try:
                __, base = self.source.rsplit("/", 1)
            except ValueError:
                base = self.source
            if base.startswith("draft-"):
                if '.' in base:
                    name, __ = base.split(".", 1)
                else:
                    name = base
                revmatch = re.search(r"\d\d$", name)
                if revmatch:
                    filename = name[:-3]
                    revision = name[-2:]
                else:
                    filename = name
            return filename, revision

    # ----------------------------------------------------------------------
    def _stripheaders(self):
        stripped = []
        pages = []
        page = []
        line = ""
        newpage = False
        sentence = False
        shortprev = False
        blankcount = 0
        linecount = 0
        # two functions with side effects
        def striplines(p):
            beg = end = 0
            for i in range(len(p)):
                l = p[i]
                if l.strip() == "":
                    continue
                else:
                    beg = i
                    break
            for i in range(len(p)-1,0,-1):
                l = p[i]
                if l.strip() == "":
                    continue
                else:
                    end = i
                    break
            return p[beg:end]
        def endpage(pages, page, newpage, line):
            if line:
                page += [ line ]
            return begpage(pages, page, newpage)
        def begpage(pages, page, newpage, line=None):
            if page and len(striplines(page)) > 5:
                pages += [ "\n".join(page) ]
                page = []
                newpage = True
            if line:
                page += [ line ]
            return pages, page, newpage
        for line in self.rawlines:
            linecount += 1
            line = line.rstrip()
            if re.search(r"\[?page [0-9ivx]+\]?[ \t\f]*$", line, re.I):
                pages, page, newpage = endpage(pages, page, newpage, line)
                continue
            if re.search(r"\f", line, re.I):
                pages, page, newpage = begpage(pages, page, newpage)
                continue
            if re.search(r"^ *Internet.Draft.+  .+[12][0-9][0-9][0-9] *$", line, re.I):
                pages, page, newpage = begpage(pages, page, newpage, line)
                continue
    #        if re.search("^ *Internet.Draft  +", line, re.I):
    #            newpage = True
    #            continue
            if re.search(r"^ *Draft.+[12][0-9][0-9][0-9] *$", line, re.I):
                pages, page, newpage = begpage(pages, page, newpage, line)
                continue
            if re.search(r"^RFC[ -]?[0-9]+.*(  +)[12][0-9][0-9][0-9]$", line, re.I):
                pages, page, newpage = begpage(pages, page, newpage, line)
                continue
            if re.search(r"^draft-[-a-z0-9_.]+.*[0-9][0-9][0-9][0-9]$", line, re.I):
                pages, page, newpage = endpage(pages, page, newpage, line)
                continue
            if linecount > 15 and re.search(r".{58,}(Jan|Feb|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|Sep|Oct|Nov|Dec) (19[89][0-9]|20[0-9][0-9]) *$", line, re.I):
                pages, page, newpage = begpage(pages, page, newpage, line)
                continue
            if newpage and re.search(r"^ *draft-[-a-z0-9_.]+ *$", line, re.I):
                pages, page, newpage = begpage(pages, page, newpage, line)
                continue
            if re.search(r"^[^ \t]+", line):
                sentence = True
            if re.search(r"[^ \t]", line):
                if newpage:
                    # 36 is a somewhat arbitrary count for a 'short' line
                    shortthis = len(line.strip()) < 36 # 36 is a somewhat arbitrary count for a 'short' line
                    if sentence or (shortprev and not shortthis):
                        stripped += [""]
                else:
                    if blankcount:
                        stripped += [""]*blankcount
                blankcount = 0
                sentence = False
                newpage = False
                shortprev = len(line.strip()) < 36 # 36 is a somewhat arbitrary count for a 'short' line
            if re.search("[.:]$", line):
                sentence = True
            if re.search("^[ \t]*$", line):
                blankcount += 1
                page += [ line ]
                continue
            page += [ line ]
            stripped += [ line ]
        pages, page, newpage = begpage(pages, page, newpage)
        _debug('pages: %s' % len(pages))
        return stripped, pages

    # ----------------------------------------------------------------------
    def get_pagecount(self):
        if self._pagecount == None:
            label_pages = len(re.findall(r"\[page [0-9ixldv]+\]", self.text, re.I))
            count_pages = len(self.pages)
            if label_pages > count_pages/2:
                self._pagecount = label_pages
            else:
                self._pagecount = count_pages
        return self._pagecount

    # ------------------------------------------------------------------
    def get_wordcount(self):
        count = 0
        # match any sequence of non-white-space characters like the Unix command "wc"
        word_re = re.compile(r'\S+', re.UNICODE)
        for l in self.lines:
            count += sum(1 for _ in word_re.finditer(l))
        return count

    # ------------------------------------------------------------------
    def get_formal_languages(self):
        language_regexps = [
            ("abnf", [re.compile(r"\bABNF"), re.compile(r" +[a-zA-Z][a-zA-Z0-9_-]* +=[/ ]")]),
            ("asn1", [re.compile(r'DEFINITIONS +::= +BEGIN')]),
            ("cbor", [re.compile(r'\b(?:CBOR|CDDL)\b'), re.compile(r" +[a-zA-Z][a-zA-Z0-9_-]* += +[\{\[\(]")]),
            ("ccode", [re.compile(r"(?:\+\+\))|(?:for \(i)|(?: [!=]= 0\) \{)|(?: struct [a-zA-Z_0-9]+ \{)")]),
            ("json", [re.compile(r'\bJSON\b'), re.compile(r" \"[^\"]+\" ?: [a-zA-Z0-9\.\"\{\[]")]),
            ("xml", [re.compile(r"<\?xml")]),
        ]
        already_matched = set()
        for l in self.lines:
            for lang_name, patterns in language_regexps:
                for p in patterns:
                    if p not in already_matched and p.search(l):
                        already_matched.add(p)
        return [
            lang_name
            for lang_name, patterns in language_regexps
            if all(p in already_matched for p in patterns)
        ]

    # ----------------------------------------------------------------------
    def get_status(self):
        if self._status == None:
            for line in self.lines[:10]:
                status_match = re.search(r"^\s*Intended [Ss]tatus:\s*(.*?)   ", line)
                if status_match:
                    self._status = status_match.group(1)
                    break
        return self._status

    # ------------------------------------------------------------------
    def get_creation_date(self):
        if self._creation_date:
            return self._creation_date
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

        dates = []
        text = self.pages[0]
        for regex in date_regexes:
            match = re.search(regex, text, re.MULTILINE)
            if match:
                start = match.start()
                if not "expires" in text[start-10:start].lower():
                    dates += [(start, match)]
        dates.sort()
        for start, match in dates:
                md = match.groupdict()
                mon = md['month'].lower()
                day = int( md.get( 'day', 0 ) )
                year = int( md['year'] )
                try:
                    if   mon in month_names:
                        month = month_names.index( mon ) + 1
                    elif mon in month_names_abbrev3:
                        month = month_names_abbrev3.index( mon ) + 1
                    elif mon in month_names_abbrev4:
                        month = month_names_abbrev4.index( mon ) + 1
                    elif mon.isdigit() and int(mon) in range(1,13):
                        month = int(mon)
                    else:
                        continue
                    today = date_today()
                    if day==0:
                        # if the date was given with only month and year, use
                        # today's date if month and year is today's month and
                        # year, otherwise pick the middle of the month.
                        # Don't use today's day for month and year in the past
                        if month==today.month and year==today.year:
                            day = today.day
                        else:
                            day = 15
                    self._creation_date = datetime.date(year, month, day)
                    return self._creation_date
                except ValueError:
                    # mon abbreviation not in _MONTH_NAMES
                    # or month or day out of range
                    pass
        self.errors['creation_date'] = 'Creation Date field is empty or the creation date is not in a proper format.'
        return self._creation_date


    # ------------------------------------------------------------------
    def get_abstract(self):
        if self._abstract:
            return self._abstract
        abstract_re = re.compile(r'^(\s*)abstract', re.I)
        header_re = re.compile(r"^(\s*)([0-9]+\.? |Appendix|Status of|Table of|Full Copyright|Copyright|Intellectual Property|Acknowled|Author|Index|Disclaimer).*", re.I)
        begin = False
        abstract = []
        abstract_indent = 0
        look_for_header = False
        for line in self.lines:
            if not begin:
                if abstract_re.match(line):
                    begin=True
                    abstract_indent = len(abstract_re.match(line).group(0))
                continue
            if begin:
                if not line and not abstract:
                    continue
                if not line:
                    look_for_header=True
                    abstract.append(line)
                    continue
                if look_for_header and header_re.match(line):
                    break
                look_for_header = False
                abstract.append(line)
        abstract = '\n'.join(abstract)
        abstract = self._clean_abstract(abstract)
        self._abstract = self._check_abstract_indent(abstract, abstract_indent)
        return self._abstract


    def _check_abstract_indent(self, abstract, indent):
        indentation_re = re.compile(r'^(\s)*')
        indent_lines = []
        for line in abstract.split('\n'):
            if line:
                indent = len(indentation_re.match(line).group(0))
                indent_lines.append(indent)
        percents = {}
        total = float(len(indent_lines))
        formatted = False
        for indent in set(indent_lines):
            count = indent_lines.count(indent)/total
            percents[indent] = count
            if count > 0.9:
                formatted = True
        if not formatted:
            return abstract
        new_abstract = []
        for line in abstract.split('\n'):
            if line:
                indent = len(indentation_re.match(line).group(0))
                if percents[indent] < 0.9:
                    break
            new_abstract.append(line)
        return '\n'.join(new_abstract)


    def _clean_abstract(self, text):
        text = re.sub("(?s)(Conventions [Uu]sed in this [Dd]ocument|Requirements [Ll]anguage)?[\n ]*The key words \"MUST\", \"MUST NOT\",.*$", "", text)
        # Get rid of status/copyright boilerplate
        text = re.sub("(?s)\nStatus of [tT]his Memo\n.*$", "", text)
        # wrap long lines without messing up formatting of Ok paragraphs:
        while re.match("([^\n]{72,}?) +", text):
            text = re.sub("([^\n]{72,}?) +([^\n ]*)(\n|$)", "\\1\n\\2 ", text)
        return text


    # ------------------------------------------------------------------
    def get_authors(self):
        """Returns a list of strings with author name and email within angle brackets"""
        if self._authors == None:
            self.extract_authors()
        return self._authors

    def get_authors_with_firm(self):
        """Returns a list of strings with author name and email within angle brackets"""
        if self._authors_with_firm == None:
            self.extract_authors()
        return self._authors_with_firm
        

    def get_author_list(self):          # () -> List[List[str, str, str, str, str, str, str]]
        """Returns a list of tuples, with each tuple containing (given_names,
        surname, email, company).  Email will be None if unknown.

        Todo update to agree with superclass method signature
        """
        if self._author_info == None:
            self.extract_authors()
        return self._author_info

    def extract_authors(self):
        """Extract author information from draft text.

        """
        aux = {
            "honor" : r"(?:[A-Z]\.|Dr\.?|Dr\.-Ing\.|Prof(?:\.?|essor)|Sir|Lady|Dame|Sri)",
            "prefix": r"([Dd]e|Hadi|van|van de|van der|Ver|von|[Ee]l)",
            "suffix": r"(jr.?|Jr.?|II|2nd|III|3rd|IV|4th)",
            "first" : r"([A-Z][-A-Za-z'`~,]*)(( ?\([A-Z][-A-Za-z'`~,]*\))?(\.?[- ]{1,2}[A-Za-z'`~]+)*)",
            "last"  : r"([-A-Za-z'`~,]+)",  # single-letter last names exist
            "months": r"(January|February|March|April|May|June|July|August|September|October|November|December)",
            "mabbr" : r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?",
            }
        authcompanyformats = [
            r" {6}(?P<author>(%(first)s[ \.]{1,3})+((%(prefix)s )?%(last)s)( %(suffix)s)?), (?P<company>[^.]+\.?)$" % aux,
            r" {6}(?P<author>(%(first)s[ \.]{1,3})+((%(prefix)s )?%(last)s)( %(suffix)s)?) *\((?P<company>[^.]+\.?)\)$" % aux,
        ]
        authformats = [
            r" {6}((%(first)s[ \.]{1,3})+((%(prefix)s )?%(last)s)( %(suffix)s)?)(, ([^.]+\.?|\([^.]+\.?|\)))?,?$" % aux,
            r" {6}(((%(prefix)s )?%(last)s)( %(suffix)s)?, %(first)s)?$" % aux,
            r" {6}(%(last)s)$" % aux,
        ]
        multiauthformats = [
            (
                r" {6}(%(first)s[ \.]{1,3}((%(prefix)s )?%(last)s)( %(suffix)s)?)(, ?%(first)s[ \.]{1,3}((%(prefix)s )?%(last)s)( %(suffix)s)?)+$" % aux,
                r"(%(first)s[ \.]{1,3}((%(prefix)s )?%(last)s)( %(suffix)s)?)" % aux
            ),
        ]
        editorformats = [
            r"(?:, | )([Ee]d\.?|\([Ee]d\.?\)|[Ee]ditor)$",
        ]
        companyformats = [
            r" {6}(([A-Za-z'][-A-Za-z0-9.& ']+)(,? ?(Inc|Ltd|AB|S\.A)\.?))$",
            r" {6}(([A-Za-z'][-A-Za-z0-9.& ']+)(/([A-Za-z'][-A-Za-z0-9.& ']+))+)$",
            r" {6}([a-z0-9.-]+)$",
            r" {6}(([A-Za-z'][-A-Za-z0-9.&']+)( [A-Za-z'][-A-Za-z0-9.&']+)*)$",
            r" {6}(([A-Za-z'][-A-Za-z0-9.']+)( & [A-Za-z'][-A-Za-z0-9.']+)*)$",
            r" {6}\((.+)\)$",
            r" {6}(\w+\s?\(.+\))$",
        ]

        dateformat = r"(((%(months)s|%(mabbr)s) \d+, |\d+ (%(months)s|%(mabbr)s),? |\d+/\d+/)\d\d\d\d|\d\d\d\d-\d\d-\d\d)$" % aux

        address_section = r"^ *([0-9]+\.)? *(Author|Editor)('s|s'|s|\(s\)) (Address|Addresses|Information)"

        # "Internet Draft" (without the dash) is correct here, because the usage is to
        # suppress incorrect author name extraction
        ignore = [
            "Standards Track", "Current Practice", "Internet Draft", "Working Group",
            "Expiration Date", 
            ]

        def make_authpat(hon, first, last, suffix):
            def dotexp(s):
                s = re.sub(r"\. ",    r"\\w* ", s)
                s = re.sub(r"\.$",    r"\\w*", s)
                s = re.sub(r"\.(\w)", r"\\w* \1", s)
                return s
            first = dotexp(first)
            last = dotexp(last)
            first = re.sub("[()]", " ", first)
            if " " in first:
                # if there's a middle part, let it be optional
                first, middle = first.split(" ", 1)
                first = "%s( +%s)?" % (first, middle)

            # Double names (e.g., Jean-Michel) are abbreviated as two letter
            # connected by a dash -- let this expand appropriately
            first = re.sub(r"^([A-Z])-([A-Z])\\w\*", r"\1.*-\2.*", first) 

            # Some chinese names are shown with double-letter(latin) abbreviated given names, rather than
            # a single-letter(latin) abbreviation:
            first = re.sub(r"^([A-Z])[A-Z]+\\w\*", r"\1[-\\w]+", first) 

            # permit insertion of middle names between first and last, and
            # add possible honorific and suffix information
            if last:
                authpat = r"(?:^| and )((?:%(hon)s ?)?['`]*%(first)s\S*( +[^ ]+)* +%(last)s(?: %(suffix)s)?)( *\(.*|,( [A-Z][-A-Za-z0-9]*)?| [A-Z][a-z]+)?" % {"hon":hon, "first":first, "last":last, "suffix":suffix,}
            else:
                # handle single-word names
                authpat = r"(?:^| and )((?:%(hon)s ?)?['`]*%(first)s\S*( +[^ ]+)*(?: %(suffix)s)?)( *\(.*|,( [A-Z][-A-Za-z0-9]*)?| [A-Z][a-z]+)?" % {"hon":hon, "first":first, "suffix":suffix,}

            return authpat

        authors = []
        companies = []
        companies_seen = []
        self._docheader = ""

        # Collect first-page author information first
        have_blankline = False
        have_draftline = False
        prev_blankline = False
        for line in self.lines[:30]:
            self._docheader += line+"\n"
            author_on_line = False

            _debug( " ** " + line)
            leading_space = len(re.findall("^ *", line)[0])
            line_len = len(line.rstrip())
            trailing_space = line_len <= 72 and 72 - line_len or 0
            # Truncate long lines at the first space past column 80:
            trunc_space = line.find(" ", 80)
            if line_len > 80 and  trunc_space > -1:
                line = line[:trunc_space]
            if line_len > 60:
                # Look for centered title, break if found:
                if (leading_space > 5 and abs(leading_space - trailing_space) < 5):
                    _debug("Breaking for centered line")
                    break
                if re.search(dateformat, line):
                    if authors:
                        _debug("Breaking for dateformat after author name")
                for editorformat in editorformats:
                    if re.search(editorformat, line):
                        line = re.sub(editorformat, "", line)
                        break
                for lineformat, authformat in multiauthformats:
                    match = re.search(lineformat, line)
                    if match:
                        _debug("a. Multiauth format: '%s'" % lineformat)
                        author_list = re.findall(authformat, line)
                        authors += [ a[0] for a in author_list ]
                        companies += [ None for a in author_list ]
                        author_on_line = True
                        #_debug("\nLine:   " + line)
                        #_debug("Format: " + authformat)
                        for author in author_list:
                            _debug("Author: '%s'" % author[0])
                        break
                if not author_on_line:
                    for lineformat in authcompanyformats:
                        match = re.search(lineformat, line)
                        if match:
                            _debug("b. Line format: '%s'" % lineformat)
                            maybe_company = match.group("company").strip(" ,.")
                            # is the putative company name just a partial name, i.e., a part
                            # that commonly occurs after a comma as part of a company name,
                            # as in "Foo Bar, Inc."?  If so, skip; else assume there's a
                            # company name after the comma.
                            if not maybe_company in ["Inc", "Ltd", "S.A", "AG", "AB", "N.V", ]:
                                author = match.group("author")
                                company = match.group("company")
                                authors += [ author, '']
                                companies += [ None, company ]
                                #_debug("\nLine:   " + line)
                                #_debug("Format: " + authformat)
                                _debug("Author: '%s'" % author)
                                _debug("Company: '%s'" % company)
                                author_on_line = True
                                break
                if not author_on_line:
                    for authformat in authformats:
                        match = re.search(authformat, line)
                        if match:
                            _debug("c. Auth format: '%s'" % authformat)
                            author = match.group(1)
                            authors += [ author ]
                            companies += [ None ]
                            #_debug("\nLine:   " + line)
                            #_debug("Format: " + authformat)
                            _debug("Author: '%s'" % author)
                            author_on_line = True
                            break
                if not author_on_line:
                    for authformat in companyformats:
                        match = re.search(authformat, line)
                        if match:
                            _debug("d. Company format: '%s'" % authformat)
                            company = match.group(1)
                            authors += [ "" ]
                            companies += [ company ]
                            #_debug("\nLine:   " + line)
                            #_debug("Format: " + authformat)
                            _debug("Company: '%s'" % company)
                            break
            if authors and not author_on_line:
                # Retain information about blank lines in author list
                authors += [""]
                companies += [ "" ]
            if line.strip() == "":
                if prev_blankline and authors:
                    _debug("Breaking, having found consecutive blank lines after author name")
                    break
                if authors:
                    have_blankline = True
                    prev_blankline = True
            else:
                prev_blankline = False
            if "draft-" in line:
                have_draftline = True
            if have_blankline and have_draftline:
                _debug("Breaking, having found both blank line and draft-name line")
                break

        # remove trailing blank entries in the author list:
        for i in range(len(authors)-1,-1,-1):
            if authors[i] == "" and companies[i] == "":
                del authors[i]
                del companies[i]
            else:
                break

        _debug("A:companies : %s" % str(companies))
        #companies = [ None if a else '' for a in authors ]
        #_debug("B:companies : %s" % str(companies))
        #find authors' addresses section if it exists
        _debug("B:authors   : %s" % str(authors))

        last_line = len(self.lines)-1
        address_section_pos = last_line//2
        for i in range(last_line//2,last_line):
            line = self.lines[i]
            if re.search(address_section, line):
                address_section_pos = i
                break

        found_pos = []
        company_or_author = None
        for i in range(len(authors)):
            _debug("1: authors[%s]: %s" % (i, authors[i]))
            _debug("   company[%s]: %s" % (i, companies[i]))
            author = authors[i]
            if i+1 < len(authors):
                company_or_author = authors[i+1]
            else:
                company_or_author = None
            if author in [ None, '', ]:
                continue
            suffix_match = re.search(" %(suffix)s$" % aux, author)
            if suffix_match:
                suffix = suffix_match.group(1)
                author = author[:-len(suffix)].strip()
            else:
                suffix = None
            if ", " in author:
                last, first = author.split(",",1)
                author = "%s %s" % (first.strip(), last.strip())
            if not " " in author:
                if "." in author:
                    first, last = author.rsplit(".", 1)
                    first += "."
                else:
                    # handle single-word names
                    first = author
                    last = ""
            else:
                if "." in author:
                    first, last = author.rsplit(".", 1)
                    first += "."
                else:
                    first, last = author.rsplit(" ", 1)
                    if "." in first and not ". " in first:
                        first = first.replace(".", ". ").strip()
            first = first.strip()
            last = last.strip()
            prefix_match = re.search(" %(prefix)s$" % aux, first)
            if prefix_match:
                prefix = prefix_match.group(1)
                first = first[:-len(prefix)].strip()
                last = prefix+" "+last
            _debug("First, Last: '%s' '%s'" % (first, last))
            for firstname, surname, casefixname in [ (first,last,last), (last,first,first), (first,last,last.upper()), (last,first,first.upper()), ]:
                for left, right in [(firstname, casefixname), (casefixname, firstname)]:
                    author = "%s %s" % (left, right)
                    _debug("\nAuthors: "+str(authors))
                    _debug("Author: "+author)

                    # Pattern for full author information search, based on first page author name:
                    authpat = make_authpat(aux['honor'], left, right, aux['suffix'])
                    _debug("Authpat: " + authpat)
                    start = 0
                    col = None
                    # Find start of author info for this author (if any).
                    # Scan towards the front from the end of the file, looking for a match to authpath
                    for j in range(last_line, address_section_pos, -1):
                        line = self.lines[j]
                        _debug( "Line: " + line)
                        forms = [ line ] + [ line.replace(short, longform[short]) for short in longform if short in line ]
                        for form in forms:
                            try:
                                if re.search(authpat, form.strip()) and not j in found_pos:
                                    _debug( "Match")

                                    start = j
                                    found_pos += [ start ]
                                    _debug( " ==> start %s, normalized '%s'" % (start, form.strip()))
                                    # The author info could be formatted in multiple columns...
                                    columns = re.split("(    +|  and  )", form)
                                    # _debug( "Columns:" + str(columns))
                                    # Find which column:
                                    # _debug( "Col range:" + str(range(len(columns))))

                                    cols = [ c for c in range(len(columns)) if re.search(authpat+r"(  and  |, |$)", columns[c].strip()) ]
                                    if cols:
                                        col = cols[0]
                                        if not (start, col) in found_pos:
                                            found_pos += [ (start, col) ]
                                            _debug( "Col:   %d" % col)
                                            beg = len("".join(columns[:col]))
                                            _debug( "Beg:   %d '%s'" % (beg, "".join(columns[:col])))
                                            _debug( "Len:   %d" % len(columns))
                                            if col == len(columns) or col == len(columns)-1:
                                                end = None
                                                _debug( "End1:  %s" % end)
                                            else:
                                                end = beg + len("".join(columns[col:col+2]))
                                                _debug( "End2:  %d '%s'" % (end, "".join(columns[col:col+2])))
                                            _debug( "Cut:   '%s'" % form[beg:end])
                                            author_match = re.search(authpat, columns[col].strip()).group(1)
                                            _debug( "AuthMatch: '%s'" % (author_match,))
                                            if re.search(r'\(.*\)$', author_match.strip()):
                                                author_match = author_match.rsplit('(',1)[0].strip()
                                            if author_match in companies_seen:
                                                companies[i] = authors[i]
                                                authors[i] = None
                                            else:
                                                fullname = author_match
                                                #if casefixname in author_match:
                                                #    fullname = author_match.replace(casefixname, surname)
                                                #else:
                                                #    fullname = author_match
                                                fullname = re.sub(" +", " ", fullname)
                                                if re.search(r"\s", fullname):
                                                    if left == firstname:
                                                        given_names, surname = fullname.rsplit(None, 1)
                                                    else:
                                                        surname, given_names = fullname.split(None, 1)
                                                else:
                                                    # handle single-word names
                                                    given_names, surname = (fullname, "")
                                                if " " in given_names:
                                                    first, middle = given_names.split(None, 1)
                                                else:
                                                    first = given_names
                                                    middle = None
                                                names = (first, middle, surname, suffix)

                                                if suffix:
                                                    fullname = fullname+" "+suffix
                                                for names in [
                                                        (first, middle, surname, suffix),
                                                        (first, surname, middle, suffix),
                                                        (middle, first, surname, suffix),
                                                        (middle, surname, first, suffix),
                                                        (surname, first, middle, suffix),
                                                        (surname, middle, first, suffix),
                                                    ]:
                                                    parts = [ n for n in names if n ]
                                                    if (" ".join(parts) == fullname):
                                                        authors[i] = (fullname, first, middle, surname, suffix)
                                                        companies[i] = None
                                                        break
                                                else:
                                                    _warn("Author tuple doesn't match text in Internet-Draft: %s, %s" % (authors[i], fullname))
                                                    authors[i] = None
                                            break
                            except AssertionError:
                                sys.stderr.write("filename: "+self.filename+"\n")
                                sys.stderr.write("authpat: "+authpat+"\n")
                                raise
                        if start and col != None:
                            break
                    if start and col != None:
                        break
                if start and col != None:
                    break
            # End for:
            if not authors[i]:
                continue
            _debug("2: authors[%s]: %s" % (i, authors[i]))
            if start and col != None:
                _debug("\n * %s" % (authors[i], ))
                nonblank_count = 0
                blanklines = 0
                email = None
                country = None
                for line_offset, line in enumerate(self.lines[start+1:]):
                    _debug( "       " + line.strip())
                    # Break on the second blank line
                    if not line:
                        blanklines += 1
                        if blanklines >= 3:
                            _debug( " - Break on blanklines")
                            break
                        else:
                            continue
                    else:
                        nonblank_count += 1                    

                    # Maybe break on author name
    #                 _debug("Line: %s"%line.strip())
    #                 for a in authors:
    #                     if a and a not in companies_seen:
    #                         _debug("Search for: %s"%(r"(^|\W)"+re.sub("\.? ", ".* ", a)+"(\W|$)"))
                    authmatch = [ a for a in authors[i+1:] if a and not a.lower() in companies_seen and (re.search((r"(?i)(^|\W)"+re.sub(r"[. ]+", ".*", a)+r"(\W|$)"), line.strip()) or acronym_match(a, line.strip()) )]

                    if authmatch:
                        _debug("     ? Other author or company ?  : %s" % authmatch)
                        _debug("     Line: "+line.strip())
                        _debug("     C or A: %s"%company_or_author)
                        if nonblank_count == 1 or (nonblank_count == 2 and not blanklines) or (company_or_author==line.strip() and not blanklines):
                            # First line after an author -- this is a company
                            companies_seen += [ c.lower() for c in authmatch ]
                            companies_seen += [ line.strip().lower() ] # XXX fix this for columnized author list
                            companies_seen = list(set(companies_seen))
                            _debug("       -- Companies: " + ", ".join(companies_seen))
                            for k in range(i+1, len(authors)):
                                if authors[k] and authors[k].lower() in companies_seen:
                                    companies[k] = authors[k]
                                    authors[k] = None
                        elif blanklines and not "@" in line:
                            # Break on an author name
                            _debug( " - Break on other author name")
                            break
                        else:
                            pass

                    def columnify(l):
                        try:
                            column = l.replace('\t', 8 * ' ')[max(0, beg - 1):end].strip()
                        except:
                            column = l
                        column = re.sub(r" *(?:\(at\)| <at> | at ) *", "@", column)
                        column = re.sub(r" *(?:\(dot\)| <dot> | dot ) *", ".", column)
                        column = re.sub(r"&cisco.com", "@cisco.com", column)
                        column = column.replace("\xa0", " ")
                        return column

                    column = columnify(line)

    #                 if re.search("^\w+: \w+", column):
    #                     keyword = True
    #                 else:
    #                     if keyword:
    #                         # Break on transition from keyword line to something else
    #                         _debug( " - Break on end of keywords")
    #                         break

                    #_debug( "  Column text :: " + column)
                    if nonblank_count >= 2 and blanklines == 0:
                        # Usually, the contact info lines will look
                        # like this: "Email: someone@example.com" or
                        # "Tel: +1 (412)-2390 23123", but sometimes
                        # the : is left out. That's okay for things we
                        # can't misinterpret, but "tel" may match "Tel
                        # Aviv 69710, Israel" so match
                        # - misc contact info
                        # - tel/fax [number]
                        # - [phone number]
                        # - [email]

                        other_contact_info_regex = re.compile(r'^(((contact )?e|\(e|e-|m|electronic )?mail|email_id|mailto|e-main|(tele)?phone|voice|mobile|work|uri|url|tel:)\b|^((ph|tel\.?|telefax|fax) *[:.]? *\(?( ?\+ ?)?[0-9]+)|^(\++[0-9]+|\(\+*[0-9]+\)|\(dsn\)|[0-9]+)([ -.]*\b|\b[ -.]*)(([0-9]{2,}|\([0-9]{2,}\)|(\([0-9]\)|[0-9])[ -][0-9]{2,}|\([0-9]\)[0-9]+)([ -.]+([0-9]+|\([0-9]+\)))+|([0-9]{7,}|\([0-9]{7,}\)))|^(<?[-a-z0-9._+]+|{([-a-z0-9._+]+, ?)+[-a-z0-9._+]+})@[-a-z0-9._]+>?|^https?://|^www\.')
                        next_line_index = start + 1 + line_offset + 1

                        if (not country
                            and not other_contact_info_regex.search(column.lower())
                            and next_line_index < len(self.lines)):

                            next_line_lower = columnify(self.lines[next_line_index]).lower().strip()

                            if not next_line_lower or other_contact_info_regex.search(next_line_lower):
                                # country should be here, as the last
                                # part of the address, right before an
                                # empty line or other contact info
                                country = column.strip() or None
                                _debug(" Country: %s" % country)

                    _debug("3: authors[%s]: %s" % (i, authors[i]))

                    emailmatch = re.search("[-A-Za-z0-9_.+]+@[-A-Za-z0-9_.]+", column)
                    if emailmatch and not "@" in author:
                        email = emailmatch.group(0).lower()
                        break

                authors[i] = authors[i] + ( email, country)
            else:
                if not author in ignore:
                    companies[i] = authors[i]
                    _debug("Not an author? '%s'" % (author))
                authors[i] = None

        assert(len(authors) == len(companies))        
        _debug('Author list: %s' % authors)
        _debug('Company list: %s' % companies)
        for i in range(len(authors)):
            if authors[i]:
                _debug('authors[%s]: %s' % (i, authors[i]))
                company = ''
                for k in range(i+1, len(companies)):
                    _debug('companies[%s]: %s' % (k, companies[k]))
                    if companies[k] != None:
                        company = companies[k]
                        break
                authors[i] = authors[i] + ( company, )

        authors = [ a for a in authors if a ]
        _debug(" * Final author tuples: %s" % (authors,))
        _debug(" * Final company list: %s" % (companies,))
        _debug(" * Final companies_seen: %s" % (companies_seen,))
        self._author_info = authors        
        self._authors_with_firm = [ "%s <%s> (%s)"%(full,email,company) for full,first,middle,last,suffix,email,country,company in authors ] # pyflakes:ignore
        self._authors = [ "%s <%s>"%(full,email) if email else full for full,first,middle,last,suffix,email,country,company in authors ]
        self._authors.sort()
        _debug(" * Final author list: " + ", ".join(self._authors))
        _debug("-"*72)

    # ------------------------------------------------------------------
    def get_title(self):
        if self._title:
            return self._title
        match = re.search(r'(?:\n\s*\n\s*)((.+\n){0,2}(.+\n*))(\s+<?draft-\S+\s*\n)\s*\n', self.pages[0])
        if not match:
            match = re.search(r'(?:\n\s*\n\s*)<?draft-\S+\s*\n*((.+\n){1,3})\s*\n', self.pages[0])
        if not match:
            match = re.search(r'(?:\n\s*\n\s*)((.+\n){0,2}(.+\n*))(\s*\n){2}', self.pages[0])
        if not match:
            match = re.search(r'(?i)(.+\n|.+\n.+\n)(\s*status of this memo\s*\n)', self.pages[0])
        if match:
            title = match.group(1)
            title = title.strip()
            title = re.sub(r'(?s)\n\s*\<?draft-.*$','', title)
            title = re.sub(r'\s*\n\s*', ' ', title)
            title = re.sub(r' +', ' ', title)
            self._title = title
            return self._title
        self.errors["title"] = "Could not find the title on the first page."

    # ------------------------------------------------------------------
    def get_refs(self):
        # Bill's horrible "references section" regexps, built up over lots of years
        # of fine tuning for different formats.
        # Examples:
        # Appendix A. References:
        # A.1. Informative References:
        sectionre = re.compile( r'(?i)(?:Appendix\s+)?(?:(?:[A-Z]\.)?[0-9.]*\s+)?(?:(\S+)\s*)?references:?$' )
        # 9.1 Normative
        sectionre2 = re.compile( r'(?i)(?:(?:[A-Z]\.)?[0-9.]*\s+)?(\S+ormative)$' )
        # One other reference section type seen:
        sectionre3 = re.compile( r'(?i)References \((\S+ormative)\)$' )
        # An Internet-Draft reference.
        idref = re.compile( r'(?i)\b(draft-(?:[-\w]+(?=-\d\d)|[-\w]+))(-\d\d)?\b' )
        # An RFC-and-other-series reference.
        rfcref = re.compile( r'(?i)\b(rfc|std|bcp|fyi)[- ]?(\d+)\b' )
        # False positives for std
        not_our_std_ref = re.compile( r'(?i)((\b(n?csc|fed|mil|is-j)-std\b)|(\bieee\s*std\d*\b)|(\bstd\s+802\b))' )
        # An Internet-Draft or series reference hyphenated by a well-meaning line break.
        eol = re.compile( r'(?i)\b(draft[-\w]*-|rfc|std|bcp|fyi)$' )
        # std at the front of a line can hide things like IEEE STD or MIL-STD
        std_start = re.compile( r'(?i)std\n*\b' )

        not_starting_regexes = [
            re.compile( r'(?i) uri references:?$' ),
        ]

        refs = {}
        in_ref_sect = False
        in_norm_ref_sect = False
        refType = self.REF_TYPE_UNKNOWN

        for i in range( 15, len( self.lines ) ):
            line = self.lines[ i ].strip()

            # skip over lines until we find the start of the reference section
            if not in_ref_sect:
                m = sectionre.match( line )
                if not m:
                    m = sectionre2.match( line )
                    if not m:
                        m = sectionre3.match( line )

                if m:
                    if not any( [ rule.search( line ) for rule in not_starting_regexes ]):
                        in_ref_sect = True
                        refType = self.REF_TYPE_INFORMATIVE
                        if line.lower().find("normative") > 1:
                            in_norm_ref_sect = True
                            refType = self.REF_TYPE_NORMATIVE

            # might be subsections within a references section
            if in_ref_sect and not in_norm_ref_sect:
                m = sectionre.match( line )
                if not m:
                    m = sectionre2.match( line )
                    if not m:
                        m = sectionre3.match( line )

                if m:
                    in_ref_sect = True
                    if line.lower().find("normative") > 1:
                        in_norm_ref_sect = True
                        refType = self.REF_TYPE_NORMATIVE

            # look for the end of the normative reference section
            if in_norm_ref_sect:
                m = sectionre.match( line )
                if not m:
                    m = sectionre2.match( line )
                    if not m:
                        m = sectionre3.match( line )

                if m and line.lower().find("normative") < 0:
                    in_norm_ref_sect = False
                    refType = self.REF_TYPE_INFORMATIVE

            # find references within the section
            if in_ref_sect:
                # If something got split badly, rejoin it.
                if eol.search( line ) and i < len( self.lines ) - 1:
                    line += self.lines[ i + 1 ].lstrip()

                m = idref.search( line )
                if m:
                    draft = m.group( 1 )
                    if draft not in refs:
                        refs[ draft ] = refType

                m = rfcref.search( line )
                if m:
                    ( series, number ) = m.groups()
                    if series.lower()=='std' and std_start.search(line) and i > 15:
                        line = self.lines[i-1].rstrip()+line
                    if series.lower()!='std' or not not_our_std_ref.search( line ):
                        name = series.lower() + number.lstrip( '0' )
                        if name not in refs:
                            refs[ name ] = refType

        # Don't add any references that point back into this doc
        if self.filename in refs:
            del refs[self.filename]

        return refs

    def old_get_refs( self ):
        refs = []
        normrefs = []
        rfcrefs = []
        draftrefs = []
        refline = None
        for i in range(len(self.lines)-1, 15, -1):
            if re.search(r"(?i)^ *[0-9.]+ *(((normative|informative|informational|non-normative) )?references|references\W+(normative|informative))", self.lines[i]):
                if not '. . .' in self.lines[i] and not '...' in self.lines[i]:
                    refline = i
        if refline:
            for i in range(refline, len(self.lines)):
                line = self.lines[i].strip()
                ref_match = re.search(r"(?i)^\[[a-z0-9.-]+( [a-z0-9.-]+)?\].+", line)
                if ref_match:
                    para = line
                    while True:
                        i += 1
                        if i >= len(self.lines):
                            break
                        line = self.lines[i].strip()
                        if not line:
                            break
                        if para[-1] not in ["-", "/"]:
                            para += " "
                        para += line
                    refs += [ para ]
                    rfc_match = re.search(r"(?i)rfc ?\d+", para)
                    if rfc_match:
                        rfcrefs += [ rfc_match.group(0).replace(" ","").lower() ]
                    draft_match = re.search(r"draft-[a-z0-9-]+", para)
                    if draft_match:
                        draft = draft_match.group(0).lower()
                        if not draft in draftrefs:
                            draftrefs += [ draft ]
        normrefs = list(set(normrefs))
        normrefs.sort()
        rfcrefs = list(set(rfcrefs))
        rfcrefs.sort()
        refs = list(set(refs))
        refs.sort()
        return normrefs, rfcrefs, draftrefs, refs

# ----------------------------------------------------------------------

def getmeta(fn):
    # Initial values
    fields = {}
    fields["eventsource"] = "draft"

    if " " in fn or not fn.endswith(".txt"):
        _warn("Skipping unexpected Internet-Draft name: '%s'" % (fn))
        return {}

    if os.path.exists(fn):
        filename = fn
        fn = os.path.basename(fn)
    else:
        _warn("Could not find file:  '%s'" % (filename))
        return

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(os.stat(filename)[stat.ST_MTIME]))
    with io.open(filename, 'rb') as file:
        try:
            draft = PlaintextDraft(file.read().decode('utf8'), filename)
        except UnicodeDecodeError:
            draft = PlaintextDraft(file.read().decode('latin1'), filename)
    #_debug("\n".join(draft.lines))

    fields["eventdate"] = timestamp
    if draft.filename:
        fields["doctag"] = draft.filename
    fields["docrev"] = draft.revision

    fields["doctitle"] = draft.get_title()
    fields["docpages"] = str(draft.get_pagecount())
    fields["docauthors"] = ", ".join(draft.get_authors())
    fields["_authorlist"] = draft.get_author_list()
    fields["docaffiliations"] = ", ".join(draft.get_authors_with_firm())
    if opt_debug:
        fields["docheader"] = draft._docheader
    normrefs, rfcrefs, draftrefs, refs = draft.old_get_refs()
    fields["docrfcrefs"] = ", ".join(rfcrefs)
    fields["docdraftrefs"] = ", ".join(draftrefs)
    fields["doccreationdate"] = str(draft.get_creation_date())
    deststatus = draft.get_status()
    if deststatus:
        fields["docdeststatus"] = deststatus
    abstract = draft.get_abstract()
    if abstract:
        fields["docabstract"] = abstract

    return fields


# ----------------------------------------------------------------------
def _output(docname, fields, outfile=sys.stdout):
    global company_domain

    if opt_attributes:
        def outputkey(key, fields):
            field = fields[key]
            if "\n" in field:
                field = "\n" + field.rstrip()
            else:
                field = field.strip()
            outfile.write("%-24s: %s\n" % ( key, field.replace("\\", "\\\\" ).replace("'", "\\x27" )))
    else:
        def outputkey(key, fields):
            outfile.write(" %s='%s'" % ( key.lower(), fields[key].strip().replace("\\", "\\\\" ).replace("'", "\\x27" ).replace("\n", "\\n")))
        if opt_timestamp:
            outfile.write("%s " % (fields["eventdate"]))
        outfile.write("%s" % (os.path.basename(docname.strip())))

    keys = list(fields.keys())
    keys.sort()
    for key in keys:
        if fields[key] and not key in ["eventdate", ] and not key.startswith("_"):
            outputkey(key, fields)
    outfile.write("\n")

# ----------------------------------------------------------------------
def _printmeta(fn, outfile=sys.stdout):
    if opt_trace:
        t = time.time()
        sys.stderr.write("%-58s" % fn[:-4])

    fields = getmeta(fn)
    if fields:
        _output(fields.get("doctag", fn[:-7]), fields, outfile)

    if opt_trace:
        sys.stderr.write("%5.1f\n" % ((time.time() - t)))

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

company_domain = {}                     # type: Dict[str, str]
def _main(outfile=sys.stdout):
    global opt_debug, opt_timestamp, opt_trace, opt_authorinfo, files, company_domain, opt_attributes
    # set default values, if any
    # ----------------------------------------------------------------------
    # Option processing
    # ----------------------------------------------------------------------
    options = ""
    for line in re.findall(r"\n +(if|elif) +opt in \[(.+)\]:\s+#(.+)\n", io.open(sys.argv[0]).read()):
        if not options:
            options += "OPTIONS\n"
        options += "        %-16s %s\n" % (line[1].replace('"', ''), line[2])
    options = options.strip()

    # with ' < 1:' on the next line, this is a no-op:
    if len(sys.argv) < 1:
        vars = globals()
        vars.update(locals())
        print(__doc__ % vars)
        sys.exit(1)

    try:
        opts, files = getopt.gnu_getopt(sys.argv[1:], "dhatTv", ["debug", "getauthors", "attribs", "attributes", "help", "timestamp", "notimestamp", "trace", "version",])
    except Exception as e:
        print("%s: %s" % (program, e))
        sys.exit(1)

    # parse options
    for opt, value in opts:
        if opt in ["-d", "--debug"]:  # Output debug information
            opt_debug = True
        elif opt in ["-h", "--help"]:   # Output this help text, then exit
            vars = globals()
            vars.update(locals())
            print(__doc__ % vars)
            sys.exit(1)
        elif opt in ["-v", "--version"]: # Output version information, then exit
            print(program, version)
            sys.exit(0)
        elif opt in ["-a", "--attribs"]: # Output key-value attribute pairs 
            opt_attributes = True
        elif opt in ["-t", ]: # Toggle leading timestamp information 
            opt_timestamp = not opt_timestamp
        elif opt in ["--timestamp"]: # Emit leading timestamp information 
            opt_timestamp = True
        elif opt in ["--notimestamp"]: # Omit leading timestamp information 
            opt_timestamp = False
        elif opt in ["-T", "--trace"]: # Emit trace information while working
            opt_trace = True

    company_domain = {}
 
    if not files:
        files = [ "-" ]

    for file in files:
        _debug( "Reading Internet-Drafts from '%s'" % file)
        if file == "-":
            file = sys.stdin
        elif file.endswith(".gz"):
            import gzip
            file = gzip.open(file)
        else:
            file = io.open(file)

        basename = os.path.basename(file.name)
        if basename.startswith("draft-"):
            draft = basename
            _debug( "** Processing '%s'" % draft)
            _printmeta(file.name, outfile)
        else:
            for line in file:
                draft = line.strip()
                if draft.startswith("#"):
                    continue
                if draft:
                    _debug( "** Processing '%s'" % draft)
                    _printmeta(draft, outfile)

if __name__ == "__main__":
    try:
        _main()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        if opt_debug:
            raise
        else:
            _err(e)

