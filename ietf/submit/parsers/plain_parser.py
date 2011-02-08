import datetime
import re

from ietf.idtracker.models import InternetDraft, IETFWG
from ietf.submit.error_manager import MainErrorManager
from ietf.submit.parsers.base import FileParser

MAX_PLAIN_FILE_SIZE = 6000000
NONE_WG_PK = 1027


class PlainParser(FileParser):

    def __init__(self, fd):
        super(PlainParser, self).__init__(fd)
        self.lines = fd.file.readlines()
        fd.file.seek(0)
        self.full_text = self.normalize_text(''.join(self.lines))

    def normalize_text(self, text):
        text = re.sub(".\x08", "", text)    # Get rid of inkribbon backspace-emphasis
        text = text.replace("\r\n", "\n")   # Convert DOS to unix
        text = text.replace("\r", "\n")     # Convert MAC to unix
        text = text.strip()
        return text

    def parse_critical_000_max_size(self):
        if self.fd.size > MAX_PLAIN_FILE_SIZE:
            self.parsed_info.add_error(MainErrorManager.get_error_str('EXCEEDED_SIZE'))
        self.parsed_info.metadraft.filesize = self.fd.size
        self.parsed_info.metadraft.submission_date = datetime.date.today()

    def parse_critical_001_file_charset(self):
        import magic
        self.fd.file.seek(0)
        m = magic.open(magic.MAGIC_MIME)
        m.load()
        filetype = m.buffer(self.fd.file.read())
        if not 'ascii' in filetype:
            self.parsed_info.add_error('A plain text document must be submitted.')

    def parse_critical_002_filename(self):
        self.fd.file.seek(0)
        draftre = re.compile('(draft-\S+)')
        revisionre = re.compile('.*-(\d+)$')
        limit = 80
        while limit:
            limit -= 1
            line = self.fd.readline()
            match = draftre.search(line)
            if not match:
                continue
            filename = match.group(1)
            filename = re.sub('^[^\w]+', '', filename)
            filename = re.sub('[^\w]+$', '', filename)
            filename = re.sub('\.txt$', '', filename)
            extra_chars = re.sub('[0-9a-z\-]', '', filename)
            if extra_chars:
                self.parsed_info.add_error('Filename contains non alpha-numeric character: %s' % ', '.join(set(extra_chars)))
            match_revision = revisionre.match(filename)
            if match_revision:
                self.parsed_info.metadraft.revision = match_revision.group(1)
            filename = re.sub('-\d+$', '', filename)
            self.parsed_info.metadraft.filename = filename
            return
        self.parsed_info.add_error(MainErrorManager.get_error_str('INVALID_FILENAME'))

    def parse_critical_003_wg(self):
        filename = self.parsed_info.metadraft.filename
        try:
            existing_draft = InternetDraft.objects.get(filename=filename)
            self.parsed_info.metadraft.wg = existing_draft.group
        except InternetDraft.DoesNotExist:
            if filename.startswith('draft-ietf-'):
                # Extra check for WG that contains dashes
                for group in IETFWG.objects.filter(group_acronym__acronym__contains='-'):
                    if filename.startswith('draft-ietf-%s-' % group.group_acronym.acronym):
                        self.parsed_info.metadraft.wg = group
                        return
                group_acronym = filename.split('-')[2]
                try:
                    self.parsed_info.metadraft.wg = IETFWG.objects.get(group_acronym__acronym=group_acronym)
                except IETFWG.DoesNotExist:
                    self.parsed_info.add_error('Invalid WG ID: %s' % group_acronym)
            else:
                self.parsed_info.metadraft.wg = IETFWG.objects.get(pk=NONE_WG_PK)

    def parse_normal_000_first_two_pages(self):
        first_pages = ''
        for line in self.lines:
            first_pages += line
            if re.search('\[[Pp]age 2', line):
                break
        self.parsed_info.metadraft.first_two_pages = self.normalize_text(first_pages)

    def parse_normal_001_title(self):
        pages = self.parsed_info.metadraft.first_two_pages or self.full_text
        title_re = re.compile('(.+\n){1,3}(\s+<?draft-\S+\s*\n)')
        match = title_re.search(pages)
        if match:
            title = match.group(1)
            title = title.strip()
            self.parsed_info.metadraft.title = title
            return
        # unusual title extract
        unusual_title_re = re.compile('(.+\n|.+\n.+\n)(\s*status of this memo\s*\n)', re.I)
        match = unusual_title_re.search(pages)
        if match:
            title = match.group(1)
            title = title.strip()
            self.parsed_info.metadraft.title = title

    def parse_normal_002_num_pages(self):
        pagecount = len(re.findall("\[[Pp]age [0-9ixldv]+\]", self.full_text)) or len(self.lines) / 58
        self.parsed_info.metadraft.pagecount = pagecount

    def parse_normal_003_creation_date(self):
        month_names = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        date_regexes = [
            r'\s{3,}(?P<month>\w+)\s+(?P<day>\d{1,2}),?\s+(?P<year>\d{4})',
            r'\s{3,}(?P<day>\d{1,2}),?\s+(?P<month>\w+)\s+(?P<year>\d{4})',
            r'\s{3,}(?P<day>\d{1,2})-(?P<month>\w+)-(?P<year>\d{4})',
            # 'October 2008' - default day to today's.
            r'\s{3,}(?P<month>\w+)\s+(?P<year>\d{4})',
        ]

        first = self.parsed_info.metadraft.first_two_pages or self.full_text
        for regex in date_regexes:
            match = re.search(regex, first)
            if match:
                md = match.groupdict()
                mon = md['month'][0:3].lower()
                day = int(md.get('day', datetime.date.today().day))
                year = int(md['year'])
                try:
                    month = month_names.index(mon) + 1
                    self.parsed_info.metadraft.creation_date = datetime.date(year, month, day)
                    return
                except ValueError:
                    # mon abbreviation not in _MONTH_NAMES
                    # or month or day out of range
                    continue
            self.parsed_info.add_warning('creation_date', 'Creation Date field is empty or the creation date is not in a proper format.')

    def parse_normal_004_authors(self):
        """
        comes from http://svn.tools.ietf.org/svn/tools/ietfdb/branch/idsubmit/ietf/utils/draft.py
        """

        def _stripheaders(rawlines):
            stripped = []
            pages = []
            page = []
            line = ""
            debug = False
            newpage = False
            sentence = False
            haveblank = False

            def endpage(pages, page, line):
                if line:
                    page += [line]
                return begpage(pages, page)

            def begpage(pages, page, line=None):
                if page and len(page) > 5:
                    pages += ["\n".join(page)]
                    page = []
                    newpage = True
                if line:
                    page += [line]
                return pages, page

            for line in rawlines:
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
                    page += [line]
                    continue
                page += [line]
                stripped += [line]
            pages, page = begpage(pages, page)
            return stripped, pages

        self.fd.file.seek(0)
        raw_lines = self.fd.file.read().split("\n")
        draft_lines, draft_pages = _stripheaders(raw_lines)

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
            "Ted": "Edward",
        }
        aux = {
            "honor": r"(?:Dr\.?|Prof(?:\.?|essor)|Sir|Lady|Dame)",
            "prefix": r"([Dd]e|Hadi|van|van de|van der|Ver|von)",
            "suffix": r"(jr|II|2nd|III|3rd|IV|4th)",
            "first": r"([A-Z][-A-Za-z]*)((\.?[- ]{1,2}[A-Za-z]+)*)",
            "last": r"([-A-Za-z']{2,})",
        }
        authformats = [
            r" {6}(%(first)s[ \.]{1,3}((%(prefix)s )?%(last)s)( %(suffix)s)?)([, ]?(.+\.?|\(.+\.?|\)))?$" % aux,
            r" {6}(((%(prefix)s )?%(last)s)( %(suffix)s)?, %(first)s)([, ]([Ee]d\.?|\([Ee]d\.?\)))?$" % aux,
            r" {6}(%(last)s)$" % aux,
        ]

        authors = []
        companies = []

        # Collect first-page author information first
        have_blankline = False
        have_draftline = False
        prev_blankline = False
        for line in draft_lines[:15]:
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
                        authors += [author]
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
            author = authors[i]
            if author == None:
                continue
            if "," in author:
                last, first = author.split(",", 1)
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

            for author in ["%s %s" % (first, last), "%s %s" % (last, first)]:
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
                start = 0
                col = None

                # Find start of author info for this author (if any).
                # Scan from the end of the file, looking for a match to  authpath
                try:
                    for j in range(len(draft_lines) - 1, 15, -1):
                        line = draft_lines[j].strip()
                        forms = [line] + [line.replace(short, longform[short]) for short in longform if short in line]
                        for line in forms:
                            if re.search(authpat, line):
                                start = j
                                columns = re.split("(    +)", line)
                                # Find which column:
                                cols = [c for c in range(len(columns)) if re.search(authpat + r"$", columns[c].strip())]
                                if cols:
                                    col = cols[0]
                                    if not (start, col) in found_pos:
                                        found_pos += [(start, col)]
                                        beg = len("".join(columns[:col]))
                                        if col == len(columns) or col == len(columns) - 1:
                                            end = None
                                        else:
                                            end = beg + len("".join(columns[col:col + 2]))
                                        author = re.search(authpat, columns[col].strip()).group(1)
                                        if author in companies:
                                            authors[i] = None
                                        else:
                                            authors[i] = author

                                        raise StopIteration("Found Author")
                except StopIteration:
                    pass
                if start and col != None:
                    break
            if not authors[i]:
                continue

            if start and col != None:
                done = False
                count = 0
                keyword = False
                blanklines = 0
                for line in draft_lines[start + 1:]:
                    # Break on the second blank line
                    if not line:
                        blanklines += 1
                        if blanklines >= 3:
                            break
                        else:
                            continue
                    else:
                        count += 1
                    authmatch = [a for a in authors[i + 1:] if a and not a in companies and re.search((r"(^|\W)" + re.sub("\.? ", ".* ", a) + "(\W|$)"), line.strip())]
                    if authmatch:
                        if count == 1 or (count == 2 and not blanklines):
                            # First line after an author -- this is a company
                            companies += authmatch
                            companies += [line.strip()]  # XXX fix this for columnized author list
                            companies = list(set(companies))
                            for k in range(i + 1, len(authors)):
                                if authors[k] in companies:
                                    authors[k] = None
                        elif not "@" in line:
                            break
                        else:
                            pass

                    try:
                        column = line[beg:end].strip()
                    except:
                        column = line
                    column = re.sub(" *\(at\) *", "@", column)
                    column = re.sub(" *\(dot\) *", ".", column)

                    emailmatch = re.search("[-A-Za-z0-9_.+]+@[-A-Za-z0-9_.]+", column)
                    if emailmatch and not "@" in authors[i]:
                        email = emailmatch.group(0).lower()
                        authors[i] = "%s <%s>" % (authors[i], email)
            else:
                authors[i] = None

        authors = [re.sub(r" +", " ", a) for a in authors if a != None]
        if authors:
            authors.sort()
            self.parsed_info.metadraft.authors = authors
        else:
            self.parsed_info.errors.append("Draft authors could not be found.")

        return authors

    def parse_normal_005_abstract(self):
        pass
