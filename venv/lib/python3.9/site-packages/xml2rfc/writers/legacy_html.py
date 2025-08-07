# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

# External libs
from lxml.html import builder as E
import lxml
import os.path
import string
import sys
import datetime
import calendar

from html import escape

try:
    from xml2rfc import debug
    debug.debug = True
    assert debug
except ImportError:
    pass

# Local libs
import xml2rfc
from xml2rfc.util.name import short_author_name_parts
from xml2rfc.util.unicode import expand_unicode_element
from xml2rfc.writers.base import BaseRfcWriter, default_options



class HtmlRfcWriter(BaseRfcWriter):
    """ Writes to an HTML file.

        Uses HTML templates located in the templates directory.
    """
    # HTML Specific Defaults that are not provided in templates or XML
    html_defaults = { 
        'references_url': 'https://tools.ietf.org/html/',
    }

    def __init__(self, xmlrfc, quiet=None, options=default_options,
                               date=None, templates_dir=None):
        if not quiet is None:
            options.quiet = quiet
        BaseRfcWriter.__init__(self, xmlrfc, options=options)
        self.list_counters = {}
        self.iref_index = []
        self.nbws_cond = ' '    # Use space as they are in an anchor element anyway
        self.cref_counter = 0
        
        # Initialize templates directory
        self.template_dir = templates_dir or \
                             os.path.join(os.path.dirname(xml2rfc.__file__),
                                          'templates')

        # Open template files and read into string.template objects
        self.templates = {}
        for filename in ['base.html',
                         'address_card.html']:
            with open(os.path.join(self.template_dir, filename), 'r') as file:
                self.templates[filename] = string.Template(file.read())
        # Buffers to aggregate various elements before processing template
        self.buffers = {'front': [],
                        'body': [],
                        'header_rows': [],
                        'toc_head_links': [],
                        'toc_rows': []}
        
        # Use an active buffer pointer
        self.buf = self.buffers['front']
        
        # String holding the final document to write
        self.output = ''
        
        # Temporary div for recursive functions
        self.temp_div = E.DIV()

        # Table to insert the iref into
        self.iref_table = None

    def _add_iref_to_index(self, element):
        # Add anchor to index
        item = element.attrib.get('item', None)
        if item:
            subitem = element.attrib.get('subitem', None)
            anchor = '.'.join(('index', item))
            if subitem:
                anchor += '.' + subitem
            # Create internal iref
            self._make_iref(item, subitem=subitem, anchor=anchor)
            # Create anchor element
            a = E.A(name=anchor)
            if element.tail:
                a.tail = element.tail
            return [a]

    def write_list(self, list, parent, level=0):
        # grab the anchors that exist
        if self.indexmode:
            t_count = 0
            for t in list.findall('t'):
                t_count += 1
                anchor = t.attrib.get('anchor')
                if anchor:
                    self._indexListParagraph(t_count, anchor)
        # style comes from the node if one exists
        style = list.attrib.get('style', '')
        if not style:
            # otherwise look for the nearest list parent with a style and use it
            for elder in list.iterancestors():
                if elder.tag == 'list':
                    style = elder.attrib.get('style', '')
                    if style:
                        break
        if not style:
            style = 'empty'
        if style == 'hanging':
            list_elem = E.DL()
            hangIndent = list.attrib.get('hangIndent', '8')
            style = 'margin-left: ' + hangIndent
            for t in list.findall('t'):
                hangText = t.attrib.get('hangText', '')
                dt = E.DT(hangText)
                dd = E.DD(style=style)
                list_elem.append(dt)
                list_elem.append(dd)
                self.write_t_rec(t, parent=dd, level=level +1)
        elif style.startswith('format'):
            format_str = style.partition('format ')[2]
            allowed_formats = ('%c', '%C', '%d', '%i', '%I', '%o', '%x', '%X')
            if not any([ f in format_str for f in allowed_formats]):
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
            list_elem = E.DL()
            for t in list.findall('t'):
                self.list_counters[counter_index] += 1
                count = self.list_counters[counter_index]
                bullet = self._format_counter(format_str, count) + ' '
                dt = E.DT(bullet)
                dd = E.DD()
                list_elem.append(dt)
                list_elem.append(dd)
                self.write_t_rec(t, parent=dd, level=level + 1)
        else:
            if style == 'symbols':
                list_elem = E.UL()
            elif style == 'numbers':
                list_elem = E.OL()
            elif style == 'letters':
                letter_style = "list-style-type: upper-alpha" if (level % 2) else "list-style-type: lower-alpha"
                list_elem = E.OL(style= letter_style)
            else:  # style == empty
                list_elem = E.UL()
                list_elem.attrib['class'] = 'empty'
            for t in list.findall('t'):
                li = E.LI()
                list_elem.append(li)
                self.write_t_rec(t, parent=li, level= level + 1)
        parent.append(list_elem)

    def _create_toc(self):
        # Add link for toc itself
        link = E.LINK(href='#rfc.toc')
        link.attrib["rel"] = 'Contents'
        self.buffers['toc_head_links'].append(self._serialize(link))
        tocdepth = self.pis['tocdepth']
        try:
            tocdepth = int(tocdepth)
        except ValueError:
            xml2rfc.log.warn('Invalid tocdepth specified, must be integer:', \
                             tocdepth)
            tocdepth = 3
        curdepth = 1
        for item in self._getTocIndex():
            if item.level <= tocdepth:
                # set UL level
                if item.level > curdepth:
                    self.buffers['toc_rows'].append('<ul>')
                for i in range(item.level, curdepth):
                    self.buffers['toc_rows'].append('</ul>')
                curdepth = item.level

                # Create link for head
                link = E.LINK(href='#' + item.autoAnchor)
                link.attrib['rel'] = 'copyright' in item.autoAnchor and \
                                     'Copyright' or 'Chapter'
                if item.title and item.counter:
                    link.attrib['title'] = item.counter + ' ' + item.title.strip()
                self.buffers['toc_head_links'].append(self._serialize(link))
                # Create actual toc list item
                a = E.A(item.title.strip(), href='#' + item.autoAnchor)
                counter_text = item.counter and item.counter + '.   ' or ''
                # Prepend appendix at first level
                if item.level == 1 and item.appendix:
                    counter_text = "Appendix " + counter_text
                li = E.LI(counter_text)
                li.append(a)
                self.buffers['toc_rows'].append(self._serialize(li))
        for i in range(1, curdepth):
            self.buffers['toc_rows'].append('</ul>')

    def _serialize(self, element):
        if sys.version > '3':
            return lxml.html.tostring(element, pretty_print=True, method='html', encoding='utf-8').decode('utf-8')
        else:
            return lxml.html.tostring(element, pretty_print=True, method='html')
    
    def _flush_temp_div(self):
        lines = []
        for child in self.temp_div:
            lines.append(self._serialize(child))
            child.drop_tree()
        return '\n'.join(lines)
    
    def _expand_ref(self, element):
        """ Return a list of HTML elements that represent the reference """   
        if element.tag == 'xref':
            target = element.attrib.get('target', '')
            format = element.attrib.get('format', self.defaults['xref_format'])
            item = self._getItemByAnchor(target)
            if not self.indexmode:
                if not item:
                    xml2rfc.log.warn("Can't resolve xref target %s" % target)
                else:
                    item.used = True
            # Create xref from index lookup
            if not item:
                text = '[' + target + ']'
            elif format == 'none':
                text = ''
            elif format == 'counter':
                text = item.counter
            elif format == 'title':
                text = item.title.strip() if item.title else ''
            else:
                # Default
                text = item.autoName

            # following the V3 HTML -
            #  If you specify text, that is what you get.
            if element.text:
                text = element.text.rstrip()
             
            a = E.A(href='#' + target)
            a.attrib["class"] = "xref"
            a.text = text
            if element.tail:
                a.tail = element.tail
            
            return [a]

        elif element.tag == 'eref':
            target = element.attrib.get('target', '')
            if element.text:
                a = E.A(element.text, href=target)
                a.tail = element.tail
                return [a]
            else:
                sp1 = E.SPAN('<')
                a = E.A(target, href=target)
                sp2 = E.SPAN('>')
                sp2.tail = element.tail
                return [sp1, a, sp2]
        elif element.tag == 'cref':
            self.cref_counter += 1
            anchor = element.attrib.get('anchor', None)
            if anchor is None:
                anchor = 'CREF' + str(self.cref_counter)
            a = E.A('[' + anchor + ']', id=anchor)
            a.attrib['class'] = 'info'
            source = element.attrib.get('source', '')
            if source:
                source = source + ": "
            b = E.SPAN(source + element.text)
            b.attrib['class'] = 'info'
            a.append( b )
            self._indexCref(self.cref_counter, anchor)
            if element.tail:
                a.tail = element.tail
            return [a]
        elif element.tag == 'iref':
            return self._add_iref_to_index(element)
        elif element.tag == 'spanx':
            style = element.attrib.get('style', self.defaults['spanx_style'])
            text = ''
            if element.text:
                text = element.text
            elem = None
            if style == 'strong':
                elem = E.STRONG(text)
            elif style == 'verb':
                elem = E.SAMP(text)
            else:
                # Default to style=emph
                elem = E.EM(text)
            if element.tail:
                elem.tail = element.tail
            return [elem]

    def _expand_u(self, element):
        try:
            text = expand_unicode_element(element)
        except (RuntimeError, ValueError) as exc:
            text = ''
            xml2rfc.log.error('%s'%exc)
        if text:
            span = E.SPAN(text)
            span.set('class', 'unicode')
            return [span]
        return []

    # -----------------------------------------
    # Base writer overrides
    # -----------------------------------------

    def insert_toc(self):
        # We don't actually insert the toc here, but we swap the active buffer
        # So that the template replacement is correct
        self.buf = self.buffers['body']

    def write_raw(self, text, align='left', blanklines=0, delimiter=None, source_line=None):
        if text:
            # Add padding with delimiter/blanklines, if specified
            edge = delimiter and [delimiter] or ['']
            edge.extend([''] * blanklines)
            fill = '\n'.join(edge)
            fill += text
            edge.reverse()
            fill += '\n'.join(edge)

            # Run through template, add to body buffer
            pre = E.PRE(fill)
            self.buf.append(self._serialize(pre))

    def write_label(self, text, type='figure', align='center', source_line=None):
        # Ignore labels for table, they are handled in draw_table
        if type == 'figure':
            p = E.P(text)
            p.attrib['class'] = 'figure'
            # Add to body buffer
            self.buf.append(self._serialize(p))

    def write_heading(self, text, bullet=None, autoAnchor=None, anchor=None,
                      level=1):
        # Use a hierarchy of header tags if docmapping set
        h = E.H1()
        if self.pis['docmapping'] == 'yes':
            if level == 2:
                h = E.H2()
            elif level == 3:
                h = E.H3()
            elif level >= 4:
                h = E.H4()
        if autoAnchor:
            h.attrib['id'] = autoAnchor
        if bullet:
            # Use separate elements for bullet and text
            a_bullet = E.A(bullet)
            a_bullet.tail = ' '
            if autoAnchor:
                a_bullet.attrib['href'] = '#' + autoAnchor
            h.append(a_bullet)
            if anchor:
                # Use an anchor link for heading
                a_text = E.A(text.strip(), href='#' + anchor, )
                a_text.attrib["id"] = anchor
                h.append(a_text)
            else:
                # Plain text
                a_bullet.tail += text
        else:
            # Only use one <a> pointing to autoAnchor
            a = E.A(text)
            if autoAnchor:
                a.attrib['href'] = '#' + autoAnchor
            h.append(a)
        
        # Add to body buffer
        self.buf.append(self._serialize(h))

    def write_paragraph(self, text, align='left', autoAnchor=None):
        if text:
            p = E.P(text)
            if autoAnchor:
                p.attrib['id'] = autoAnchor        
            # Add to body buffer
            self.buf.append(self._serialize(p))

    def write_t_rec(self, t, autoAnchor=None, align='left', parent=None, level=0):
        """ Recursively writes a <t> element

            If no parent is specified, a dummy div will be treated as the parent
            and any text will go in a <p> element.  Otherwise text and
            child elements will be insert directly into the parent -- meaning
            we are in a list
        """
        if parent is None:
            parent = self.temp_div # Dummy div
            current = E.P()
            parent.append(current)
        else:
            current = parent
        if t.text:
            if "anchor" in t.attrib:
                a = E.A(name=t.attrib["anchor"])
                a.tail = t.text
                current.append(a)
            else:
                current.text = t.text
            if autoAnchor:
                current.attrib['id'] = autoAnchor
        for child in t:
            if child.tag in ['xref', 'eref', 'iref', 'cref', 'spanx']:
                for element in self._expand_ref(child):
                    current.append(element)
            elif child.tag == 'u':
                for element in self._expand_u(child):
                    current.append(element)
            elif child.tag == 'vspace':
                br = E.BR()
                current.append(br)
                blankLines = int(child.attrib.get('blankLines',
                                 self.defaults['vspace_blanklines']))
                for i in range(blankLines):
                    br = E.BR()
                    current.append(br)
                if child.tail:
                    br.tail = child.tail
            elif child.tag == 'list':
                self.write_list(child, parent, level=level)
                if child.tail:
                    parent.append(E.P(child.tail))
            elif child.tag == 'figure':
                # Callback to base writer method
                self.write_figure(child)
            elif child.tag == 'texttable':
                # Callback to base writer method
                self.write_table(child)
        # If we are back at top level, serialize the whole temporary structure
        # Add to body buffer
        if parent == self.temp_div:
            self.buf.append(self._flush_temp_div())

    def write_top(self, left_header, right_header):
        """ Buffers the header table """
        for i in range(max(len(left_header), len(right_header))):
            if i < len(left_header):
                left = left_header[i]
            else:
                left = ''
            if i < len(right_header):
                right = right_header[i]
            else:
                right = ''
                
            # Add row to header_rows buffer
            left_td = E.TD(left)
            left_td.attrib['class'] = 'left'
            right_td = E.TD(right)
            right_td.attrib['class'] = 'right'
            tr = E.TR(left_td, right_td)
            self.buffers['header_rows'].append(self._serialize(tr))

    def write_address_card(self, author):
        # Create substitution dictionary with empty string values
        vars = ['fullname', 'surname', 'role', 'organization',
                'street_spans', 'locality', 'region', 'code', 
                'locality_sep', 'region_sep', 'country', 'contact_spans']
        subs = dict(zip(vars, [''] * len(vars)))
        
        # Get values with safe defaults
        subs['fullname'] = author.attrib.get('fullname', '')
        subs['surname'] = author.attrib.get('surname', '')
        subs['role'] = author.attrib.get('role', '')
        subs['role'] = subs['role'] and "(%s)" % subs['role'] or ''
        subs['organization'] = author.find('organization') is not None and \
                               author.find('organization').text or ''
        address = author.find('address')
        
        # Crawl through optional elements
        if address is not None:
            postal = address.find('postal')
            if postal is not None:
                street_spans = []
                for street in postal.findall('street'):
                    if street.text:
                        span = E.SPAN(street.text)
                        span.attrib['class'] = 'vcardline'
                        street_spans.append(self._serialize(span))
                subs['street_spans'] = ''.join(street_spans)
                city = postal.find('city')
                if city is not None and city.text:
                    subs['locality'] = city.text
                    subs['locality_sep'] = ', '
                region = postal.find('region')
                if region is not None and region.text:
                    subs['region'] = region.text
                    subs['region_sep'] = ' '
                code = postal.find('code')
                if code is not None and code.text:
                    subs['code'] = code.text
                country = postal.find('country')
                if country is not None and country.text:
                    subs['country'] = country.text

            # Use temp div for contact spans
            contact_div = self.temp_div
            phone = address.find('phone')
            if phone is not None and phone.text:
                span = E.SPAN('Phone: ' + phone.text)
                span.attrib['class'] = 'vcardline'
                contact_div.append(span)
            facsimile = address.find('facsimile')
            if facsimile is not None and facsimile.text:
                span = E.SPAN('Fax: ' + facsimile.text)
                span.attrib['class'] = 'vcardline'
                contact_div.append(span)
            email = address.find('email')
            if email is not None and email.text:
                span = E.SPAN('EMail: ')
                span.attrib['class'] = 'vcardline'
                if self.pis['linkmailto'] == 'yes':
                    span.append(E.A(email.text, href='mailto:' + email.text))
                else:
                    span.text += email.text
                contact_div.append(span)
            uri = address.find('uri')
            if uri is not None and uri.text:
                span = E.SPAN('URI: ')
                span.attrib['class'] = 'vcardline'
                span.append(E.A(uri.text, href=uri.text))
                contact_div.append(span)

            # Serialize the temp div
            subs['contact_spans'] = self._flush_temp_div() 

        # Run through template and add to body buffer
        html = self.templates['address_card.html'].substitute(subs)
        self.buf.append(html)

    def write_reference_list(self, list):
        tbody = E.TBODY()
        refkeys = []
        refdict = {}
        for i, reference in enumerate(list.findall('reference')):
            tr = E.TR()
            # Use anchor or num depending on PI
            anchor = reference.attrib.get('anchor', str(i + self.ref_start))
            if self.pis['symrefs'] == 'yes':
                bullet = anchor
            else:
                bullet = str(i + self.ref_start)
            bullet_td = E.TD(E.B('[' + bullet + ']', id=anchor))
            bullet_td.attrib['class'] = 'reference'
            ref_td = E.TD()
            ref_td.attrib['class'] = 'top'
            last = None
            authors = reference.findall('front/author')
            for j, author in enumerate(authors):
                organization = author.find('organization')
                email = author.find('address/email')
                initials, surname = short_author_name_parts(author)
                initials = self.get_initials(author) or initials or ''
                a = None
                if j == len(authors) - 1 and len(authors) > 1:
                    last.tail = ' and '
                if surname is not None:
                    if j == len(authors) - 1 and len(authors) > 1:
                        # Last author, render in reverse
                        if len(initials) > 0:
                            name_string = initials + ' ' + surname
                        else:
                            name_string = surname
                    else:
                        if len(initials) > 0:
                            name_string = surname + ', ' + initials
                        else:
                            name_string = surname
                    a = E.A(name_string)
                    if email is not None and email.text:
                        if self.pis['linkmailto'] == 'yes':
                            a.attrib['href'] = 'mailto:' + email.text
                    if organization is not None and organization.text:
                        a.attrib['title'] = organization.text.strip()
                elif organization is not None and organization.text:
                    # Use organization instead of name
                    a = E.A(organization.text.strip())
                else:
                    continue
                ref_td.append(a)
                last = a
                a.tail = ', '
            title = reference.find('front/title')
            if title is not None and title.text:
                title_string = title.text.strip()
            else:
                xml2rfc.log.warn('No title specified in reference', \
                                 reference.attrib.get('anchor', ''))
                title_string = ''
            if title_string:
                if reference.attrib.get("quote-title", "true") == "true": # attribute default value: yes
                    if last is not None:
                        last.tail = ', "' 
                    else:
                        ref_td.text = '"'
                    title_a = E.A(title_string)
                    title_a.tail = '"'
                else:
                    if last is not None:
                        last.tail = ', '
                    title_a = E.A(title_string)
                    title_a.tail = ''
                ref_td.append(title_a)
            for seriesInfo in reference.findall('seriesInfo'):
                # Create title's link to document from seriesInfo
                if seriesInfo.attrib.get('name', '') == 'RFC':
                    title_a.attrib['href'] = \
                        self.html_defaults['references_url'] + \
                        'rfc' + seriesInfo.attrib.get('value', '')
                elif seriesInfo.attrib.get('name', '') == 'Internet-Draft':
                    title_a.attrib['href'] = \
                        self.html_defaults['references_url'] + \
                        seriesInfo.attrib.get('value', '')
                title_a.tail += ', '+seriesInfo.attrib.get('name', '') + ' ' + \
                             seriesInfo.attrib.get('value', '')
            if not title_a.attrib.has_key("href"):
                href = reference.attrib.get("target", None)
                if href:
                    title_a.attrib['href'] = href
            date = reference.find('front/date')
            if date is not None:
                month = date.attrib.get('month', '')
                if month.isdigit():
                    month = calendar.month_name[int(month)]
                year = date.attrib.get('year', '')
                if month or year:
                    title_a.tail += ', '
                    if month:
                        month += ' '
                    title_a.tail += month + year + '.'
            tr.append(bullet_td)
            tr.append(ref_td)
            refdict[bullet] = tr
            refkeys.append(bullet)
            # Render annotation as a separate paragraph
            annotation = reference.find('annotation')
            if annotation is not None and annotation.text:
                p = E.P()
                self.write_t_rec(annotation, parent=p)
                ref_td.append(p)
                    
        if self.pis['sortrefs'] == 'yes' and self.pis['symrefs'] == 'yes':
            refkeys.sort(key=str.lower)
        for key in refkeys:
            tbody.append(refdict[key])
        self.ref_start += i + 1                
        # Add to body buffer
        self.buf.append(self._serialize(E.TABLE(tbody)))

    def draw_table(self, table, table_num=None):
        style = 'tt %s %s' % ( table.attrib.get('style', self.defaults['table_style']),
                               table.attrib.get('align', self.defaults['table_align']) )
        cellpadding = '3'
        cellspacing = '0'
        htmltable = E.TABLE(cellpadding=cellpadding, )
        htmltable.attrib['cellspacing'] = cellspacing
        htmltable.attrib['class'] = style

        # Add caption, if it exists
        if 'title' in table.attrib and table.attrib['title']:
            caption = ''
            if table_num and self.pis['tablecount'] == 'yes':
                caption = 'Table ' + str(table_num) + ': '
            htmltable.append(E.CAPTION(caption + table.attrib['title']))

        # Draw headers
        header_row = E.TR()
        col_aligns = []
        for header in table.findall('ttcol'):
            th = E.TH()
            if header.text:
                th.text = header.text
            header_align = header.attrib.get('align',
                                             self.defaults['ttcol_align'])
            th.attrib['class'] = header_align
            # Store alignment information
            col_aligns.append(header_align)
            header_row.append(th)
        htmltable.append(E.THEAD(header_row))

        # Draw body
        body = E.TBODY()
        tr = E.TR()
        num_columns = len(col_aligns)
        for i, cell in enumerate(table.findall('c')):
            col_num = i % num_columns
            if col_num == 0 and i != 0:
                # New row
                body.append(tr)
                tr = E.TR()
            td = E.TD()
            if cell.text:
                # Add text
                td.text = cell.text
            for child in cell:
                # Add any inline elements (references)
                for element in self._expand_ref(child):
                    td.append(element)
            # Get alignment from header
            td.attrib['class'] = col_aligns[col_num]
            tr.append(td)
        body.append(tr)  # Add final row
        htmltable.append(body)

        # Add to body buffer
        self.buf.append(self._serialize(htmltable))

    def insert_anchor(self, text):
        # Add to body buffer
        self.buf.append(self._serialize(E.DIV(id=text)))

    def insert_iref_index(self):
        # Write the heading
        self.write_heading('Index', autoAnchor='rfc.index')
        table = E.TABLE()
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
            # Add letter element
            table.append(E.TR(E.TD(E.STRONG(letter))))
            for item in sorted(alpha_bucket[letter]):
                # Add item element
                anchor = self._iref_index[item].anchor or ''
                if anchor:
                    anchor = '#' + anchor
                    td = E.TD(E.A(item, href=anchor))
                else:
                    td = E.TD(item)
                table.append(E.TR(E.TD(' '), td))
                subkeys = list(self._iref_index[item].subitems.keys())
                subkeys.sort(key=str.upper)
                for name in subkeys:
                    subitem = self._iref_index[item].subitems[name]
                    # Add subitem element
                    td = E.TD()
                    td.text = (u'\u00a0\u00a0')  # Spaces
                    anchor = subitem.anchor or ''
                    anchor = '#' + anchor
                    td.append(E.A(name, href=anchor))
                    table.append(E.TR(E.TD(' '), td))

        self.buf.append(self._serialize(table))
    
    def pre_indexing(self):
        pass

    def pre_rendering(self):
        # Reset buffers
        self.buffers = {'front': [],
                        'body': [],
                        'header_rows': [],
                        'toc_head_links': [],
                        'toc_rows': []}
        self.list_counters = {}
        self.buf = self.buffers['front']
        self.cref_counter = 0

    def post_rendering(self):
        # Create table of contents buffers
        self._create_toc()
        
        # Grab values that haven't been inserted yet
        background_image = (self.pis['background'] and 
            "background-image:url('%s');" % self.pis['background'] or '')
        title = self.r.find('front/title').text or ''
        
        if self.rfcnumber:
            docName = ''
        else:
            docName = self.r.attrib.get('docName', '') 
        description = ''
        abs = self.r.find('front/abstract')
        if abs != None:
            description = ''.join(abs.itertext())
        keywords = self.r.findall('front/keyword')
        keyword_list = [keyword.text for keyword in keywords if keyword.text]
        generator = "xml2rfc version %s - https://tools.ietf.org/tools/xml2rfc" % xml2rfc.__version__

        # Build ISO8601 date string
        docDate = ''
        date = self.r.find('front/date')
        if date is not None:
            # We can assume AT LEAST year was defined in base.py from _format_date()
            docDate = date.attrib.get('year', '')
            try:
                month = datetime.datetime.strptime(date.attrib.get('month', ''), '%B').month
                docDate += "-%02d" % int(month)
            except ValueError:
                pass
            if date.attrib.get('day'):
                docDate += "-%02d" % int(date.attrib.get('day'))

        # Build author string
        authors = self.r.findall('front/author')
        authors = [ a for a in authors if a.get('role') != 'contributor' ]
        authors = self._format_author_string(authors)

        # Run through base template, store in main output string
        subs = { 
                 # Replace flat values 
                 'background':      background_image,

                 # HTML-escaped values
                 'docName':         escape(docName, quote=True),
                 'docDate':         escape(docDate, quote=True),
                 'description':     escape(description, quote=True),
                 'generator':       escape(generator, quote=True),
                 'authors':         escape(authors, quote=True),
                 'keywords':        escape(', '.join(keyword_list), quote=True),
                 'title':           escape(title, quote=False),
                 
                 # Replace buffers
                 'front':           ''.join(self.buffers['front']),
                 'body':            ''.join(self.buffers['body']),
                 'header_rows':     ''.join(self.buffers['header_rows']),
                 'toc_head_links':  ''.join(self.buffers['toc_head_links']),
                 'toc_rows':        ''.join(self.buffers['toc_rows'])
                }
        for key in subs.keys():
            subs[key] = subs[key].replace('\uE060', '\u2060').encode('ascii', 'xmlcharrefreplace').decode('ascii')
        self.output = self.templates['base.html'].substitute(subs)

    def post_process_lines(self, lines):
        return lines

    def write_to_file(self, file):
        file.write(self.output)

#-------------------------------------------------------------------------------
# Unused methods
#-------------------------------------------------------------------------------

    def write_title(self, title, docName=None, source_line=None):
        pass
