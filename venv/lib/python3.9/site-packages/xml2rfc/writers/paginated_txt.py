# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

# Python libs
import calendar

try:
    import debug
    assert debug
except ImportError:
    pass

# Local libs
from xml2rfc.writers.base import BaseRfcWriter, default_options
from xml2rfc.writers.raw_txt import RawTextRfcWriter
import xml2rfc.utils
import xml2rfc.log

class PaginatedTextRfcWriter(RawTextRfcWriter):
    """ Writes to a text file, paginated with headers and footers

        The page width is controlled by the *width* parameter.
    """

    def __init__(self, xmlrfc, width=72, quiet=None, options=default_options,
                               date=None, omit_headers=False):
        if not quiet is None:
            options.quiet = quiet
        RawTextRfcWriter.__init__(self, xmlrfc, options=options, date=date)
        self.left_header = ''
        self.center_header = ''
        self.right_header = ''
        self.left_footer = ''
        self.center_footer = ''
        self.break_hints = {}
        self.heading_marks = {}
        self.paged_toc_marker = 0
        self.page_line = 0
        self.omit_headers = omit_headers
        self.page_end_blank_lines = 2
        # Don't permit less than this many lines of a broken paragraph at the
        # top of a page:
        self.widow_limit = self.get_numeric_pi('widowlimit', default=2)
        # Don't permit less than this many lines of a broken paragraph at the
        # bottom of a page:
        self.orphan_limit = self.get_numeric_pi('orphanlimit', default=2)

    def _make_footer_and_header(self, page, final=False):
        tmp = []
        tmp.append(xml2rfc.utils.justify_inline(self.left_footer,
                                                self.center_footer,
                                                '[Page ' + str(page) + ']'))
        if not final:
            tmp.append('\f')
            tmp.append(xml2rfc.utils.justify_inline(self.left_header,
                                                    self.center_header,
                                                    self.right_header))
        return tmp

    def _vspace(self, num=0):
        """ <vspace> needs to allow for forcing page breaks """
        if num > 51:
            self._set_break_hint(-1, 'break')
            num = 1
        self._lb(num=num)
            
    def _set_break_hint(self, needLines, type, where=-1):
        """ Use this function to set break hints since it will do all of the
            necessary checks to see that we don't override a stronger hint
        """
        if where == -1:
            where = len(self.buf)
        if where in self.break_hints:
            need, ptype = self.break_hints[where]
            if ptype == 'break':
                # breaks always win
                return
            if ptype == 'raw':
                # raw is better than text
                type = ptype
            # Extend the number of lines if greater
            if need > needLines:
                needLines = need
        self.break_hints[where] = (needLines, type)
            

    def write_with_break_hint(self, writer, type, *args, **kwargs):
        """A helper function to wrap a fragment writer in code to a page break
        hint.  This function also takes care to preserve a stronger break type
        so that it's not overwritten with a weaker one."""
        begin = len(self.buf)
        writer(self, *args, **kwargs)
        needLines = len(self.buf) - begin
        for line in self.buf[begin:]:
            if self.IsFormatting(line):
                needLines -= 1
        self._set_break_hint(needLines, type, begin)

    def needLines(self, count):
        """Deal with the PI directive needLines"""
        if isinstance(count, str):
            if count.isdigit():
                count = int(count)
            else:
                xml2rfc.log.warn('Expected a numeric value for needLines, but got "%s".  Using 3.' % count)
                count = 3
        try:
            if count < 0:
                self._set_break_hint(1, 'break', len(self.buf))
            else:
                self._set_break_hint(count, 'raw', len(self.buf))
        except ValueError as e:
            if not self.indexmode:
                xml2rfc.log.warn('%s, in processing instruction needlines="%s"' % (str(e).capitalize(), count))

    # Here we override some methods to mark line numbers for large sections.
    # We'll store each marking as a dictionary of line_num: section_length.
    # This way we can step through these markings during writing to
    # preemptively construct appropriate page breaks.
    # Only those things which are supposed to be widowed or orphaned use 'txt'
    def write_figure(self, *args, **kwargs):
        """ Override base writer to add a marking """
        self.write_with_break_hint(BaseRfcWriter.write_figure, 'raw', *args, **kwargs)

    def write_table(self, *args, **kwargs):
        """ Override base writer to add a marking """
        self.write_with_break_hint(BaseRfcWriter.write_table, 'raw', *args, **kwargs)

    def write_raw(self, *args, **kwargs):
        """ Override text writer to add a marking """
        self.write_with_break_hint(RawTextRfcWriter.write_raw, 'raw', *args, **kwargs)

    def write_text(self, *args, **kwargs):
        """ Override text writer to add a marking """
        self.write_with_break_hint(RawTextRfcWriter.write_text, 'txt', *args, **kwargs)

    def write_ref_element(self, *args, **kwargs):
        """ Override text writer to add a marking """
        self.write_with_break_hint(RawTextRfcWriter.write_ref_element, 'raw', *args, **kwargs)
        
    def _force_break(self):
        """ Force a pagebreak at the current buffer position. Not used yet, waiting
        for markup that indicates a forced page break to be defined"""
        self._set_break_hint(-1, 'break', len(self.buf))
        
    def _toc_size_hint(self):
        return len(self.write_toc(paging=True))
    
    def _iref_size_hint(self):
        return len(self.write_iref_index())

    
    # ------------------------------------------------------------------------
    
    def write_heading(self, text, bullet='', autoAnchor=None, anchor=None, \
                      level=1):
        # Store the line number of this heading with its unique anchor, 
        # to later create paging info
        begin = len(self.buf)
        self.heading_marks[begin] = autoAnchor
        RawTextRfcWriter.write_heading(self, text, bullet=bullet, \
                                       autoAnchor=autoAnchor, anchor=anchor, \
                                       level=level)
        # Reserve room for a blankline and some lines of section content
        # text, in order to prevent orphan headings
        #
        # We've now written a blank line before the heading, followed by
        # the heading.  Next will be a blank line, followed by the section
        # content.  We thus need (begin - end) + 1 + orphan_limit lines, but
        # if we ask for only that, we'll end up moving the text, to the next
        # page, without moving the section heading.  So we ask for one more
        self.orphan_limit = self.get_numeric_pi('orphanlimit', default=self.orphan_limit)
        orphanlines = self.get_numeric_pi('sectionorphan', default=self.orphan_limit+2)
        end = len(self.buf)
        needed = end - begin + orphanlines
        self._set_break_hint(needed, 'raw', begin)


    def pre_rendering(self):
        """ Prepares the header and footer information """
        # Raw textwriters preprocessing will replace unicode with safe ascii
        RawTextRfcWriter.pre_rendering(self)

        # Discard hints and marks from indexing pass
        self.break_hints = {}
        self.heading_marks = {}

        if self.pis['private']:
            self.left_header = ''
        elif self.draft:
            self.left_header = 'Internet-Draft'
        else:
            self.left_header = 'RFC %s' % self.r.attrib.get('number', '')
        title = self.r.find('front/title')
        if title is not None:
            self.center_header = title.attrib.get('abbrev', title.text)
        date = self.r.find('front/date')
        if date is not None:
            month = date.attrib.get('month', '')
            if month.isdigit():
                month = calendar.month_name[int(month)]
            year = date.attrib.get('year', '')
            self.right_header = month + ' ' + year
        authors = self.r.findall('front/author')
        surnames = list(filter(None, [ a.get('asciiSurname', a.get('surname')) for a in authors ]))
        if len(surnames) == 1:
            self.left_footer = surnames[0]
        elif len(surnames) == 2:
            self.left_footer = '%s & %s' % (surnames[0], surnames[1],)
        elif len(surnames) > 2:
            self.left_footer = '%s, et al.' % surnames[0]
        if self.draft:
            self.center_footer = 'Expires %s' % self.expire_string
        else:
            self.center_footer = self.boilerplate.get(
                                 self.r.attrib.get('category', ''), '(Category')

        # Check for PI override
        self.center_footer = self.pis.get('footer', self.center_footer)
        self.left_header = self.pis.get('header', self.left_header)

    def page_break(self, final=False):
        # remove header if nothing on the page
        if final and self.page_length == 1:
            while len(self.output) > 0:
                p = self.output.pop()
                if p == '\f':
                    break;
            return
        if self.omit_headers:
            self.output.append('\f')
        else:
            self.output.append('')
            self.output.append('')
            self.output.append('')
            self.output.extend(self._make_footer_and_header(self.page_num, final))
        if not final:
            self.output.append('')
            self.output.append('')

        self.page_length = 1
        self.page_num += 1

    def emit(self, text):
        """Write text to the output buffer if it's not just a blank
           line at the top of the page"""
        if isinstance(text, type('')) or isinstance(text, type(u'')):
            if self.page_length == 1 and text.strip() in ['', u'']:
                return 
            self.output.append(text)
            self.page_length += 1
        elif isinstance(text, list):
            if self.page_length == 1:
                for line in text:
                    self.emit(line)
                return
            self.output.extend(text)
            self.page_length += len(text)
        else:
            raise TypeError("a string or a list of strings is required")

    def IsFormatting(self, line):
        return False

    def post_rendering(self):
        """ Add paging information to a secondary buffer """
        # Counters    
        self.page_length = 0
        self.page_num = 1
        max_page_length = 51
        lines_until_break = -1


        # Maintain a list of (start, end) pointers for elements to re-insert
        toc_pointers = []
        toc_prev_start = 0     
        iref_pointers = []
        iref_prev_start = 0

        for line_num, line in enumerate(self.buf):
            if line_num == self.toc_marker and self.toc_marker > 0:
                # Don't start ToC too close to the end of the page
                if self.pis['tocpagebreak'] == 'yes' or self.page_length + 10 >= max_page_length:
                    remainder = max_page_length - self.page_length - self.page_end_blank_lines
                    self.emit([''] * remainder)
                    self.page_break()

                # Insert a dummy table of contents here
                toc_prev_start = len(self.output)
                preliminary_toc = self.write_toc(paging=True)
                for l in preliminary_toc:
                    if self.page_length + self.page_end_blank_lines >= max_page_length:
                        # Store a pair of TOC pointers
                        toc_pointers.append((toc_prev_start, len(self.output)))
                        # New page
                        self.page_break()
                        toc_prev_start = len(self.output)
                    # Write dummy line
                    self.emit(l)
                # Store last pair of toc pointers
                toc_pointers.append((toc_prev_start, len(self.output)))
                
            if line_num == self.iref_marker and self.iref_marker > 0:
                # Don't start Index too close to the end of the page
                if self.page_length + 10 >= max_page_length:
                    remainder = max_page_length - self.page_length - self.page_end_blank_lines
                    self.emit([''] * remainder)
                    self.page_break()

                # Add page number for index
                item = self._getItemByAnchor('rfc.index')
                if item:
                    item.page = self.page_num
                # Insert a dummy iref here
                iref_prev_start = len(self.output)
                preliminary_iref_index = self.write_iref_index()
                for l in preliminary_iref_index:
                    if self.page_length + self.page_end_blank_lines >= max_page_length:
                        # Store a pair of pointers
                        iref_pointers.append((iref_prev_start, len(self.output)))
                        # New page
                        self.page_break()
                        iref_prev_start = len(self.output)
                    # Write dummy line
                    self.emit(l)
                # Store last pair of pointers
                iref_pointers.append((iref_prev_start, len(self.output)))

            if line_num in self.break_hints:
                # If this size hint exceeds the rest of the page, or is set
                # to -1 (a forced break), insert a break.

                available = max_page_length - (self.page_length + self.page_end_blank_lines)
                needed, text_type = self.break_hints[line_num]

                blanks = 0
                i = 0
                while ((line_num+i < len(self.buf)) and
		       (self.buf[line_num+i].strip() == "" or
                        self.IsFormatting(self.buf[line_num+i]))):
                    if not self.IsFormatting(self.buf[line_num+i]):
                        blanks += 1
                    i += 1
                if blanks > 0:
                    # discount initial blank line in what we're about to
                    # write when considering whether we're about to create
                    # orphans or widows
                    available -= blanks
                    needed -= blanks

                if (text_type == "break"
                    or (text_type == "raw" and needed > available and needed < max_page_length-self.page_end_blank_lines )):
                    lines_until_break = 0

                elif (self.pis['autobreaks'] == 'yes'
                      and needed > available
                      and needed < max_page_length-self.page_end_blank_lines
                      and (needed-available < self.widow_limit or available < self.orphan_limit) ):
                    lines_until_break = available
                    if available == needed - 1:
                        lines_until_break -= 1
                    if lines_until_break < self.page_end_blank_lines:
                        lines_until_break = 0
                    if lines_until_break > 0 and blanks > 0:
                        # put back that blank line since we are going to emit it
                        lines_until_break += blanks

            if lines_until_break == 0:
                # Insert break
                remainder = max_page_length - self.page_length - self.page_end_blank_lines
                self.emit([''] * remainder)
            if not self.IsFormatting(line):
                lines_until_break -= 1

            if self.page_length + self.page_end_blank_lines >= max_page_length:
                # New page
                self.page_break()

            self.emit(line)

            # Store page numbers for any marked elements
            if line_num in self.heading_marks:
                item = self._getItemByAnchor(self.heading_marks[line_num])
                if item:
                    item.page = self.page_num
            if line_num in self.iref_marks:
                for item, subitem in self.iref_marks[line_num]:
                    # Store pages in item unless there are subitems
                    if subitem:
                        self._iref_index[item].subitems[subitem].pages.append(self.page_num)
                    else:
                        self._iref_index[item].pages.append(self.page_num)

        # Write final footer
        if self.page_length > 1:
            remainder = max_page_length - self.page_length - self.page_end_blank_lines
            self.emit([''] * remainder)
        self.page_break(final=True)
        
        # Now we need to go back into the buffer and insert the real table 
        # of contents and iref based on the pointers we created
        if len(toc_pointers) > 0:
            tocbuf = self.write_toc(paging=True)
            ptr, end = toc_pointers.pop(0)
            for line in tocbuf:
                if self.output[ptr] != '' and line == '':
                    continue
                self.output[ptr] = line
                ptr += 1
                if ptr >= end:
                    if len(toc_pointers) > 0:
                        ptr, end = toc_pointers.pop(0)
                    else:
                        break

        if len(iref_pointers) > 0:
            irefbuf = self.write_iref_index()
            ptr, end = iref_pointers.pop(0)
            for line in irefbuf:
                if self.output[ptr] != '' and line == '':
                    continue
                self.output[ptr] = line
                ptr += 1
                if ptr >= end:
                    if len(iref_pointers) > 0:
                        ptr, end = iref_pointers.pop(0)
                    else:
                        break

    def post_process_lines(self, lines):
        return RawTextRfcWriter.post_process_lines(self, lines)
