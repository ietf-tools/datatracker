# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

# Python libs
import textwrap
import lxml
import re

try:
    from xml2rfc import debug
    assert debug
except ImportError:
    pass

# Local lib
from xml2rfc.writers.base import BaseRfcWriter, default_options
from xml2rfc.util.unicode import expand_unicode_element
import xml2rfc.utils


class RawTextRfcWriter(BaseRfcWriter):
    """ Writes to a text file, unpaginated, no headers or footers.

        The page width is controlled by the *width* parameter.
    """

    def __init__(self, xmlrfc, width=72, margin=3, quiet=None, options=default_options, date=None):
        if not quiet is None:
            options.quiet = quiet
        BaseRfcWriter.__init__(self, xmlrfc, options=options, date=date)
        # Document processing data
        self.width = width      # Page width
        self.margin = margin    # Page margin
        self.buf = []           # Main buffer during processing
        self.output = []        # Final buffer that gets written to disk
        self.toc_marker = 0     # Line number in buffer to write toc to
        self.iref_marker = 0    # Line number in buffer to write index to
        self.list_counters = {} # Maintain counters for 'format' type lists
        self.edit_counter = 0   # Counter for edit marks
        # Set this to False to permit utf+8 output:
        self.ascii = not options.utf8       # Enable ascii flag
        self.cref_counter = 0   # Counter for cref anchors
        self.cref_list = []

        # Marks position of iref elements
        self.iref_marks = {}

        # Text lookups
        self.inline_tags = ['xref', 'eref', 'iref', 'cref', 'spanx', 'u', ]
        
        # Custom textwrapper object
        self.wrapper = xml2rfc.utils.TextWrapper(width=self.width,
                                                   fix_sentence_endings=True)

    def _length(self, text):
        return len(text)

    def _lb(self, buf=None, text='', num=1):
        """ Write a blank line to the file, with optional filler text 
        
            Filler text is usually used by editing marks
        """
        if num > 0:
            if buf is None:
                buf = self.buf
            buf.extend([text] * num)

    def _vspace(self, num=0):
        """ <vspace> line break wrapper to allow for overrides """
        return self._lb(num=num)

    def write_text(self, string, indent=0, sub_indent=0, bullet='',
                  align='left', leading_blankline=False, buf=None,
                  strip=True, edit=False, wrap_urls=True,
                  fix_sentence_endings=True, source_line=None,
                  fix_doublespace=True):
        """ Writes a line or multiple lines of text to the buffer.

            Several parameters are included here.  All of the API calls
            for text writers use this as the underlying method to write data
            to the buffer, with the exception of write_raw() that handles
            preserving of whitespace.
        """
        if buf is None:
            buf = self.buf

        if leading_blankline:
            if edit and self.pis['editing'] == 'yes':
                # Render an editing mark
                self.edit_counter += 1
                self._lb(buf=buf, text=str('<' + str(self.edit_counter) + '>'))
            else:
                self._lb(buf=buf)

        # We can take advantage of textwrap's initial_indent by using a bullet
        # parameter and treating it separately.  We still need to indent it.
        subsequent = ' ' * (indent + sub_indent)
        if bullet:
            initial = ' ' * indent
            bullet_parts = self.wrapper.wrap(bullet, initial=initial,
                                             fix_doublespace=False, drop_whitespace=False)
            if len(bullet_parts) > 1:
                buf.extend(bullet_parts[:-1])
            initial = bullet_parts[-1]
            if not sub_indent:
                # Use bullet length for subsequent indents
                subsequent = ' ' * len(initial)
        else:
            # No bullet, so combine indent and sub_indent
            initial = subsequent

        if string:
            if strip:
                # Strip initial whitespace
                string = string.lstrip()
            if wrap_urls:
                par = self.wrapper.wrap(string, initial=initial, subsequent_indent=subsequent,
                                        fix_sentence_endings=fix_sentence_endings,
                                        fix_doublespace=fix_doublespace)
            else:
                par = self.wrapper.wrap(xml2rfc.utils.urlkeep(string), initial=initial,
                                        subsequent_indent=subsequent,
                                        fix_sentence_endings=fix_sentence_endings,
                                        fix_doublespace=fix_doublespace)
            if len(par) == 0 and bullet:
                par = [ initial ]                    
            if align == 'left':
                buf.extend(par)
            elif align == 'center':
                for line in par:
                    margin = ' ' * indent
                    if line.startswith(margin):
                        line = line.rstrip()
                        centered = ' ' * ((self.width - len(line.rstrip()))//2)
                        centered += line
                        # centered = margin + line[len(margin):].center(self.width-indent-4).rstrip()
                        buf.append(centered)
                    else:
                        buf.append(line.center(self.width).rstrip())
            elif align == 'right':
                for line in par:
                    buf.append(line.rjust(self.width))
        elif bullet:
            # If the string is empty but a bullet was declared, just
            # print the bullet
            buf.append(initial)

    def write_list(self, list, level=0, indent=3):
        """ Writes a <list> element """
        bullet = '   '
        hangIndent = None
        # style comes from the node if one exists
        style = list.attrib.get('style', '')
        if not style:
            # otherwise look for the nearest list parent with a style and use it
            for parent in list.iterancestors():
                if parent.tag == 'list':
                    style = parent.attrib.get('style', '')
                    if style:
                        break
        if not style:
            style = 'empty'
        listlength = len(list.findall('t'))        
        if style == 'hanging' or style.startswith('format'):
            # Check for optional hangIndent
            try:
                hangIndent = list.attrib.get('hangIndent', None)
                if hangIndent != None:
                    hangIndent = int(hangIndent)
            except (ValueError, TypeError):
                xml2rfc.log.error("hangIndent value '%s' is not an integer" % hangIndent)
                hangIndent = 6
        format_str = None
        counter_index = None
        if style.startswith('format'):
            format_str = style.partition('format ')[2]
            allowed_formats = ('%c', '%C', '%d', '%i', '%I', '%o', '%x', '%X')
            if not any(map(lambda format: format in format_str, allowed_formats)):
                xml2rfc.log.warn('Invalid format specified: %s ' 
                                 '(Must be one of %s)' % (style,
                                    ', '.join(allowed_formats)))
            counter_index = list.attrib.get('counter', None)
            if not counter_index:
                counter_index = 'temp' + str(level)
                self.list_counters[counter_index] = 0
            elif counter_index not in self.list_counters:
                # Initialize if we need to
                self.list_counters[counter_index] = 0
        t_count = 0
        for element in list:
            # Check for PI
            if element.tag is lxml.etree.PI:
                pidict = self.parse_pi(element)
                if pidict and "needLines" in pidict:
                    self.needLines(pidict["needLines"])
            elif element.tag == 't':
                # Disable linebreak if subcompact=yes AND not first list element
                leading_blankline = True
                if t_count > 0 and element.pis['subcompact'] == 'yes':
                    leading_blankline = False
                if style == 'symbols':
                    bullet = element.pis['text-list-symbols'][level % len(element.pis['text-list-symbols'])]
                    bullet += '  '
                elif style == 'numbers':
                    bullet = self._format_counter("%d.", t_count+1, listlength)
                elif style == 'letters':
                    letter_style = "%C." if (level % 2) else "%c."
                    bullet = self._format_counter(letter_style, t_count+1, listlength)
                elif style == 'hanging':
                    bullet = element.attrib.get('hangText', '')
                    if hangIndent is None:
                        hangIndent = 3
                    if len(bullet) < hangIndent:
                        # Insert whitespace up to hangIndent
                        bullet = bullet.ljust(hangIndent)
                    else:
                        # Insert a single space
                        bullet += '  '
                    # Add an extra space in front of colon if colonspace enabled
                    if bullet.endswith(':') and \
                    element.pis['colonspace'] == 'yes':
                        bullet+= ' '
                    if element.text and len(bullet) > self.width//2:
                        # extra check of remaining space if the bullet is
                        # very long
                        first_word = self.wrapper._split(element.text)[0]
                        if len(first_word) > (self.width - len(bullet) - indent):
                            self.write_text('', bullet=bullet, indent=indent,
                                leading_blankline=leading_blankline)
                            self._vspace()
                            leading_blankline=False
                            indent = hangIndent
                            bullet = ''
                elif style.startswith('format'):
                    self.list_counters[counter_index] += 1
                    count = self.list_counters[counter_index]
                    bullet = self._format_counter(format_str, count, listlength)
                if hangIndent:
                    sub_indent = hangIndent
                else:
                    sub_indent = len(bullet)
                anchor = element.attrib.get('anchor')
                if anchor and self.indexmode:
                    self._indexListParagraph(t_count+1, anchor)
                self.write_t_rec(element, bullet=bullet, indent=indent, \
                                 level=level + 1, \
                                 sub_indent=sub_indent, leading_blankline=leading_blankline)
                t_count += 1

        
    def pre_write_toc(self):
        return ['', 'Table of Contents', '']

    def post_write_toc(self):
        return []

    def write_toc(self, paging=False):
        """ Write table of contents to a temporary buffer and return """
        if self.toc_marker < 1:
            # Toc is either disabled, or the pointer was messed up
            return ['']
        tmpbuf = []
        tmpbuf.extend(self.pre_write_toc())
        # Retrieve toc from the index
        tocindex = self._getTocIndex()
        tocdepth = self.pis['tocdepth']
        try:
            tocdepth = int(tocdepth)
        except ValueError:
            xml2rfc.log.warn('Invalid tocdepth specified, must be integer:', \
                             tocdepth)
            tocdepth = 3
        indent_scale = 2
        if self.pis['tocnarrow'] == 'no':
            indent_scale = 3
        for item in tocindex:
            # Add decoration to counter if it exists, otherwise leave empty
            if item.level <= tocdepth:
                counter = ''
                if item.counter:
                    counter = item.counter + '. '
                    # Extra space on single digit counters
                    if len(item.counter.rsplit('.')[-1]) == 1:
                        counter += ' '
                # Get item depth based on its section 'level' attribute
                depth = item.level - 1
                if depth < 0 or self.pis['tocindent'] == 'no':
                    depth = 0
                # Prepend appendix at first level
                if item.level == 1 and item.appendix:
                    counter = "Appendix " + counter
                bullet = ' ' * (depth * indent_scale) + counter
                indent = 3
                sub_indent = indent + len(bullet)
                pagestr = '%4s' % item.page
                lines = textwrap.wrap(bullet + (item.title.strip() if item.title else ""),
                                      self.width - len(pagestr),
                                      initial_indent=' ' * indent,
                                      subsequent_indent=' ' * sub_indent)
                if paging:
                    # Construct dots
                    dots = len(lines[-1]) % 2 and ' ' or ''
                    dots += ' .' * int((self.width - len(lines[-1]) - len(dots) + 1)//2)
                    lines[-1] += dots
                    # Insert page
                    lines[-1] = lines[-1][:0 - len(pagestr)] + pagestr
                tmpbuf.extend(lines)
        tmpbuf.extend(self.post_write_toc())
        return tmpbuf

    def pre_write_iref_index(self):
        return ['', 'Index']

    def write_iref_index(self):
        """ Write iref index to a temporary buffer and return """
        def pagelist(pages):
            pages = list(set(pages))
            pages.sort()
            # find ranges
            items = []
            prev = None
            for page in pages:
                if prev and (page - prev == 1):
                    items[-1].append(page)
                else:
                    items.append([page])
                prev = page
            pagelist = []
            for item in items:
                if len(item) == 1:
                    pagelist.append("%d"%item[0])
                else:
                    pagelist.append("%d-%d"%(item[0], item[-1]))
            return ", ".join(pagelist)

        if self.iref_marker < 1:
            # iref is either disabled, or the pointer was messed up
            return ['']
        tmpbuf = self.pre_write_iref_index()
        # Sort iref items alphabetically, store by first letter 
        alpha_bucket = {}
        keys = list(self._iref_index.keys())
        keys.sort(key=str.upper)
        for key in keys:
            letter = key[0].upper()
            if letter in alpha_bucket:
                alpha_bucket[letter].append(key)
            else:
                alpha_bucket[letter] = [key]
        for letter in sorted(alpha_bucket.keys()):
            # Write letter
            self.write_text(letter, indent=3, leading_blankline=True, buf=tmpbuf)
            for item in sorted(alpha_bucket[letter]):
                pages = self._iref_index[item].pages
                # Write item
                self.write_text(item + '  ' + pagelist(pages)
                                                        , indent=6, buf=tmpbuf, fix_doublespace=False)
                subkeys = list(self._iref_index[item].subitems.keys())
                subkeys.sort(key=str.upper)
                for subitem in subkeys:
                    pages = set(self._iref_index[item].subitems[subitem].pages)
                    # Write subitem
                    self.write_text(subitem + '  ' + pagelist(pages)
                                                        , indent=9, buf=tmpbuf, fix_doublespace=False)
        return tmpbuf

    def _expand_xref(self, xref):
        """ Returns the proper text representation of an xref element """
        target = xref.attrib.get('target', '')
        format = xref.attrib.get('format', self.defaults['xref_format'])
        item = self._getItemByAnchor(target)
        if not self.indexmode:
            if not item:
                xml2rfc.log.warn("Can't resolve xref target %s" % target)
            else:
                item.used = True
        if not item:
            target_text = '[' + target + ']'
        elif format == 'none':
            if xref.text:
                return xref.text.rstrip()
            return ''
        elif format == 'counter':
            target_text = item.counter
        elif format == 'title':
            target_text = item.title.strip()
        else: #Default
            target_text = item.autoName
        target_text = re.sub("-", u"\u2011", target_text) # switch to non-breaking hyphens
        target_text = re.sub(" ", u"\u00A0", target_text)  # switch to non-breaking space
        if xref.text:
            if not target_text.startswith('['):
                target_text = '(' + target_text + ')'
            return xref.text.rstrip() + ' ' + target_text
        else:
            return target_text

    def _expand_u(self, u):
        try:
            text = expand_unicode_element(u)
        except (RuntimeError, ValueError) as exc:
            text = ''
            xml2rfc.log.error('%s'%exc)
        return text

    def write_ref_element(self, key, text, sub_indent, source_line=None):
        """ Render a single reference element """
        # Use an empty first line if key is too long
        min_spacing = 2
        if len(key) + min_spacing > sub_indent:
            self.write_text(key, indent=3, leading_blankline=True, wrap_urls=False, fix_sentence_endings=False, source_line=source_line)
            self.write_text(text, indent=3 + sub_indent, wrap_urls=False, fix_sentence_endings=False, source_line=source_line)
        else:
            # Fill space to sub_indent in the bullet
            self.write_text(text, indent=3, bullet=key.ljust(sub_indent), \
                     sub_indent=sub_indent, leading_blankline=True, wrap_urls=False, fix_sentence_endings=False, source_line=source_line)
    
    def _combine_inline_elements(self, elements):
        """ Shared function for <t> and <c> elements
        
            Aggregates all the rendered text of the following elements:
                - xref
                - eref
                - iref
                - cref
                - spanx
            
            Plus their tails.  If an element is encountered that isn't one
            of these (such as a list, figure, etc) then the function
            returns.
            
            This function takes a list of elements as its argument.
            
            This function returns TWO arguments, the aggregated text, and 
            a list containing the rest of the elements that were not processed,
            so that the calling function can deal with them.
        """
        line = ['']
        for i, element in enumerate(elements):
            if element.tag not in self.inline_tags:
                # Not an inline element, exit
                return ''.join(line), elements[i:]

            if element.tag == 'xref':
                line.append(self._expand_xref(element))
            elif element.tag == 'eref':
                if element.text and len(element.text)>0:
                    line.append(element.text.strip())
                    self.eref_count += 1
                    line.append(' [' + str(self.eref_count) + ']')
                    if self.indexmode:
                        self.eref_list.append([self.eref_count, element])
                else:
                    line.append('<' + element.attrib['target'].strip() + '>')
            elif element.tag == 'iref':
                self._add_iref_to_index(element)
            elif element.tag == 'cref':
                if element.pis['comments'] == 'yes':                
                    # Render if processing instruction is enabled
                    self.cref_counter += 1
                    anchor = element.attrib.get('anchor', None)
                    if anchor is None:
                        anchor = 'CREF' + str(self.cref_counter)
                        element.attrib['anchor'] = anchor
                    self._indexCref(self.cref_counter, anchor)
                    if element.pis['inline'] == 'yes':
                        if anchor:
                            anchor = anchor + ': '
                        source = element.attrib.get('source', "")
                        if source:
                            source = " --" + source
                        if element.text:
                            line.append('[[' + anchor + element.text + source + ']]')
                    else:
                        line.append('[' + anchor + ']')
                        self.cref_list.append(element)
            elif element.tag == 'spanx':
                style = element.attrib.get('style', 'emph')
                edgechar = '_'  # default to emph because the spanx element exists
                if style == 'emph':
                    edgechar = '_'
                elif style == 'strong':
                    edgechar = '*'
                elif style == 'verb':
                    edgechar = '"'
                text = ''
                if element.text:
                    text = element.text
                line.append(edgechar + text + edgechar)
            elif element.tag == 'u':
                line.append(self._expand_u(element))
            else:
                xml2rfc.log.error("Found unexpected inline element: <%s>" % element.tag)

            # Add tail text before next element
            if element.tail:
                line.append(element.tail)

            # Go to next sibling
            element = element.getnext()

        # Went through all elements, return text with an empty list
        return ''.join(line), []
            
    def _check_long_lines(self, buf_line, source_line):
        long_lines = [ (num, line) for num, line in enumerate(self.buf[buf_line:]) if (len(line) > self.width) ]
        for num, line in long_lines:
            if source_line:
                xml2rfc.log.warn("Output line (from source around line %s) is %s characters; longer than %s.  Excess characters: '%s':\n  '%s'\n"
                    % (source_line+num, len(line), self.width, line[self.width:], line))
            else:
                xml2rfc.log.warn("Output line (from source around line %s) is %s characters; longer than %s.  Excess characters: '%s':\n  '%s'\n"
                    % (buf_line+num, len(line), self.width, line[self.width:], line))

    # ---------------------------------------------------------
    # Base writer overrides
    # ---------------------------------------------------------

    def insert_toc(self):
        """ Marks buffer position for post-writing table of contents """
        self.toc_marker = len(self.buf)
        
    def insert_iref_index(self):
        """ Marks buffer position for post-writing index """
        self.iref_marker = len(self.buf)

    def write_raw(self, text, indent=3, align='left', blanklines=0, \
                  delimiter=None, leading_blankline=True, source_line=None):
        """ Writes a raw stream of characters, preserving space and breaks """
        
        if text:
            if leading_blankline:
                # Start with a newline
                self._lb()
            # Delimiter?
            if delimiter:
                self.buf.append(delimiter)
            # Additional blank lines?
            self.buf.extend([''] * blanklines)
            start_line = len(self.buf)
            # Format the input
            if "\t" in text:
                xml2rfc.log.warn("Text %scontains tab characters.  These will be expanded, assuming a tab-size of 8." %
                    (("around line %s "%source_line) if source_line else ""))
            lines = [line.rstrip() for line in text.expandtabs().split('\n')]
            # Outdent if it helps anything
            longest_line = max(len(line.rstrip()) for line in lines)
            if (longest_line > self.width-indent):
                new_indent = max(self.width - longest_line, 0)
                if not self.indexmode:
                    xml2rfc.log.warn('artwork outdented %s characters to avoid overrunning right margin around input line %s)' % (indent - new_indent, source_line if source_line else 0))
                indent = new_indent

            # Trim first and last lines if they are blank, whitespace is handled
            # by the `blanklines` and `delimiter` arguments
            if len(lines) > 1:
                if lines[0] == '':
                    lines.pop(0)
                if lines[-1] == '':
                    lines.pop(-1)
            if align == 'center':
                # Find the longest line, and use that as a fixed center.
                center_indent = indent + ((self.width - indent - longest_line) // 2)
                indent_str = center_indent > indent and ' ' * center_indent or \
                                                        ' ' * indent
                for line in lines:
                    self.buf.append(indent_str + line.rstrip())
            elif align == 'right':
                indent_str = ' ' * (self.width - longest_line)
                for line in lines:
                    self.buf.append(indent_str + line.rstrip())
            else:  # align == left
                indent_str = ' ' * indent
                for line in lines:
                    self.buf.append(indent_str + line.rstrip())
            # Additional blank lines?
            self.buf.extend([''] * blanklines)
            # Delimiter?
            if delimiter:
                self.buf.append(delimiter)
            if not self.indexmode:
                self._check_long_lines(start_line, source_line)

    def write_label(self, text, type='figure', source_line=None):
        """ Writes a centered label """
        self.write_text(text, indent=3, align='center', leading_blankline=True, source_line=source_line)

    def write_title(self, title, docName=None, source_line=None):
        """ Write the document title and (optional) name """
        self.write_text(title, leading_blankline=True, align='center', source_line=source_line)
        if docName and not self.rfcnumber:
            self.write_text(docName, align='center')

    def write_heading(self, text, bullet='', autoAnchor=None, anchor=None, \
                      level=1):
        """ Write a generic header """
        if bullet:
            bullet += '  '
        self.write_text(text, bullet=bullet, indent=0, leading_blankline=True)

    def write_paragraph(self, text, align='left', autoAnchor=None):
        """ Write a generic paragraph of text.  Used for boilerplate. """
        text = xml2rfc.utils.urlkeep(text)
        self.write_text(text, indent=3, align=align, leading_blankline=True)

    def write_t_rec(self, t, indent=3, sub_indent=0, bullet='',
                     autoAnchor=None, align='left', level=0, leading_blankline=True):
        """ Recursively writes a <t> element """
        # Grab any initial text in <t>
        current_text = t.text or ''
        if bullet and current_text == '':
            current_text = ' '
        
        # Render child elements
        remainder = t.getchildren()
        while len(remainder) > 0 or current_text:
            # Process any inline elements
            inline_text, remainder = self._combine_inline_elements(remainder)
            current_text += inline_text
            if (current_text and not current_text.isspace()) or bullet:
                # Attempt to write a paragraph of inline text
                self.write_text(current_text, indent=indent,
                                leading_blankline=leading_blankline,
                                sub_indent=sub_indent, bullet=bullet,
                                edit=True, align=align, source_line=t.sourceline)
            # Clear text
            current_text = ''

            # Handle paragraph-based elements (list, figure, vspace)
            if len(remainder) > 0:
                # Get front element
                element = remainder.pop(0)

                if element.tag == 'list': 
                    if sub_indent > 0:
                        new_indent = sub_indent + indent
                    else:
                        new_indent = len(bullet) + indent
                    # Call sibling function to construct list
                    self.write_list(element, indent=new_indent, level=level)
                    # Auto-break for tail paragraph
                    leading_blankline = True
                    bullet = ''

                elif element.tag == 'figure':
                    self.write_figure(element)
                    # Auto-break for tail paragraph
                    leading_blankline = True
                    bullet = ''

                elif element.tag == 'vspace':
                    # Insert `blankLines` blank lines into document
                    self._vspace(num=int(element.attrib.get('blankLines',
                                         self.defaults['vspace_blanklines'])))
                    # Don't auto-break for tail paragraph
                    leading_blankline = False
                    # Keep indentation
                    bullet = ' ' * sub_indent

                # Set tail of element as input text of next paragraph
                if element.tail:
                    current_text = element.tail
                    

    def write_top(self, left_header, right_header):
        """ Combines left and right lists to write a document heading """
        # Begin with a blank line on the first page.  We'll add additional
        # blank lines at the top later, but those won't be counted as part
        # of the page linecount.
        #self._lb(num=3)
        self._lb()
        heading = []
        for i in range(max(len(left_header), len(right_header))):
            if i < len(left_header):
                left = left_header[i]
            else:
                left = ''
            if i < len(right_header):
                right = right_header[i]
            else:
                right = ''
            heading.append(xml2rfc.utils.justify_inline(left, '', right, \
                                                        self.width))
        self.write_raw('\n'.join(heading), align='left', indent=0,
                        leading_blankline=False, source_line=None)
        # Extra blank line underneath top block
        self._lb()

    def write_address_card(self, author):
        """ Writes a simple address card with no line breaks """
        lines = []
        if 'role' in author.attrib:
            lines.append("%s (%s)" % (author.attrib.get('fullname', ''),
                                      author.attrib.get('role', '')))
        else:
            lines.append(author.attrib.get('fullname', ''))
        organization = author.find('organization')
        if organization is not None and organization.text:
            lines.append(organization.text.strip())
        address = author.find('address')
        if address is not None:
            postal = address.find('postal')
            if postal is not None:
                for street in postal.findall('street'):
                    if street.text:
                        lines.append(street.text)
                cityline = []
                city = postal.find('city')
                if city is not None and city.text:
                    cityline.append(city.text)
                region = postal.find('region')
                if region is not None and region.text:
                    if len(cityline) > 0: cityline.append(', ');
                    cityline.append(region.text)
                code = postal.find('code')
                if code is not None and code.text:
                    if len(cityline) > 0: cityline.append('  ');
                    cityline.append(code.text)
                if len(cityline) > 0:
                    lines.append(''.join(cityline))
                country = postal.find('country')
                if country is not None and country.text:
                    lines.append(country.text)
            lines.append('')
            phone = address.find('phone')
            if phone is not None and phone.text:
                lines.append('Phone: ' + phone.text)
            facsimile = address.find('facsimile')
            if facsimile is not None and facsimile.text:
                lines.append('Fax:   ' + facsimile.text)
            email = address.find('email')
            if email is not None and email.text:
                label = self.pis['rfcedstyle'] == 'yes' and 'EMail' or 'Email'
                lines.append('%s: %s' % (label, email.text))
            uri = address.find('uri')
            if uri is not None and uri.text:
                lines.append('URI:   ' + uri.text)
        self.write_raw('\n'.join(lines), indent=self.margin)
        self._lb()

    def write_reference_list(self, list):
        """ Writes a formatted list of <reference> elements """
        refdict = {}
        annotationdict = {}
        refkeys = []
        refsource = {}
        # [surname, initial.,] "title", (STD), (BCP), (RFC), (Month) Year.
        i = 0
        for i, ref in enumerate(list.findall('reference')):
            refstring = []
            authors = ref.findall('front/author')
            author_string = self._format_author_string(authors)
            refstring.append(author_string)
            if len(author_string):
                refstring.append(', ')
            title = ref.find('front/title')
            if title is not None and title.text:
                if ref.attrib.get("quote-title", "true") == "true": # attribute default value: yes
                    refstring.append('"' + title.text.strip() + '"')
                else:
                    refstring.append(title.text.strip())
            else:
                xml2rfc.log.warn('No title specified in reference',
                                 ref.attrib.get('anchor', ''))
            for seriesInfo in ref.findall('seriesInfo'):
                if seriesInfo.attrib['name'] == "Internet-Draft":
                    refstring.append(', '+seriesInfo.attrib['value'] + ' (work in progress)')
                else:
                    refstring.append(', '+seriesInfo.attrib['name'] + u'\u00A0' +
                                     seriesInfo.attrib['value'].replace('/', '/' + u'\uE060'))
            date = ref.find('front/date')
            if date is not None:
                month = date.attrib.get('month', '')
                year = date.attrib.get('year', '')
                if month or year:
                    if month:
                        month += ' '
                    refstring.append(', '+month + year)
            # Target?
            target = ref.attrib.get('target')
            if target:
                refstring.append(', <' + target + '>')
            refstring.append('.')
            annotation = ref.find('annotation')
            # Use anchor or num depending on PI
            if self.pis['symrefs'] == 'yes':
                key = ref.attrib.get('anchor', str(i + self.ref_start))
            else:
                key = str(i + self.ref_start)
            refdict[key] = ''.join(refstring)
            refsource[key] = ref.sourceline
            refkeys.append(key)
            # Add annotation if it exists to a separate dict
            if annotation is not None and annotation.text:
                # Render annotation as a separate paragraph
                remainder = annotation.getchildren()
                annotationdict[key] = annotation.text
                if len(remainder) > 0:
                    inline_txt, remainder = self._combine_inline_elements(remainder)
                    annotationdict[key] += inline_txt
        self.ref_start += i + 1
        # Don't sort if we're doing numbered refs; they are already in
        # numeric order, and if we sort, they will be sorted alphabetically,
        # rather than numerically ... ( i.e., [10], [11], ... [19], [1], ... )
        if self.pis['sortrefs'] == 'yes' and self.pis['symrefs'] == 'yes' :
            refkeys.sort(key=str.lower)
        # Hard coded indentation amount
        refindent = 11
        for key in refkeys:
            reflabel = '['+key+']'
            self.write_ref_element(reflabel, refdict[key], refindent, source_line=refsource[key])
            # Render annotation as a separate paragraph
            if key in annotationdict:
                self.write_text(annotationdict[key], indent=refindent + 3,
                                 leading_blankline=True, source_line=refsource[key])

    def write_erefs(self, refs_counter, refs_subsection):
        bullet=str(refs_counter) + '.' + str(refs_subsection)
        self.write_heading("URIs", bullet=bullet +'.',
                           level = 2, autoAnchor='rfc.references.' + str(refs_subsection))
        for i, element in self.eref_list:
            self.write_text(element.attrib['target'], bullet='['+str(i)+'] ',
                            leading_blankline=True, indent=3)

    def write_crefs(self):
        """ If we have any of these because the are not inline, then
            write them out here
        """
        if self.cref_list:
            self.write_heading('Editorial Comments')
            for cref in self.cref_list:
                body = cref.text
                source = cref.attrib.get('source', None)
                if source:
                    body = source + ': ' + body
                self.write_text(body, bullet='['+cref.attrib['anchor']+'] ',
                                leading_blankline=True)

    def draw_table(self, table, table_num=None):
        # First construct a 2d matrix from the table
        matrix = []
        matrix.append([])
        row = 0
        column_aligns = []
        ttcol_width_attrs = []
        style = table.attrib.get('style', self.defaults['table_style'])

        # Extract information from the ttcol elements about each column
        for ttcol in table.findall('ttcol'):
            column_aligns.append(ttcol.attrib.get('align', self.defaults['ttcol_align']))
            ttcol_width_attrs.append(ttcol.attrib.get('width', ''))

            text = ttcol.text or ''
            if len(ttcol) > 0:
                # <c> has children, render their text and add to line
                inline_text, null = \
                    self._combine_inline_elements(ttcol.getchildren())
                text += inline_text
            matrix[row].append(text)

        num_columns = len(matrix[0])

        # Get the text for each cell into the matrix
        #    Insert appropriate blank lines for filler at this time.
        for i, cell in enumerate(table.findall('c')):
            if i % num_columns == 0:
                # Insert blank row if PI 'compact' is 'no'
                if table.pis["compact"] == "no":
                    if (style == 'none' and row == 0) or (style in ['headers', 'full'] and row != 0):
                        row += 1
                        matrix.append(['']*num_columns)
                        pass
                row += 1
                matrix.append([])


            text = cell.text or ''
            if len(cell) > 0:
                # <c> has children, render their text and add to line
                inline_text, null = \
                    self._combine_inline_elements(cell.getchildren())
                text += inline_text
            matrix[row].append(text)

        # Get table style and determine maximum width of table
        if style in ['none', 'headers']:
            table_max_chars = self.width - 3 - num_columns + 1
        else:
            table_max_chars = self.width - 3 - 3 * num_columns - 1  # indent+border

        if table_max_chars < 0:
            xml2rfc.log.error("too many <ttcol>s to even build <texttable> frame")

        # Find the longest line and longest word in each column
        longest_lines = [0] * num_columns
        longest_words = [0] * num_columns
        for col in range(num_columns):
            for row in matrix:
                if col < len(row) and len(row[col]) > 0:  # Column exists
                    # Longest line
                    if self._length(row[col]) > longest_lines[col]:
                        longest_lines[col] = self._length(row[col])
                    # Longest word
                    if row[col].strip():
                        word = max(xml2rfc.utils.ascii_split(row[col]), key=self._length)
                        if self._length(word) > longest_words[col]:
                            longest_words[col] = self._length(word)
        
        min_width = sum(longest_words)
        
        # Assume one character per non-empty column - are there too many columns?
        inf = []
        for col in longest_words:
            col = (col != 0)
            inf.append(col)
        if table_max_chars < sum(inf):
            xml2rfc.log.error("too many non-empty columns in <texttable> to fit in page width")

        # Translate width specs given available space
        cols = []
        rel_total = 0
        ttcol_width_unspec = []

        for col in ttcol_width_attrs:
            #  what to do with the unspecified ones is touchy.
            u = 0
            if not col:
                x = longest_words[len(cols)]
                u = 1
            elif col == '*':
                x = -1
                rel_total += x
            else:
                m = re.match("^0*([0-9]+)(|em|[%*])$", col)
                if not m:
                    xml2rfc.log.warn("Width attribute not in correct format: %s" & col)
                    x = longest_words[len(cols)]
                    u = 1
                if m.group(2) == 'em':
                    x = int(m.group(1));
                elif m.group(2) == '%':
                    x = (int(m.group(1)) * table_max_chars + 99)//100
                elif m.group(2) == '*':
                    x = -int(m.group(1))
                    rel_total += x

            cols.append(x)
            ttcol_width_unspec.append(u)

        ttcol_width_attrs = cols

        # Compute final cell widths ( and their totals )

        width = table_max_chars
        if table_max_chars == sum(longest_words):
            #  Use the minimum widths if that is all we have
            ttcol_widths = longest_words
        elif table_max_chars == sum(inf):
            #  ??????????????
            ttcol_widths = inf
        elif table_max_chars < sum(longest_words):
            if not self.indexmode:
                xml2rfc.log.warn("so many <ttcol>s in <texttable> that some words need to be split near line %s" % table.sourceline)

            excess = sum(longest_words) - table_max_chars

            # First, try the mins that are greater than what they requested.

            rel_total = -rel_total
            tol = []
            fnum  = 1000 if (rel_total > 0) else 0
            fden  = 1
            for s, n in zip(ttcol_width_attrs, longest_words):
                t = 0
                if s >= 0:
                    s += (s == 0)
                    y = n - s
                    if y > 0:
                        t = y
                elif fnum > 0:
                    # Prepare in case we need to try the relative widths.
                    n -= 1
                    s = -s
                    # We keep the smallest acceptable factor to all as a mixed number.
                    if n <= 0:
                        fnum = 0
                    elif n * fden < s * fnum:
                        fnum = n
                        fden = s

                tol.append(t)

            excess, ttcol_widths = self.shave_cols_excess(longest_words, excess, tol, sum(tol))

            # Second, try the unspecified widths.
            if excess > 0:
                tol = []
                for w,u in zip(ttcol_widths, ttcol_width_unspec):
                    t = (w-1) if (u and w > 0) else 0
                    tol.append(t)

                excess, ttcol_widths = self.shave_cols_excess(ttcol_widths, excess, tol, sum(tol))

            # Third, try the relative widths (to shrink, not expand).
            if excess > 0 and fnum > 0:
                if excess * fden < rel_total * fnum:
                    fnum = excess
                    fden = rel_total

                tol = []
                for s in ttcol_width_attrs:
                    t = ((fnum * -(s)) // fden) if (s < 0) else 0
                    tol.append(t)

                excess, ttcol_widths = self.shave_cols_excess(ttcol_widths, excess, tol, sum(tol))

            # Finally, try anything that's left, leaving as little as one column.
            # Start with largest.

            p = 1
            for w in ttcol_widths:
                if w > p:
                    p = w
            
            while excess > 0:
                if p == 1:
                    xml2rfc.log.error("bug in reducing <texttable> column widths")

                # Find second largest.
                q = 1
                for w in ttcol_widths:
                    if w > q and w < p:
                        q = w

                tol = []
                for w in ttcol_widths:
                    t = (w - q) if (w > q) else 0
                    tol.append(t)

                excess, ttcol_widths = self.shave_cols_excess(ttcol_widths, excess, tol, sum(tol))

                p = q

        else:
           #  There is room beyond the minimum space
           #  First, try and give everyone what they want or need
           #   longest_words + ttcol_width_attrs + longest_lines(all)
           ttcol_widths = []
           cols_width = 0

           #   longest_words + ttcol_width_attrs
           mnsa = []

           #   longest_words + ttcol_width_attrs + longest_lines(rel)
           mnsb = []

           #   longest_words + ttcol_width_attrs + longest_lines(rel + ttcol_width_unspec)
           mnsc = []
       
           for m, n, s, u in zip(longest_lines, longest_words, ttcol_width_attrs, ttcol_width_unspec):
                t = n
                if (t < s):
                    t = s
                mnsa.append( t )

                if (s < 0):
                    t = m
                mnsb.append( t )

                if u:
                    t = m
                mnsc.append(t)

                if (t < m):
                    t = m
                ttcol_widths.append(t)

           cols_width = sum(ttcol_widths)

           #  In decreasing order by width
           if table_max_chars >= cols_width:
               width = cols_width

           elif table_max_chars > sum(mnsc):
               # partially expand columns with greater maximal width from mnsc
               target = table_max_chars - sum(mnsc)
               target, ttcol_widths = self.expand_cols_by_height(mnsc, target, ttcol_widths)

           elif table_max_chars == sum(mnsc):
                ttcol_widths = mnsc

           elif table_max_chars > sum(mnsb):
               # Partially expand columns with unspecified width from mnsb
               target = table_max_chars - sum(mnsb)
               target, ttcol_widths = self.expand_cols_by_height(mnsb, target, ttcol_widths)

           elif table_max_chars == sum(mnsb):
                ttcol_widths = mnsb

           elif table_max_chars > sum(mnsa):
                #Partially expand columns with relative width from mnsa.
            
                ttcol_widths = mnsa
                target = table_max_chars - sum(mnsa)
                while target > 0:
                   rel = []
                   num_rel = 0
                   rel_total = 0
                   fnum = 1000
                   fden = 1
                   for m,s,w in zip(longest_lines, ttcol_width_attrs, ttcol_widths):
                       x = 0
                       if s < 0:
                           d = m - w
                           if d > 0:
                               x = -s
                               if d * fden < x * fnum:
                                   fnum = d
                                   fden = x
                               num_rel += 1;
                               rel_total += x
                       rel.append(x)
                       
                   if target * fden < rel_total * fnum:
                       fnum = target
                       fden = rel_total

                   plus_width = 0
                   if (num_rel > 0) and (fnum > 0):
                       kols = []
                       for r,w in zip(rel, ttcol_widths):
                           p = r*fnum//fden
                           kols.append(w + p)
                           plus_width += p

                   if plus_width > 0:
                       ttcol_widths = kols
                       target += -plus_width

                   elif num_rel > 0:
                       dd = target
                       kols = []
                       for r,w in zip(rel, ttcol_widths):
                           if r > 0:
                              # prefer expanding the rightmost ones
                              if dd >= num_rel:
                                  w += 1
                                  target -= 1
                              dd += 1
                           kols.append(w)
                       ttcol_widths = kols

                   else:
                       xml2rfc.log.error("bug in expanding <texttable> columns with relative widths")

           elif table_max_chars == sum(mnsa):
               ttcol_widths = mnsa
           else:
               # Partially expand comns with greater specified width from longest_words
               target = table_max_chars - min_width
               plus = []
               for a,b in zip(mnsa, longest_words):
                   plus.append(a-b)
               target, ttcol_widths = self.expand_cols(longest_words, target, plus)

        # Ensure we don't have any zero-width columns; it breaks textwrap
        ttcol_widths = [ k or 1 for k in ttcol_widths ] 
        # Now construct the cells using textwrap against ttcol_widths
        cell_lines = [
            [ textwrap.wrap(cell, ttcol_widths[j]) or [''] for j, cell in enumerate(matrix[i]) ]
            for i in range(0, len(matrix))
        ]

        output = []
        # Create the border
        if style == 'none':
            pass
        elif style == 'headers':
            borderstring = []
            for i in range(num_columns):
                borderstring.append('-' * ttcol_widths[i])
                borderstring.append(' ')
        else:
            borderstring = ['+']
            for i in range(num_columns):
                borderstring.append('-' * (ttcol_widths[i] + 2))
                borderstring.append('+')
            output.append(''.join(borderstring))

        # Draw the table
        for i, cell_line in enumerate(cell_lines):
            if i==0 and cell_line == [['']]*num_columns:
                if style in ['headers']:
                    # This is the header row, append the header decoration
                    output.append(''.join(borderstring))
                continue
            # produce as many output rows as the number of wrapped
            # text lines in the cell with most lines, but at least 1
            for row in range(0, max(map(len, cell_line))):
                if style == 'headers' or style == 'none':
                    line = ['']
                else:
                    line = ['|']
                for col, cell in enumerate(cell_line):
                    align = column_aligns[col]
                    width = ttcol_widths[col]
                    if row < len(cell):
                        # width = width + len(cell[row]) - self._length(cell[row])
                        if align == 'center':
                            text = cell[row].center(width)
                        elif align == 'right':
                            text = cell[row].rjust(width)
                        else:  # align == left
                            text = cell[row].ljust(width)
                        if style == 'headers' or style == 'none':
                            line.append(text)
                            line.append(' ')
                        else:
                            line.append(' ')
                            line.append(text)
                            line.append(' |')
                    else:
                        if style == 'headers' or style == 'none':
                            line.append(' ' * (ttcol_widths[col] + 1))
                        else:
                            line.append(' ' * (ttcol_widths[col] + 2) + '|')
                output.append(''.join(line))
            if style in ['headers', 'full']:
                if i == 0:
                    # This is the header row, append the header decoration
                    output.append(''.join(borderstring))
            if style in ['full']:
                if i == len(cell_lines)-1:
                    output.append(''.join(borderstring))
            if style in ['all']:
                output.append(''.join(borderstring))


        # Finally, write the table to the buffer with proper alignment
        align = table.attrib.get('align', self.defaults['table_align'])
        self.write_raw('\n'.join(output), align=align, indent=self.margin,
                        source_line=table.sourceline)


    def expand_cols_by_height(self, cols, target, bound):
        # cols - current column width
        # target - expand by this amount 
        # bound - this is the lower boundary of the column width

        while target > 0:
            # Compute the current width and boundary width for those where current is less than boundary
            m_width = 0
            w_width = 0
            for m,w in zip(bound, cols):
                if (m > w):
                   # Only cover those columns below the bound.
                   m_width += m
                   w_width += w

            #  This mixed number is the average height we could achieve.

            fnum = m_width
            fden = w_width + target
            plus_num = 0
            plus = []
            plus_width = 0
            kols = []
            for m,w in zip(bound, cols):
                p = 0
                k = w
                if m > w:
                    x = m * fden
                    y = w * fnum
                    # Seek columns of above average height.
                    if x >= y:
                        # Nearly reduce height to average by augmenting width
                        p = 1
                        k = x // (fnum + fden - 1)
                        if k < w:
                            # but no smaller than before.
                            k = w
                        if k > w + target:
                            k = w + target
                        q = k - w
                        plus_num += 1
                        plus_width += q

                plus.append(p)
                kols.append(k)

            if plus_width > 0:
               cols = kols
               target += (-plus_width)

            elif plus_num > 0:
                # No progress due to integer division.  Make some.
                dd = target
                cols = []
                for p,w in zip(plus, kols):
                    if p > 0:
                        # Prefer expanding the rightmost ones.
                        if dd >= plus_num:
                            w += 1
                            target -= 1
                        dd += 1
                    cols.append(w)

            else:
                # Should not happen, but just in case we were given a bad target
                cols = cols
                break;

        return [target, cols]

    def shave_cols_excess (self, cols, excess, give, give_width=-1):
        if give_width < 0:
            give_width =sum(give)

        if excess <= 0 or give_width <= 0:
            # Nothing to do.
            pass
        elif excess >= give_width:
            # Take everything; it may still not be enough.
            plus = []
            for a,b in zip(cols, give):
                plus.append(a-b)
            cols = plus
            excess += -(give_width)
        else:
            # Take only what we need, in relative proportion.
            dd = 0
            kols = []
            for c, g in zip(cols, give):
                if g > 0:
                    d =(g * excess) // give_width
                    c += -(d)
                    dd += d
                kols.append( c )
            excess += -(dd)
    
            # Do the ones we missed because of integer division.
            if excess > 0:
                cols = []
                for k, g in zip(kols, give):
                    # Prefer shaving the leftmost ones.
                    if excess > 0 and g > 0:
                        k += -1
                        excess += -1
                    cols.append( k )
            else:
                cols = kols
    
        return [excess, cols]

    def expand_cols(self, cols, target, plus, plus_width=-1):
        if plus_width < 0:
            plus_width =sum(plus)

        if target <= 0 or plus_width <= 0:
            # Nothing to do.
            pass
        elif target >= plus_width:
            # Take everything; it may still not be enough.
            tmp = []
            for a,b in zip(cols, plus):
                tmp.append(a+b)
            cols = tmp
            target += -(plus_width)
        else:
            # Take only what we need, in relative proportion.
            dd = 0
            dr = 0
            kols = []
            for c,p in zip(cols, plus):
                if p > 0:
                    d = (p * target) // plus_width
                    c += d
                    dd += d
                    dr += 1
                kols.append(c)

            target += -(dd)

            # Do the ones we missed because of integer division.
            if target > 0:
                dd = target
                cols = []
                for k, p in zip(kols, plus):
                    if p > 0:
                        # Prefer expanding the rightmost ones.
                        if dd >= dr:
                            k += 1
                            target -= 1
                        dd += 1
                    cols.append( k )
            else:
                cols = kols

        return [target, cols]

    def insert_anchor(self, text):
        # No anchors for text
        pass

    def pre_indexing(self):
        pass

    def pre_rendering(self):
        # Discard buffer from indexing pass
        self.buf = []
        
        # Reset document counters from indexing pass
        self.list_counters = {}
        self.edit_counter = 0   # Counter for edit marks
        self.cref_counter = 0
        self.cref_list = []

    def post_rendering(self):
        # Insert the TOC and IREF into the main buffer
        self.output = self.buf[:self.toc_marker] + \
                      self.write_toc()
        if self.iref_marker > 0:
            self.output += self.buf[self.toc_marker:self.iref_marker] + \
                      self.write_iref_index() + \
                      self.buf[self.iref_marker:]
        else:
            self.output += self.buf[self.toc_marker:]

    def post_process_lines(self, lines):
        output = []
        for line in lines:
            if isinstance(line, type(u'')):
                # line = line.replace(u"\u8209", '-')
                line = line.replace(u'\u00A0', u' ')
                line = line.replace(u'\u2011', u'-')
                line = line.replace(u'\u200B', u'')
                line = line.replace(u'\u2028', u' ')
                line = line.replace(u'\u2060', u'')
                assert line == line.replace(u'\uE060', u'')
            output.append(line);
        return output

    def write_to_file(self, file):
        """ Writes the buffer to the specified file """
        # write initial blank lines, not counted against page size...
        if self.draft:
            file.write("\n"*3)
        else:
            file.write("\n"*5)
        for line in self.post_process_lines(self.output):
            file.write(line.rstrip(u" \t"))
            file.write("\n")
