#!/usr/bin/python
# -*- python -*-

"""
NAME
	%(program)s - Extract meta-information from an IETF draft.

SYNOPSIS
	%(program)s [OPTIONS] DRAFTLIST_FILE

DESCRIPTION
        Extract information about authors' names and email addresses,
        intended status and number of pages from Internet Drafts.
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

import getopt
import os
import os.path
import re
import stat
import sys
import time

version = "0.13"
program = os.path.basename(sys.argv[0])
progdir = os.path.dirname(sys.argv[0])

# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------


opt_debug = False
opt_timestamp = False
opt_trace = False

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
    "Ned": "Edward" ,
    "Ted":"Edward",
}
longform = dict([ (short+" ", longform[short]+" ") for short in longform ])


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
    file = open(file)
    text = file.read()
    file.close()

    text = re.sub(".\x08", "", text)    # Get rid of inkribbon backspace-emphasis
    text = text.replace("\r\n", "\n")   # Convert DOS to unix
    text = text.replace("\r", "\n")     # Convert MAC to unix
    text = text.strip()

    return text

# ----------------------------------------------------------------------

class Draft():

    def __init__(self, text):
        self.rawtext = text

        text = re.sub(".\x08", "", text)    # Get rid of inkribbon backspace-emphasis
        text = text.replace("\r\n", "\n")   # Convert DOS to unix
        text = text.replace("\r", "\n")     # Convert MAC to unix
        text = text.strip()
        self.text = text
        self.errors = {}

        self.rawlines = self.text.split("\n")
        self.lines, self.pages = self._stripheaders()
        if not self.pages:
            self.pages = [ self.text ]
        self.filename, self.revision = self._parse_draftname()
        
        self._authors = None
        self._pagecount = None
        self._status = None
        self._creation_date = None

    # ------------------------------------------------------------------
    def _parse_draftname(self):
        draftname_regex = r"(draft-[a-z0-9-]*)-(\d\d)(\w|\.txt|\n|$)"
        draftname_match = re.search(draftname_regex, self.pages[0])
        if draftname_match:
            return (draftname_match.group(1), draftname_match.group(2) )
        else:
            self.errors["draftname"] = "Could not find the draft name and revision on the first page."
            return ("", "")

    # ----------------------------------------------------------------------
    def _stripheaders(self):
        stripped = []
        pages = []
        page = []
        line = ""
        debug = False
        newpage = False
        sentence = False
        haveblank = False
        # two functions with side effects
        def endpage(pages, page, line):
            if line:
                page += [ line ]
            return begpage(pages, page)
        def begpage(pages, page, line=None):
            if page and len(page) > 5:
                pages += [ "\n".join(page) ]
                page = []
                newpage = True
            if line:
                page += [ line ]
            return pages, page
        for line in self.rawlines:
    #         if re.search("^ *Curtis King", line):
    #             debug = True
    #         if re.search("^Intellectual", line):
    #             debug = False
    #         if debug:
    #             _debug( "* newpage: %s; sentence: %s; haveblank: %s" % (newpage, sentence, haveblank))
    #             _debug( "    " + line)
            line = line.rstrip()
            if re.search("\[?[Pp]age [0-9ivx]+\]?[ \t\f]*$", line, re.I):
                pages, page = endpage(pages, page, line)
                continue
            if re.search("\f", line, re.I):
                pages, page = begpage(pages, page)
                continue
            if re.search("^ *Internet.Draft.+[12][0-9][0-9][0-9] *$", line, re.I):
                pages, page = begpage(pages, page, line)
                continue
    #        if re.search("^ *Internet.Draft  +", line, re.I):
    #            newpage = True
    #            continue
            if re.search("^ *Draft.+[12][0-9][0-9][0-9] *$", line, re.I):
                pages, page = begpage(pages, page, line)
                continue
            if re.search("^RFC[ -]?[0-9]+.*(  +)[12][0-9][0-9][0-9]$", line, re.I):
                pages, page = begpage(pages, page, line)
                continue
            if re.search("^draft-[-a-z0-9_.]+.*[0-9][0-9][0-9][0-9]$", line, re.I):
                pages, page = endpage(pages, page, line)
                continue
            if re.search(".{60,}(Jan|Feb|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|Sep|Oct|Nov|Dec) (19[89][0-9]|20[0-9][0-9]) *$", line, re.I):
                pages, page = begpage(pages, page, line)
                continue
            if newpage and re.search("^ *draft-[-a-z0-9_.]+ *$", line, re.I):
                pages, page = begpage(pages, page, line)
                continue
            if re.search("^[^ \t]+", line):
                sentence = True
            if re.search("[^ \t]", line):
                if newpage:
                    if sentence:
                        stripped += [""]
                else:
                    if haveblank:
                        stripped += [""]
                haveblank = False
                sentence = False
                newpage = False
            if re.search("[.:]$", line):
                sentence = True
            if re.search("^[ \t]*$", line):
                haveblank = True
                page += [ line ]
                continue
            page += [ line ]
            stripped += [ line ]
        pages, page = begpage(pages, page)
        return stripped, pages

    # ----------------------------------------------------------------------
    def get_pagecount(self):
        if self._pagecount == None:
            self._pagecount = len(re.findall("\[[Pp]age [0-9ixldv]+\]", self.text)) or len(self.lines)/58
        return self._pagecount

    # ----------------------------------------------------------------------
    def get_status(self):
        if self._status == None:
            for line in self.lines[:10]:
                status_match = re.search("^\s*Intended [Ss]tatus:\s*(.*?)   ", line)
                if status_match:
                    self._status = status_match.group(1)
                    break
        return self._status

    # ------------------------------------------------------------------
    def get_creation_date(self):
        if self._creation_date:
            return self._creation_date
        month_names = [ 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec' ]
	date_regexes = [
            r'\s{3,}(?P<month>\w+)\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})',
            r'\s{3,}(?P<day>\d{1,2}),?\s+(?P<month>\w+)\s+(?P<year>\d{4})',
            r'\s{3,}(?P<day>\d{1,2})-(?P<month>\w+)-(?P<year>\d{4})',
            # 'October 2008' - default day to today's.
            r'\s{3,}(?P<month>\w+)\s+(?P<year>\d{4})',
        ]

        for regex in date_regexes:
            match = re.search(regex, self.pages[0])
            if match:
		md = match.groupdict()
		mon = md['month'][0:3].lower()
		day = int( md.get( 'day', date.today().day ) )
		year = int( md['year'] )
		try:
		    month = month_names.index( mon ) + 1
		    self._creation_date = date(year, month, day)
                    return self._creation_date
		except ValueError:
		    # mon abbreviation not in _MONTH_NAMES
		    # or month or day out of range
		    pass
        self.errors['creation_date'] = 'Creation Date field is empty or the creation date is not in a proper format.'
        return self._creation_date


    # ------------------------------------------------------------------
    def get_authors(self):
        """Extract author information from draft text.

        """
        if self._authors == None:
            aux = {
                "honor" : r"(?:Dr\.?|Prof(?:\.?|essor)|Sir|Lady|Dame)",
                "prefix": r"([Dd]e|Hadi|van|van de|van der|Ver|von)",
                "suffix": r"(jr|II|2nd|III|3rd|IV|4th)",
                "first" : r"([A-Z][-A-Za-z]*)((\.?[- ]{1,2}[A-Za-z]+)*)",
                "last"  : r"([-A-Za-z']{2,})",
                }
            authformats = [
                r" {6}(%(first)s[ \.]{1,3}((%(prefix)s )?%(last)s)( %(suffix)s)?)([, ]?(.+\.?|\(.+\.?|\)))?$" % aux,
                r" {6}(((%(prefix)s )?%(last)s)( %(suffix)s)?, %(first)s)([, ]([Ee]d\.?|\([Ee]d\.?\)))?$" % aux,
                r" {6}(%(last)s)$" % aux,
                ]

            ignore = [
                "Standards Track", "Current Practice", "Internet Draft", "Working Group",
                "No Affiliation", 
                ]
            # group       12                   34            5            6
            authors = []
            companies = []

            # Collect first-page author information first
            have_blankline = False
            have_draftline = False
            prev_blankline = False
            for line in self.lines[:15]:
                #_debug( "**" + line)
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
                        break
                    for authformat in authformats:
                        match = re.search(authformat, line)
                        if match:
                            author = match.group(1)
                            authors += [ author ]
                            #_debug("\nLine:   " + line)
                            #_debug("Format: " + authformat)
                            _debug("Author: '%s'" % author)
                if line.strip() == "":
                    if prev_blankline:
                        break
                    have_blankline = True
                    prev_blankline = True
                else:
                    prev_blankline = False
                if "draft-" in line:
                    have_draftline = True
                if have_blankline and have_draftline:
                    break

            found_pos = []
            for i in range(len(authors)):
                _debug("1: authors[%s]: %s" % (i, authors[i]))
                author = authors[i]
                if author == None:
                    continue
                if "," in author:
                    last, first = author.split(",",1)
                    author = "%s %s" % (first.strip(), last.strip())
                if not " " in author:
                    if "." in author:
                        first, last = author.rsplit(".", 1)
                        first += "."
                    else:
                        author = "[A-Z].+ " + author
                        first, last = author.rsplit(" ", 1)
                else:
                    first, last = author.rsplit(" ", 1)
                _debug("First, Last: '%s' '%s'" % (first, last))
                for author in [ "%s %s"%(first,last), "%s %s"%(last,first), ]:
                    _debug("\nAuthors: "+str(authors))
                    _debug("Author: "+author)
                    # Pattern for full author information search, based on first page author name:
                    authpat = author
                    # Permit expansion of first name
                    authpat = re.sub("\. ", ".* ", authpat)
                    authpat = re.sub("\.$", ".*", authpat)
                    # Permit insertsion of middle name or initial
                    authpat = re.sub(" ", "\S*( +[^ ]+)* +", authpat)
                    # Permit expansion of double-name initials
                    authpat = re.sub("-", ".*?-", authpat)
                    # Some chinese names are shown with double-letter(latin) abbreviated given names, rather than
                    # a single-letter(latin) abbreviation:
                    authpat = re.sub("^([A-Z])[A-Z]+\.\*", r"\1[-\w]+", authpat) 
                    authpat = "^(?:%s ?)?(%s)( *\(.*\)|,( [A-Z][-A-Za-z0-9]*)?)?" % (aux["honor"], authpat)
                    _debug("Authpat: " + authpat)
                    start = 0
                    col = None
                    # Find start of author info for this author (if any).
                    # Scan from the end of the file, looking for a match to  authpath
                    try:
                        for j in range(len(self.lines)-1, 15, -1):
                            line = self.lines[j].strip()
                            forms = [ line ] + [ line.replace(short, longform[short]) for short in longform if short in line ]
                            for line in forms:
                                try:
                                    if re.search(authpat, line):
                                        start = j
                                        _debug( " ==>   " + line.strip())
                                        # The author info could be formatted in multiple columns...
                                        columns = re.split("(    +)", line)
                                        # _debug( "Columns:" + columns; sys.stdout.flush())
                                        # Find which column:
                                        #_debug( "Col range:" + range(len(columns)); sys.stdout.flush())

                                        cols = [ c for c in range(len(columns)) if re.search(authpat+r"$", columns[c].strip()) ]
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
                                                _debug( "Cut:   '%s'" % line[beg:end])
                                                author = re.search(authpat, columns[col].strip()).group(1)
                                                if author in companies:
                                                    authors[i] = None
                                                else:
                                                    authors[i] = author
                                                #_debug( "Author: %s: %s" % (author, authors[author]))
                                                # We need to exit 2 for loops -- a break isn't sufficient:
                                                raise StopIteration("Found Author")
                                except AssertionError, e:
                                    sys.stderr.write("filename: "+self.filename+"\n")
                                    sys.stderr.write("authpat: "+authpat+"\n")
                                    raise
                    except StopIteration:
                        pass
                    if start and col != None:
                        break
                if not authors[i]:
                    continue
                _debug("2: authors[%s]: %s" % (i, authors[i]))
                if start and col != None:
                    _debug("\n *" + authors[i])
                    done = False
                    count = 0
                    keyword = False
                    blanklines = 0
                    for line in self.lines[start+1:]:
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
                            count += 1                    

                        # Maybe break on author name
        #                 _debug("Line: %s"%line.strip())
        #                 for a in authors:
        #                     if a and a not in companies:
        #                         _debug("Search for: %s"%(r"(^|\W)"+re.sub("\.? ", ".* ", a)+"(\W|$)"))
                        authmatch = [ a for a in authors[i+1:] if a and not a in companies and re.search((r"(^|\W)"+re.sub("\.? ", ".* ", a)+"(\W|$)"), line.strip()) ]
                        if authmatch:
                            _debug("     ? Other author or company ?  : %s" % authmatch)
                            _debug("     Line: "+line.strip())
                            if count == 1 or (count == 2 and not blanklines):
                                # First line after an author -- this is a company
                                companies += authmatch
                                companies += [ line.strip() ] # XXX fix this for columnized author list
                                companies = list(set(companies))
                                _debug("       -- Companies: " + ", ".join(companies))
                                for k in range(i+1, len(authors)):
                                    if authors[k] in companies:
                                        authors[k] = None
                            elif not "@" in line:
                                # Break on an author name
                                _debug( " - Break on other author name")
                                break
                            else:
                                pass

                        try:
                            column = line[beg:end].strip()
                        except:
                            column = line
                        column = re.sub(" *\(at\) *", "@", column)
                        column = re.sub(" *\(dot\) *", ".", column)


        #                 if re.search("^\w+: \w+", column):
        #                     keyword = True
        #                 else:
        #                     if keyword:
        #                         # Break on transition from keyword line to something else
        #                         _debug( " - Break on end of keywords")
        #                         break

                        #_debug( "  Column text :: " + column)
                        _debug("3: authors[%s]: %s" % (i, authors[i]))
                        
                        emailmatch = re.search("[-A-Za-z0-9_.+]+@[-A-Za-z0-9_.]+", column)
                        if emailmatch and not "@" in authors[i]:
                            email = emailmatch.group(0).lower()
                            authors[i] = "%s <%s>" % (authors[i], email)
                else:
                    authors[i] = None
                    if not author in ignore:
                        _debug("Not an author? '%s'" % (author))

            authors = [ re.sub(r" +"," ", a) for a in authors if a != None ]
            authors.sort()
            _debug(" * Final author list: " + ", ".join(authors))
            _debug("-"*72)
            self._authors = authors

        return self._authors

# ----------------------------------------------------------------------
def _output(fields):
    if opt_timestamp:
        sys.stdout.write("%s " % (fields["eventdate"]))
    sys.stdout.write("%s" % (fields["doctag"].strip()))

    def outputkey(key, fields):
        sys.stdout.write(" %s='%s'" % ( key.lower(), fields[key].strip().replace("\\", "\\\\" ).replace("'", "\\x27" ).replace("\n", "\\n")))

    keys = fields.keys()
    keys.sort()
    for key in keys:
        if fields[key] and not key in ["doctag", "eventdate"]:
            outputkey(key, fields)
    sys.stdout.write("\n")

# ----------------------------------------------------------------------
def _printmeta(timestamp, fn):
    # Initial values
    fields = {}
    fields["eventdate"] = timestamp
    fields["eventsource"] = "draft"

    if " " in fn or not fn.endswith(".txt"):
        _warn("Skipping unexpected draft name: '%s'" % (fn))
        return

    filename = os.path.join("/www/tools.ietf.org/id", fn)
    if not os.path.exists(filename):
        _warn("Could not find file: '%s'" % (filename))
        return

    if opt_trace:
        t = time.time()
        sys.stderr.write("%-58s" % fn[:-4])

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(os.stat(filename)[stat.ST_MTIME]))
    text = _gettext(filename)
    draft = Draft(text)

    fields["eventdate"] = timestamp
    fields["doctag"] = draft.filename or fn[:-7]
    fields["docrev"] = draft.revision

    fields["docpages"] = str(draft.get_pagecount())
    fields["docauthors"] = ", ".join(draft.get_authors())
    deststatus = draft.get_status()
    if deststatus:
        fields["docdeststatus"] = deststatus

    _output(fields)

    if opt_trace:
        sys.stderr.write("%5.1f\n" % ((time.time() - t)))

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def _main():
    global opt_debug, opt_timestamp, opt_trace, files
    # set default values, if any
    # ----------------------------------------------------------------------
    # Option processing
    # ----------------------------------------------------------------------
    options = ""
    for line in re.findall("\n +(if|elif) +opt in \[(.+)\]:\s+#(.+)\n", open(sys.argv[0]).read()):
        if not options:
            options += "OPTIONS\n"
        options += "        %-16s %s\n" % (line[1].replace('"', ''), line[2])
    options = options.strip()

    # with ' < 1:' on the next line, this is a no-op:
    if len(sys.argv) < 1:
        vars = globals()
        vars.update(locals())
        print __doc__ % vars
        sys.exit(1)

    try:
        opts, files = getopt.gnu_getopt(sys.argv[1:], "dhtTv", ["debug", "help", "timestamp", "trace", "version",])
    except Exception, e:
        print "%s: %s" % (program, e)
        sys.exit(1)

    # parse options
    for opt, value in opts:
        if   opt in ["-d", "--debug"]:  # Output debug information
            opt_debug = True
        elif opt in ["-h", "--help"]:   # Output this help text, then exit
            vars = globals()
            vars.update(locals())
            print __doc__ % vars
            sys.exit(1)
        elif opt in ["-v", "--version"]: # Output version information, then exit
            print program, version
            sys.exit(0)
        elif opt in ["-t", "--timestamp"]: # Emit leading timestamp information 
            opt_timestamp = True
        elif opt in ["-T", "--trace"]: # Emit trace information while working
            opt_trace = True

    if not files:
        files = [ "-" ]

    for file in files:
        _debug( "Reading drafts from '%s'" % file)
        if file == "-":
            file = sys.stdin
        elif file.endswith(".gz"):
            file = gzip.open(file)
        else:
            file = open(file)

        if os.path.exists(file.name):
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(os.stat(file.name)[stat.ST_MTIME]))
        else:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())

        basename = os.path.basename(file.name)
        if basename.startswith("draft-"):
            draft = basename
            _debug( "** Processing '%s'" % draft)
            _printmeta(timestamp, draft)
        else:
            for line in file:
                draft = line.strip()
                if draft.startswith("#"):
                    continue
                _debug( "** Processing '%s'" % draft)
                _printmeta(timestamp, draft)

if __name__ == "__main__":
    try:
        _main()
    except KeyboardInterrupt:
        raise
        pass
