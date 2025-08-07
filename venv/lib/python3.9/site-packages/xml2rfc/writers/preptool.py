# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import copy
import datetime
import os
import re
import sys
import traceback as tb
import unicodedata

from codecs import open
from collections import defaultdict, namedtuple
from contextlib import closing

try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass

from urllib.parse import urlsplit, urlunsplit, urljoin, urlparse
from urllib.request import urlopen

from lxml import etree


from xml2rfc import strings, log
from xml2rfc.boilerplate_id_guidelines import boilerplate_draft_status_of_memo
from xml2rfc.boilerplate_rfc_7841 import boilerplate_rfc_status_of_memo
from xml2rfc.boilerplate_tlp import boilerplate_tlp
from xml2rfc.scripts import get_scripts
from xml2rfc.uniscripts import is_script
from xml2rfc.util.date import get_expiry_date, format_date, normalize_month
from xml2rfc.util.file import can_access, FileAccessError
from xml2rfc.util.name import full_author_name_expansion
from xml2rfc.util.num import ol_style_formatter
from xml2rfc.util.unicode import (
        unicode_content_tags, unicode_attributes, expand_unicode_element,
        isascii, latinscript_attributes, is_svg)
from xml2rfc.utils import build_dataurl, namespaces, sdict, clean_text
from xml2rfc.writers.base import default_options, BaseV3Writer, RfcWriterError


pnprefix = {
    # tag: prefix
    'abstract':     'section',
    'boilerplate':  'section',
    'toc':          'section',
    'figure':       'figure',
    'iref':         'iref',
    'note':         'section',
    'references':   'section',
    'section':      'section',
    'table':        'table',
    'u':            'u',
}

index_item = namedtuple('index_item', ['item', 'sub', 'anchor', 'anchor_tag', 'iref', ])

re_spaces = re.compile(r'\s+')

def uniq(l):
    seen = set()
    ll = []
    for i in l:
        if not i in seen:
            seen.add(i)
            ll.append(i)
    return ll


class PrepToolWriter(BaseV3Writer):
    """ Writes an XML file where the input has been modified according to RFC 7998"""

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None, liberal=None, keep_pis=['v3xml2rfc']):
        super(PrepToolWriter, self).__init__(xmlrfc, quiet=quiet, options=options, date=date)
        if not quiet is None:
            options.quiet = quiet
        self.rfcnumber = self.root.get('number')
        self.liberal = liberal if liberal != None else options.accept_prepped
        self.keep_pis = keep_pis
        #
        self.ol_counts = {}
        self.attribute_defaults = {}
        # 
        self.boilerplate_section_number = 0
        self.toc_section_number = 0
        self.note_number = 0
        self.middle_section_number = [0, ]
        self.table_number = 0
        self.figure_number = 0
        self.unicode_number = 0
        self.references_number = [0, ]
        self.back_section_number = [0, ]
        self.paragraph_number = [0, ]
        self.iref_number = 0
        #
        self.prev_section_level = 0
        self.prev_references_level = 0
        self.prev_paragraph_section = None
        #
        self.prepped = self.root.get('prepTime')
        #
        self.index_entries = []
        #
        self.spacer = '\u00a0\u00a0'
        #
        self.boilerplate_https_date = datetime.date(year=2017, month=8, day=21)
        #
        self._seen_slugs = set()  # This is used to enforce global uniqueness on slugs:

    def get_attribute_names(self, tag):
        attr = self.schema.xpath("/x:grammar/x:define/x:element[@name='%s']//x:attribute" % tag, namespaces=namespaces)
        names = [ a.get('name') for a in attr ]
        return names
        
    def get_attribute_defaults(self, tag):
        if not tag in self.attribute_defaults:
            ignored_attributes = set(['keepWithNext', 'keepWithPrevious', 'toc', 'pageno', ])
            attr = self.schema.xpath("/x:grammar/x:define/x:element[@name='%s']//x:attribute" % tag, namespaces=namespaces)
            defaults = dict( (a.get('name'), a.get("{%s}defaultValue"%namespaces['a'], None)) for a in attr )
            keys = set(defaults.keys()) - ignored_attributes
            self.attribute_defaults[tag] = sdict(dict( (k, defaults[k]) for k in keys if defaults[k] ))
        return copy.copy(self.attribute_defaults[tag])

    def set_element_pn(self, elt, value):
        existing_value = elt.get('pn', None)
        if existing_value is None:
            if self.prepped:
                self.warn(elt, 'pn not set on element in prepped input, setting to {}'.format(value))
            elt.set('pn', value)
        elif existing_value != value:
            self.warn(elt, 'using existing pn ({}) instead of generated pn ({})'.format(existing_value, value))

    def element(self, tag, line=None, **kwargs):
        attrib = self.get_attribute_defaults(tag)
        attrib.update(kwargs)
        e = etree.Element(tag, **sdict(attrib))
        if line:
            e.sourceline = line
        elif self.options.debug:
            filename, lineno, caller, code = tb.extract_stack()[-2]
            e.base = os.path.basename(filename)
            e.sourceline = lineno
        return e

    def slugify_name(self, name):
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
        slug = re.sub(r'[^\w\s/-]', '', name).strip().lower()
        slug = re.sub(r'[-\s/]+', '-', slug)
        # limit slug length
        n = 32
        m = 2
        while slug[:n] in self._seen_slugs and n < len(slug) and n < 40:
            n += 1
        while slug[:n] + '-%s' % m in self._seen_slugs and m < 99:
            m += 1
        if m == 99 and slug[:n] + '-%s' % m in self._seen_slugs:
            raise RuntimeError(
                "Too many overlapping <name> content instances; cannot create a sensible slugifiedName attribute")
        if slug[:n] in self._seen_slugs:
            slug = slug[:n] + '-%s' % m
        else:
            slug = slug[:n]
        self._seen_slugs.add(slug)
        return slug

    def validate(self, when, warn=False):
        return super(PrepToolWriter, self).validate(when='%s running preptool'%when, warn=warn)

    def write(self, filename):
        """ Public method to write the XML document to a file """

        if not self.options.quiet:
            self.log(' Prepping %s' % self.xmlrfc.source)
        self.prep()
        if self.errors:
            raise RfcWriterError("Not creating output file due to errors (see above)")

        # remove the processing instructions
        self.remove_pis()

        with open(filename, 'w', encoding='utf-8') as file:
            # Use lxml's built-in serialization
            text = etree.tostring(self.root.getroottree(),
                                            xml_declaration=True,
                                            encoding='utf-8',
                                            pretty_print=True)
            file.write(text.decode('utf-8'))

            if not self.options.quiet:
                self.log(' Created file %s' % filename)

    def normalize_whitespace(self, e):
        lines = e.text.split('\n')
        for i, line in enumerate(lines):
            # This strips unnecessary whitespace, and also works around an issue in
            # WeasyPrint where trailing whitespace in artwork can trigger something
            # akin to line wrapping even if rendered in <pre>: 
            line = line.rstrip()
            if '\t' in line:
                self.warn(e, "Found tab on line %d of <%s>: \n   %s" % (i+1, e.tag, line))
                line = line.expandtabs()                    
            lines[i] = line
        e.text = '\n'.join(lines)

    def prep(self):
        self._seen_slugs = set()  # Reset cache before prepping
        self.xinclude()
        # Set up reference mapping for later use.  Done here, and not earlier,
        # to capture any references pulled in by the XInclude we just did.
        self.refname_mapping = self.get_refname_mapping()
        self.remove_dtd()
        tree = self.dispatch(self.selectors)
        log.note(" Completed preptool run")
        return tree
        
    ## Selector notation: Some selectors below have a handler annotation,
    ## with the selector and the annotation separated by a semicolon (;).
    ## Everything from the semicolon to the end of the string is stripped
    ## before the selector is used as an XPath selector.
    selectors = [
        './/keyword',                       # 2.28.   Keyword
        '.;check_unnumbered_sections()',    # 2.46.2  "numbered" Attribute
                                            # 5.1.1.  XInclude Processing
                                            # 5.1.2.  DTD Removal
        '//processing-instruction();removal()',       # 5.1.3.  Processing Instruction Removal
        '.;validate_before()',              # 5.1.4.  Validity Check
        '/rfc;check_attribute_values()',
        '.;check_attribute_values()',       #
        '.;check_ascii_text()',
        '.;normalize_text_items()',
        './/bcp14;check_key_words()',
        './/*[@anchor]',                    # 5.1.5.  Check "anchor"
        '.;insert_version()',               # 5.2.1.  "version" Insertion
        './front;insert_series_info()',     # 5.2.2.  "seriesInfo" Insertion
        './front;insert_date())',           # 5.2.3.  <date> Insertion
        '.;insert_preptime()',              # 5.2.4.  "prepTime" Insertion
        './/ol[@group]',                    # 5.2.5.  <ol> Group "start" Insertion
        '//*;insert_attribute_defaults()',  # 5.2.6.  Attribute Default Value Insertion
        './/relref;to_xref()',
        './/section',                       # 5.2.7.  Section "toc" attribute
        './/note[@removeInRFC="true"]',     # 5.2.8.  "removeInRFC" Warning Paragraph
        './/section[@removeInRFC="true"]',
        '//*[@*="yes" or @*="no"]',         #         convert old attribute false/true
        './front/date',                     # 5.3.1.  "month" Attribute
        './/*[@ascii]',                     # 5.3.2.  ASCII Attribute Processing
        './front/author',
        './/contact',
        './/*[@title]',                     # 5.3.3.  "title" Conversion
        './/*[@keepWithPrevious="true"]',   # 5.3.4.  "keepWithPrevious" Conversion
        '.;fill_in_expires_date()',         # 5.4.1.  "expiresDate" Insertion
        './front;insert_boilerplate()',     # 5.4.2.  <boilerplate> Insertion
        './front;insert_toc()',
        '.;check_series_and_submission_type()', # 5.4.2.1.  Compare <rfc> "submissionType" and <seriesInfo> "stream"
        './/boilerplate;insert_status_of_memo()',  # 5.4.2.2.  "Status of This Memo" Insertion
        './/boilerplate;insert_copyright_notice()', # 5.4.2.3.  "Copyright Notice" Insertion
        './/boilerplate//section',          # 5.2.7.  Section "toc" attribute
        './/reference;insert_target()',     # 5.4.3.  <reference> "target" Insertion
        './/referencegroup;insert_target()',        # <referencegroup> "target" Insertion
        './/reference;insert_work_in_progress()',
        './/reference;sort_series_info()',  #         <reference> sort <seriesInfo>
        './/name;insert_slugified_name()',  # 5.4.4.  <name> Slugification
        './/references;sort()',             # 5.4.5.  <reference> Sorting
        './/references;add_derived_anchor()',
        './/references;check_usage()',
        './/*;insert_attribute_defaults()',  # 5.2.6.  Attribute Default Value Insertion
                                            # 5.4.6.  "pn" Numbering
        './/boilerplate//section;add_number()',
        './front//abstract;add_number()',
        './/front//note;add_number()',
        './/middle//section;add_number()',
        './/table;add_number()',
        './/figure;add_number()',
        './/references;add_number()',
        './/back//section;add_number()',
        '.;paragraph_add_numbers()',
        './/iref;add_number()',             # 5.4.7.  <iref> Numbering
        './/u;add_number()',
        './/ol;add_counter()',
        './/artset',                        #         <artwork> Processing
        './/artwork',                       # 5.5.1.  <artwork> Processing
        './/sourcecode',                    # 5.5.2.  <sourcecode> Processing
        #
        './back;insert_index()',
        './/xref',                          # 5.4.8.  <xref> Processing
        # Relref processing be handled under .//xref:
                                            # 5.4.9.  <relref> Processing
        './back;insert_author_address()',
        './/toc;insert_table_of_contents()',
        './/*[@removeInRFC="true"]',        # 5.6.1.  <note> Removal
        './/cref;removal()',                # 5.6.2.  <cref> Removal
                                            # 5.6.3.  <link> Processing
        './/link[@rel="alternate"];removal()',
        '.;check_links_required()',
        './/comment();removal()',           # 5.6.4.  XML Comment Removal
        '.;attribute_removal()',            # 5.6.5.  "xml:base" and "originalSrc" Removal
        '.;validate_after()',               # 5.6.6.  Compliance Check
        '.;insert_scripts()',               # 5.7.1.  "scripts" Insertion
        #'.;final_pi_removal()',            # Done in write().  Keep PIs when prep() is called interally
        '.;pretty_print_prep()',            # 5.7.2.  Pretty-Format
    ]

    # ----------------------------------------------------------------
    # 2.28.  <keyword>
    # 
    #    Specifies a keyword applicable to the document.
    # 
    #    Note that each element should only contain a single keyword; for
    #    multiple keywords, the element can simply be repeated.
    # 
    #    Keywords are used both in the RFC Index and in the metadata of
    #    generated document representations.
    # 
    #    This element appears as a child element of <front> (Section 2.26).
    # 
    #    Content model: only text content.
    def element_keyword(self, e, p):
#         if ',' in e.text or ' ' in e.text:
#             self.warn(e, "Expected a single keyword in the <keyword/> element, but found '%s'" % (e.text, ))
        pass

    # ----------------------------------------------------------------
    # 2.46.2.  "numbered" Attribute
    # 
    #    If set to "false", the formatter is requested to not display a
    #    section number.  The prep tool will verify that such a section is not
    #    followed by a numbered section in this part of the document and will
    #    verify that the section is a top-level section.
    def check_unnumbered_sections(self, e, p):
        def check_child_sections(e, unnumbered_parent=None):
            unnumbered_seen = None
            for s in e.iterchildren('section'):
                numbered = s.get('numbered', 'true')
                if   numbered == 'false':
                    unnumbered_seen = s
                elif unnumbered_parent != None:
                    self.err(s, "Did not expect a numbered section under an unnumbered parent section (seen on line %s)" % unnumbered_parent.sourceline)
                elif numbered == 'true':
                    if unnumbered_seen != None:
                        self.err(s, "Did not expect a numbered section after an unnumbered section (seen on line %s)" % unnumbered_seen.sourceline)
                check_child_sections(s, unnumbered_parent=(s if numbered=='false' else None))
        # 
        for tag in ['front', 'middle', 'back' ]:
            e = self.root.find(tag)
            if e != None:
                check_child_sections(e)

    # ----------------------------------------------------------------

    # 5.1.3.  Processing Instruction Removal
    # 
    #    Remove processing instructions.

    def processing_instruction_removal(self, e, p):
        if p != None:
            if not e.target in self.keep_pis:
                self.remove(p, e)

    def final_pi_removal(self, e, p):
        self.keep_pis = []
        for i in e.xpath('.//processing-instruction()'):
            self.processing_instruction_removal(i, i.getparent())

    def relref_to_xref(self, e, p):
        e.attrib['sectionFormat'] = e.attrib['displayFormat']
        del e.attrib['displayFormat']
        e.tag = 'xref'
        self.note(e, "Changed <relref> to <xref>, which now supports equivalent functionality.")
        
    # 5.1.4.  Validity Check
    # 
    #    Check the input against the RELAX NG (RNG) in [RFC7991].  If the
    #    input is not valid, give an error.

    # implemented in parent class: validate_before(self, e, p):


    def rfc_check_attribute_values(self, e,  p):
        doc_name = e.get('docName')
        if self.root.get('ipr') == '':
            # If the <rfc> ipr attribute is blank, it's a non-I*TF document
            if doc_name and doc_name.strip():
                if '.' in doc_name:
                    self.warn(e, "The 'docName' attribute of the <rfc/> element should not contain any filename extension: docName=\"draft-foo-bar-02\".")
                if not re.search(r'-\d\d$', doc_name):
                    self.warn(e, "The 'docName' attribute of the <rfc/> element should have a revision number as the last component: docName=\"draft-foo-bar-02\".")
            elif not self.options.rfc:
                self.warn(e, "Expected a 'docName' attribute in the <rfc/> element, but found none.")

    def check_attribute_values(self, e, p):
        # attribute names
        attribute_names = (
            ('quote-title', 'quoteTitle'),
        )
        for old, new in attribute_names:
            for o in self.root.findall('.//*[@%s]'%old):
                a = o.get(old)
                if a:
                    o.set(new, a)
                del o.attrib[old]


        # Integer attributes
        integer_attributes = {
            'rfc':      ('number', 'version', ),
            'date':     ('year', 'day', ),
            'dl':       ('indent', ),
            'format':   ('octets', ),
            'ol':       ('indent', ),
            't':        ('indent', ),
            'ul':       ('indent', ),
        }
        tags = integer_attributes.keys()
        for c in e.iter(tags):
            for a in integer_attributes[c.tag]:
                i = c.get(a)
                if i and not i.isdigit() and not i==self.get_attribute_defaults(c.tag).get(a):
                    self.err(c, 'Expected <%s> attribute "%s" to be a non-negative integer, but found "%s"' % (c.tag, a, i))


        # Attributes that may have leading or trailing space
        space_attributes = {
            ('u',       'format'),
            ('iref',    'item'),
            ('iref',    'subitem'),
        }
        for c in e.iter():
            if c.tag == etree.PI:
                continue
            for a in c.attrib:
                v = c.get(a)
                if not (c.tag, a) in unicode_attributes:
                    if (c.tag, a) in latinscript_attributes:
                        if not is_script(v, 'Latin'):
                            self.err(c, 'Found non-Latin-script content in <%s> attribute value %s="%s"' % (c.tag, a, v))
                    if self.options.warn_bare_unicode:
                        if not isascii(v):
                            self.warn(c, f'Found non-ASCII content in {c.tag} attribute value {a}="{v}" that should be inspected to ensure it is intentional.')
                if not (c.tag, a) in space_attributes:
                    vv = v.strip()
                    if vv != v:
                        self.note(c, 'Stripped extra whitespace in <%s> attribute value %s="%s"' % (c.tag, a, v))
                        c.set(a, vv)


        # Some attribute values we should check before we default set them,
        # such as some of the attributes on <rfc>:
        self.attribute_yes_no(e, p)
        #
        stream = self.root.get('submissionType')
        category = self.root.get('category')
        consensus = self.root.get('consensus')
        workgroup = self.root.find('./front/workgroup')
        #
        rfc_defaults = self.get_attribute_defaults('rfc')
        #
        stream_values = boilerplate_rfc_status_of_memo.keys()
        stream_default = rfc_defaults['submissionType']
        if not stream in stream_values:
            self.warn(self.root, "Expected a valid submissionType (stream) setting, one of %s, but found %s.  Will use '%s'" %
                                (', '.join(stream_values), stream, stream_default))
            stream = stream_default
        #
        category_values = boilerplate_rfc_status_of_memo[stream].keys()
        if not category in category_values:
            self.die(self.root, "Expected a valid category for submissionType='%s', one of %s, but found '%s'" %
                                (stream, ','.join(category_values), category, ))
        #
        consensus_values = list(boilerplate_rfc_status_of_memo[stream][category].keys())
        consensus_default = rfc_defaults['consensus']
        if stream == 'IRTF' and workgroup == None:
            if consensus:
                self.err(self.root, "Expected no consensus setting for IRTF stream and no workgroup, but found '%s'.  Ignoring it." % consensus)
            consensus = 'n/a'
        elif stream == 'independent' or stream == 'editorial':
            if consensus:
                self.err(self.root, "Expected no consensus setting for %s stream, but found '%s'.  Ignoring it." % (stream, consensus))
            consensus = 'n/a'
        elif consensus != None:
            pass
        else:
            if len(consensus_values) > 1:
                consensus = consensus_default
            else:
                consensus = consensus_values[0]
                if consensus != consensus_default:
                    self.warn(self.root, 'Setting consensus="%s" for %s %s document (this is not the schema default, but is the only value permitted for this type of document)' % (consensus, stream, category.upper()))
        if not consensus in consensus_values:
            if not consensus_default in consensus_values:
                self.die(self.root, "No valid consensus setting available.")
            else:
                self.warn(self.root, "Expected a valid consensus setting (one of %s), but found %s.  Will use '%s'" %
                                    (', '.join(consensus_values), consensus, consensus_default))
            consensus = consensus_default
        if consensus in ('true', 'false'):
            self.root.set('consensus', consensus)
        #

    def check_ascii_text(self, e, p):
        for c in self.root.iter():
            if is_svg(c):
                continue
            if c.text and not isascii(c.text) and c.tag not in unicode_content_tags:
                show = c.text.encode('ascii', errors='replace')
                if self.options.warn_bare_unicode:
                    self.warn(c, 'Found non-ascii characters in an element that should be inspected to ensure they are intentional, in <%s>: %s' % (c.tag, show))

    def normalize_text_items(self, e, p):
        """
        Normalize the text content of tags expected to hold a word, name,
        or similar, in order to get rid of newlines, double spaces etc.
        inserted just for editing convenience.
        """
        tags = [ 'area', 'bcp14', 'cityarea', 'code', 'country', 'date', 'email', 'extaddr',
                      'keyword', 'organization', 'phone', 'pobox', 'postalLine', 'sortingcode',
                      'street', 'uri', 'workgroup', 'region', 'title', ]
        for c in self.root.iter(tags):
            if c.text:
                t = c.text
                t = re.sub(r'[ \t\n\r\f\v]', ' ', t)        # convert \n\t etc. to space (not &nbsp; etc., though)
                t = re.sub(r'\.   +', '.  ', t)             # normalize period followed by more than 2 spaces
                t = re.sub(r'([^.])  +', r'\1 ', t)         # normalize non-period followed by more than one space
                t = t.strip()                               # strip leading and trailing spaces
                c.text = t
                
    def bcp14_check_key_words(self, e, p):
        # according to RFC 2119 and 8174
        permitted_words = [ "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
            "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", "OPTIONAL", ]
        text = re.sub(r'(\s|\u00a0)+', ' ', e.text, flags=re.UNICODE).strip()
        if not text in permitted_words:
            self.warn(e, "Expected one of the permitted words or phrases from RFC 2119 and RFC 8174 in <bcp14/>, "
                         "but found '%s'." % (etree.tostring(e).strip()))

    # 5.1.5.  Check "anchor"
    # 
    #    Check all elements for "anchor" attributes.  If any "anchor"
    #    attribute begins with "s-", "f-", "t-", or "i-", give an error.
    #
    ## modified to use "section-", "figure-", "table-", "index-"

    def attribute_anchor(self, e, p):
        if not self.prepped:
            reserved = set([ '%s-'%v for v in pnprefix.values() ])
            k = 'anchor'
            if k in e.keys():
                v = e.get(k)
                for prefix in reserved:
                    if v.startswith(prefix):
                        self.err(e, "Reserved anchor name: %s.  Don't use anchor names beginning with one of %s" % (v, ', '.join(reserved)))

    # 
    # 5.2.  Defaults
    # 
    #    These steps will ensure that all default values have been filled in
    #    to the XML, in case the defaults change at a later date.  Steps in
    #    this section will not overwrite existing values in the input file.
    # 
    # 5.2.1.  "version" Insertion
    # 
    #    If the <rfc> element has a "version" attribute with a value other
    #    than "3", give an error.  If the <rfc> element has no "version"
    #    attribute, add one with the value "3".

    def insert_version(self, e, p):
        version = e.get('version', None)
        if version and version != '3':
            self.err(e, "Expected <rfc version='3'>, found version='%s'" % (version,))
        e.set('version', '3')

    # 5.2.2.  "seriesInfo" Insertion
    # 
    #    If the <front> element of the <rfc> element does not already have a
    #    <seriesInfo> element, add a <seriesInfo> element with the name
    #    attribute based on the mode in which the prep tool is running
    #    ("Internet-Draft" for Draft mode and "RFC" for RFC production mode)
    #    and a value that is the input filename minus any extension for
    #    Internet-Drafts, and is a number specified by the RFC Editor for
    #    RFCs.
    def front_insert_series_info(self, e, p):
        series = e.xpath('seriesInfo')
        if self.root.get('ipr') == 'none':
            return
        if series == None:
            title = e.find('title')
            if title != None:
                pos = e.index(title)+1
            else:
                pos = 0
            path, base = os.path.split(self.options.output_filename)
            name, ext  = base.split('.', 1)
            if self.options.rfc:
                if not name.startswith('rfc'):
                    self.die(e, "Expected a filename starting with 'rfc' in RFC mode, but found '%s'" % (name, ))
                num = name[3:]
                if not num.isdigit():
                    self.die(e, "Expected to find the RFC number in the file name in --rfc mode, but found '%s'" % (num, ))
                e.insert(pos, self.element('seriesInfo', name='RFC', value=self.rfcnumber))
            else:
                e.insert(pos, self.element('seriesInfo', name='Internet-Draft', value=name))
        else:
            if self.options.rfc:
                rfcinfo = e.find('./seriesInfo[@name="RFC"]')
                if rfcinfo is None:
                    if self.rfcnumber:
                        self.warn(e, "Expected a <seriesInfo> element giving the RFC number in --rfc mode, but found none")
                    else:
                        self.die(e, "Expected a <seriesInfo> element giving the RFC number in --rfc mode, but found none")
                rfc_number = self.root.get('number')
                if rfc_number and rfcinfo!=None and rfc_number != rfcinfo.get('value'):
                    self.die(e, 'Mismatch between <rfc number="%s" ...> and <seriesInfo name="RFC" value="%s">' % (rfc_number, rfcinfo.get('value')))
                if not self.rfcnumber.isdigit():
                    self.die(rfcinfo, "Expected a numeric RFC number, but found '%s'" % (self.rfcnumber, ))
                    

    # 5.2.3.  <date> Insertion
    # 
    #    If the <front> element in the <rfc> element does not contain a <date>
    #    element, add it and fill in the "day", "month", and "year" attributes
    #    from the current date.  If the <front> element in the <rfc> element
    #    has a <date> element with "day", "month", and "year" attributes, but
    #    the date indicated is more than three days in the past or is in the
    #    future, give a warning.  If the <front> element in the <rfc> element
    #    has a <date> element with some but not all of the "day", "month", and
    #    "year" attributes, give an error.
    ## This tries to change the RFC Editor policy on publication dates
    ## (normally only indicating year and month, not day, of publication.  It
    ## also changes the heuristics that have been found helpful in v2.
    ## Disregarding most of this, and going with what seems to make sense.
    def front_insert_date(self, e, p):
        d = e.find('date')
        today = datetime.date.today()
        
        if d != None:
            year  = d.get('year')
            month = d.get('month')
            day   = d.get('day')
            if month and not month.isdigit():
                if len(month) < 3:
                    self.err(e, "Expected a month name with at least 3 letters, found '%s'" % (month, ))
                month = normalize_month(month)
            if not year:
                year = str(today.year)
            if not month:
                if year != str(today.year):
                    self.warn(e, "Expected <date> to have the current year when month is missing, but found '%s'" % (d.get('year')))
                month = today.strftime('%m')
                day = today.strftime('%d')
            datestr = "%s-%s-%s" %(year, month, day or '01')
            try:
                date = datetime.datetime.strptime(datestr, "%Y-%m-%d").date()
            except ValueError:
                self.die(e, '<date> {} is invalid'.format(datestr))
            if not self.rfcnumber and abs(date - datetime.date.today()) > datetime.timedelta(days=3):
                self.warn(d, "The document date (%s) is more than 3 days away from today's date" % date)
            n = self.element('date', year=year, month=month, line=d.sourceline)
            if day:
                n.set('day', day)
            e.replace(d, n)
        else:
            preceding = e.xpath('title|seriesInfo|author')
            pos = max(e.index(i) for i in preceding)+1
            date = self.options.date or datetime.date.today()
            year  = str(date.year)
            month = date.strftime('%m')
            day   = date.strftime('%d')
            e.insert(pos, self.element('date', year=year, month=month, day=day))
        self.date = datetime.date(year=int(year), month=int(month), day=int(day or '01'))

    # 5.2.4.  "prepTime" Insertion
    # 
    #    If the input document includes a "prepTime" attribute of <rfc>, exit
    #    with an error.
    # 
    #    Fill in the "prepTime" attribute of <rfc> with the current datetime.
    def insert_preptime(self, e, p):
        if 'prepTime' in e.attrib:
            if self.liberal:
                self.note(e, "Scanning already prepped source dated %s" % (e.get('prepTime'), ))
            else:
                self.die(e, "Did not expect a prepTime= attribute for <rfc>, but found '%s'" % (e.get('prepTime')))
        else:
            pn = e.xpath('.//*[@pn]')
            if pn and not self.liberal:
                self.die(e, "Inconsistent input.  Found pn numbers but no prepTime.  Cannot continue.")
            e.set('prepTime', datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))

    # 5.2.5.  <ol> Group "start" Insertion
    # 
    #    Add a "start" attribute to every <ol> element containing a group that
    #    does not already have a start.

    def attribute_ol_group(self, e, p):
        group = e.get('group')
        start = e.get('start')
        if start and not start.isdigit():
            self.warn(e, 'Expected the "start" attribute to have a numeric value, but found "%s".  Using "1"' %(start,))
            start = "1"
        if not group in self.ol_counts:
            self.ol_counts[group] = 1
        if not start:
            start = self.ol_counts[group]
            e.set('start', str(start))
        else:
            self.ol_counts[group] = int(start)
        self.ol_counts[group] += len(list(e.iterchildren('li')))

    # 5.2.6.  Attribute Default Value Insertion
    # 
    #    Fill in any default values for attributes on elements, except
    #    "keepWithNext" and "keepWithPrevious" of <t>, and "toc" of <section>.
    #    Some default values can be found in the RELAX NG schema, while others
    #    can be found in the prose describing the elements in [RFC7991].
    def insert_attribute_defaults(self, e, p):
        g = p.getparent() if p != None else None
        ptag = p.tag if p != None else None
        gtag = g.tag if g != None else None
        if not (gtag in ['reference', ] or ptag in ['reference', ]):
            defaults = self.get_attribute_defaults(e.tag)
            for k in defaults:
                if not k in e.attrib:
                    if (e.tag, k) in [('rfc', 'consensus')]:
                        continue
                    #debug.say('L%-5s: Setting <%s %s="%s">' % (e.sourceline, e.tag, k, defaults[k]))
                    if ':' in k:
                        ns, tag = k.split(':',1)
                        q = etree.QName(namespaces[ns], tag)
                        e.set(q, defaults[k])
                    else:
                        e.set(k, defaults[k])

    # 5.2.7.  Section "toc" attribute
    # 
    #    For each <section>, modify the "toc" attribute to be either "include"
    #    or "exclude":
    # 
    #    o  for sections that have an ancestor of <boilerplate>, use "exclude"
    # 
    #    o  else for sections that have a descendant that has toc="include",
    #       use "include".  If the ancestor section has toc="exclude" in the
    #       input, this is an error.
    # 
    #    o  else for sections that are children of a section with
    #       toc="exclude", use "exclude".
    # 
    #    o  else for sections that are deeper than rfc/@tocDepth, use
    #       "exclude"
    # 
    #    o  else use "include"
    def element_section(self, e, p):
        # we will process .//boilerplate//section elements correctly later,
        # so ignore that condition for now.
        etoc = e.get('toc')
        ptoc = p.get('toc')
        included_descendants = e.xpath('.//section[@toc="include"]')
        edepth = len([ a for a in e.iterancestors('section') ])+1
        if   etoc == 'include':
            pass
        elif etoc in [ None, 'default' ]:
            if included_descendants:
                e.set('toc', 'include')
            elif ptoc == 'exclude':
                e.set('toc', 'exclude')
            else:
                tocDepth = self.root.get('tocDepth', '3')
                if tocDepth.isdigit():
                    if edepth <= int(tocDepth):
                        e.set('toc', 'include')
                    else:
                        e.set('toc', 'exclude')
                else:
                    self.err(self.root, "Expected tocDepth to be an integer, but found '%s'" % (tocDepth))
        elif etoc == 'exclude':
            if included_descendants:
                self.err(e, 'Expected <section> to have toc="include", to match child section attribute, but found toc="exclude"')
        else:
            self.err(e, "Expected the toc attribute to be one of 'include', 'exclude', or 'default', but found '%s'" % etoc)
            

    # 5.2.8.  "removeInRFC" Warning Paragraph
    # 
    #    In I-D mode, if there is a <note> or <section> element with a
    #    "removeInRFC" attribute that has the value "true", add a paragraph to
    #    the top of the element with the text "This note is to be removed
    #    before publishing as an RFC." or "This section...", unless a
    #    paragraph consisting of that exact text already exists.
    def attribute_note_removeinrfc_true(self, e, p):
        if not self.options.rfc:
            warning_text = "This %s is to be removed before publishing as an RFC." % e.tag
            # Ignore the <name> element, if present. It must be the first child.
            if len(e) > 0 and e[0].tag == 'name':
                pos = 1
            else:
                pos = 0
            # Check whether the first child (after optional <name>) is a <t>
            first_child_tag = e[pos].tag if len(e) > pos else None
            top_para = e[pos] if first_child_tag == 't' else None
            # If no top_para, or if it is not the warning, then insert the warning
            if top_para is None or top_para.text != warning_text:
                t = self.element('t')
                t.text = warning_text
                e.insert(pos, t)

    def attribute_section_removeinrfc_true(self, e, p):
        self.attribute_note_removeinrfc_true(e, p)
    


    # 5.3.  Normalization
    # 
    #    These steps will ensure that ideas that can be expressed in multiple
    #    different ways in the input document are only found in one way in the
    #    prepared document.

    # The following is not specified or required, but will make life easier
    # later:
    def attribute_yes_no(self, e, p):
        for k,v in e.attrib.items():
            if   v == 'yes':
                e.set(k, 'true')
            elif v == 'no':
                e.set(k, 'false')

    # 5.3.1.  "month" Attribute
    # 
    #    Normalize the values of "month" attributes in all <date> elements in
    #    <front> elements in <rfc> elements to numeric values.
    def element_front_date(self, e, p):
        month = e.get('month')
        if not month.isdigit():
            e.set('month', normalize_month(month))

    # 5.3.2.  ASCII Attribute Processing
    # 
    #    In every <email>, <organization>, <street>, <city>, <region>,
    #    <country>, and <code> element, if there is an "ascii" attribute and
    #    the value of that attribute is the same as the content of the
    #    element, remove the "ascii" element and issue a warning about the
    #    removal.
    def attribute_ascii(self, e, p):
        if e.text.strip() == e.get('ascii').strip():
            del e.attrib['ascii']
            self.warn(e, "Removed a redundant ascii= attribute from <%s>" % (e.tag))

    #    In every <author> element, if there is an "asciiFullname",
    #    "asciiInitials", or "asciiSurname" attribute, check the content of
    #    that element against its matching "fullname", "initials", or
    #    "surname" element (respectively).  If the two are the same, remove
    #    the "ascii*" element and issue a warning about the removal.
    def element_front_author(self, e, p):
        fullname = e.get('fullname')
        initials = e.get('initials')
        surname  = e.get('surname')
        organization = e.find('organization')
        org = organization.text if organization != None and organization.text else None
        if not ((initials and surname) or fullname or org):
            self.err(e, "Expected <author> to have initials, surname and fullname or organization")
        if (initials or surname) and not fullname:
            e.set('fullname', ' '.join( n for n in [initials, surname] if n ))
        for a in ['fullname', 'initials', 'surname']:
            aa = 'ascii'+a.capitalize()
            keys = e.keys()
            if   aa in keys and not a in keys:
                self.err(e, "Expected a %s= attribute to match the %s= attribute, but found none" % (a, aa))
            elif a in keys and not aa in keys:
                if not is_script(e.get(a), 'Latin'):
                    self.err(e, "Expected an %s= attribute to match the unicode %s value" % (aa, a))
            elif a in keys and aa in keys:
                if e.get(a).strip() == e.get(aa).strip():
                    del e.attrib[aa]
                    self.warn(e, "Removed a redundant %s= attribute from <%s>" % (aa, e.tag))

    element_contact = element_front_author

    # 5.3.3.  "title" Conversion
    # 
    #    For every <section>, <note>, <figure>, <references>, and <texttable>
    #    element that has a (deprecated) "title" attribute, remove the "title"
    #    attribute and insert a <name> element with the title from the
    #    attribute.
    def attribute_title(self, e, p):
        title = e.get('title')
        del e.attrib['title']
        name = e.find('name')
        if title:
            if name is None:
                name = self.element('name', line=e.sourceline)
                name.text = title
                e.insert(0, name)
            else:
                self.warn(e, "Found both title attribute and <name> element for section; dropping the title.")

    # 5.3.4.  "keepWithPrevious" Conversion
    # 
    #    For every element that has a (deprecated) "keepWithPrevious" attribute,
    #    remove the "keepWithPrevious" attribute, and if its value is "true",
    #    and the previous element can have a "keepWithNext" element, remove
    #    "keepWithPrevious" and replace it with a "keepWithNext" attribute set
    #    to "true" on the previous element.
    def attribute_keepwithprevious_true(self, e, p):
        value = e.get('keepWithPrevious')
        # XXX TODO: This is too simple.  We need to find the previous
        # content-generating element of relevant types, probably something
        # like ['t', 'dl', 'ol', 'figure', 'table', ], and update that:
        prev = e.getprevious()          
        if prev is None:
            return
        prev_attrs = self.get_attribute_names(prev.tag)
        if value=='true' and prev!=None and 'keepWithNext' in prev_attrs:
            prev.set('keepWithNext', value)
            del e.attrib['keepWithPrevious']


    # 5.4.  Generation
    # 
    #    These steps will generate new content, overriding existing similar
    #    content in the input document.  Some of these steps are important
    #    enough that they specify a warning to be generated when the content
    #    being overwritten does not match the new content.
    # 
    # 5.4.1.  "expiresDate" Insertion
    # 
    #    If in I-D mode, fill in "expiresDate" attribute of <rfc> based on the
    #    <date> element of the document's <front> element.
    def fill_in_expires_date(self, e, p):
        return
        if not self.options.rfc:
            d = e.find('./front/date')
            date = datetime.date(year=int(d.get('year')), month=int(d.get('month')), day=int(d.get('day')))
            old_exp = e.get('expiresDate')
            new_exp = (date + datetime.timedelta(days=185)).strftime('%Y-%m-%d')
            if old_exp != new_exp:
                e.set('expiresDate', new_exp)
                if old_exp:
                    self.warn(e, "Changed the rfc expiresDate attribute to correspond with the <front><date> element: '%s'" % (new_exp, ))

    # 
    # 5.4.2.  <boilerplate> Insertion
    # 
    #    Create a <boilerplate> element if it does not exist.  If there are
    #    any children of the <boilerplate> element, produce a warning that
    #    says "Existing boilerplate being removed.  Other tools, specifically
    #    the draft submission tool, will treat this condition as an error" and
    #    remove the existing children.
    # 
    def front_insert_boilerplate(self, e, p):
        if self.root.get('ipr') == 'none':
            # no boilerplate
            return
        old_bp = e.find('boilerplate')
        new_bp = self.element('boilerplate')
        if old_bp != None:
            if not self.liberal and not self.prepped:
                children = old_bp.getchildren()
                if len(children):
                    self.warn(old_bp, "Expected no <boilerplate> element, but found one.  Replacing the content with new boilerplate")
                    for c in children:
                        old_bp.remove(c)
            elif not self.rfcnumber:
                for c in old_bp.getchildren():
                    old_bp.remove(c)
        else:
            e.append(new_bp)

    def front_insert_toc(self, e, p):
        old_toc = e.find('toc')
        new_toc = self.element('toc')
        if old_toc != None:
            if not self.liberal and not self.prepped:
                children = old_toc.getchildren()
                if len(children):
                    self.warn(old_toc, "Expected no <toc> element, but found one.  Replacing the content with new toc")
                    for c in children:
                        old_toc.remove(c)
            elif not self.rfcnumber:
                for c in old_toc.getchildren():
                    old_toc.remove(c)
        else:
            e.append(new_toc)

    # 5.4.2.1.  Compare <rfc> "submissionType" and <seriesInfo> "stream"
    # 
    #    Verify that <rfc> "submissionType" and <seriesInfo> "stream" are the
    #    same if they are both present.  If either is missing, add it.  Note
    #    that both have a default value of "IETF".
    def check_series_and_submission_type(self, e, p):
        submission_type = e.get('submissionType')
        series_info_list = e.xpath('./front/seriesInfo')
        streams = [ i.get('stream') for i in series_info_list if i.get('stream') ] + [ submission_type ]
        if len(set(streams)) > 1:
            if submission_type:
                self.err(series_info_list[0], "The stream setting of <seriesInfo> is inconsistent with the submissionType of <rfc>.  Found %s" % (', '.join(streams)))
            else:
                self.err(series_info_list[0], "The stream settings of the <seriesInfo> elements are inconsistent.  Found %s" % (', '.join(streams)))
        else:
            stream = list(streams)[0]
            if stream:
                e.set('submissionType', stream)
                for i in series_info_list:
                    i.set('stream', stream)

    # 5.4.2.2.  "Status of This Memo" Insertion
    # 
    #    Add the "Status of This Memo" section to the <boilerplate> element
    #    with current values.  The application will use the "submissionType",
    #    and "consensus" attributes of the <rfc> element, the <workgroup>
    #    element, and the "status" and "stream" attributes of the <seriesInfo>
    #    element, to determine which boilerplate from [RFC7841] to include, as
    #    described in Appendix A of [RFC7991].
    def boilerplate_insert_status_of_memo(self, e, p):
        if self.prepped and self.rfcnumber:
            return
        if self.root.get('ipr') == 'none':
            return
        # submissionType: "IETF" | "IAB" | "IRTF" | "independent" | "editorial"
        # consensus: "false" | "true"
        # category: "std" | "bcp" | "exp" | "info" | "historic"
        b = e.xpath('./section/name[text()="Status of This Memo"]')
        existing_status_of_memo = b[0] if b else None
        if existing_status_of_memo:
            if self.liberal:
                self.note(e, "Boilerplate 'Status of this Memo' section exists, leaving it in place")
                return
            else:
                e.remove(existing_status_of_memo)
        #
        section = self.element('section', numbered='false', toc='exclude', anchor='status-of-memo')
        name = self.element('name')
        name.text = "Status of This Memo"
        section.append(name)
        format_dict = {}
        format_dict['scheme'] = 'http' if self.date < self.boilerplate_https_date else 'https'
        #
        if self.options.rfc:
            stream = self.root.get('submissionType')
            category = self.root.get('category')
            consensus = self.root.get('consensus')
            workgroup = self.root.find('./front/workgroup')
            if not category in strings.category_name:
                self.err(self.root, "Expected a known category, one of %s, but found '%s'" % (','.join(strings.category_name.keys()), category, ))
            #
            group = workgroup.text if workgroup != None else None
            format_dict.update({ 'rfc_number': self.rfcnumber })
            if group:
                format_dict['group_name'] = group
            #
            if stream == 'IRTF' and workgroup == None:
                consensus = 'n/a'
            elif stream == 'independent' or stream == 'editorial':
                consensus = 'n/a'
            try:
                for para in boilerplate_rfc_status_of_memo[stream][category][consensus]:
                    para = para.format(**format_dict).strip()
                    t = etree.fromstring(para)
                    section.append(t)
            except KeyError as exception:
                if str(exception) in ["'rfc_number'", "'group_name'"]:
                    # Error in string expansion
                    self.die(p, 'Expected to have a value for %s when expanding the "Status of This Memo" boilerplate, but found none.' % str(exception))
                else:
                    # Error in boilerplate dictionary indexes
                    self.die(self.root, 'Unexpected attribute combination(%s): <rfc submissionType="%s" category="%s" consensus="%s">' % (exception, stream, category, consensus))

        else:
            exp = get_expiry_date(self.tree, self.date)
            format_dict['expiration_date'] = format_date(exp.year, exp.month, exp.day, legacy=self.options.legacy_date_format)
            for para in boilerplate_draft_status_of_memo:
                para = para.format(**format_dict).strip()
                t = etree.fromstring(para)
                section.append(t)
        e.append(section)            

    # 5.4.2.3.  "Copyright Notice" Insertion
    # 
    #    Add the "Copyright Notice" section to the <boilerplate> element.  The
    #    application will use the "ipr" and "submissionType" attributes of the
    #    <rfc> element and the <date> element to determine which portions and
    #    which version of the Trust Legal Provisions (TLP) to use, as
    #    described in A.1 of [RFC7991].
    def boilerplate_insert_copyright_notice(self, e, p):
        if self.prepped and self.rfcnumber:
            return
        ipr = self.root.get('ipr', '').lower()
        if ipr == 'none':
            return
        b = e.xpath('./section/name[text()="Copyright Notice"]')
        existing_copyright_notice = b[0] if b else None
        if existing_copyright_notice:
            if self.liberal:
                self.note(e, "Boilerplate 'Copyright Notice' section exists, leaving it in place")
                return
            else:
                e.remove(existing_copyright_notice)
        #
        tlp_2_start_date = datetime.date(year=2009, month=2, day=15)
        tlp_3_start_date = datetime.date(year=2009, month=9, day=12)
        tlp_4_start_date = datetime.date(year=2009, month=12, day=28)
        ipr = self.root.get('ipr', '').lower()
        subtype = self.root.get('submissionType')
        if not ipr:
            self.die(self.root, "Missing ipr attribute on <rfc> element.")
        if not ipr.endswith('trust200902'):
            self.die(self.root, "Unknown ipr attribute: %s" % (self.root.get('ipr'), ))
        #
        if   self.date < tlp_2_start_date:
            self.die(e, "Cannot insert copyright statements earlier than TLP2.0, effective %s" % (tlp_2_start_date))
        elif self.date < tlp_3_start_date:
            tlp = "2.0"
            stream = "n/a"
        elif self.date < tlp_4_start_date:
            tlp = "3.0"
            stream = "n/a"
        else:
            # The only difference between 4.0 and 5.0 is selective URL scheme,
            # which we handle using the http cutover date, through interpolation:
            tlp = "5.0"                 
            stream = 'IETF' if subtype == 'IETF' else 'alt'
        format_dict = {'year': self.date.year, }
        format_dict['scheme'] = 'http' if self.date < self.boilerplate_https_date else 'https'
        section = self.element('section', numbered='false', toc='exclude', anchor='copyright')
        name = self.element('name')
        name.text = "Copyright Notice"
        section.append(name)
        paras = []
        paras += boilerplate_tlp[tlp][stream][:]
        if   ipr.startswith('nomodification'):
            paras += boilerplate_tlp[tlp]['noModification'][:]
        elif ipr.startswith('noderivatives'):
            paras += boilerplate_tlp[tlp]['noDerivatives'][:]
        elif ipr.startswith('pre5378'):
            paras += boilerplate_tlp[tlp]['pre5378'][:]
        for para in paras:
            para = para.format(**format_dict).strip()
            t = etree.fromstring(para)
            section.append(t)
        e.append(section)

    # 5.2.7.  Section "toc" attribute
    # 
    #    ...
    #    o  for sections that have an ancestor of <boilerplate>, use "exclude"    

    def element_boilerplate_section(self, e, p):
        e.set('toc', 'exclude')

    # 5.4.3.  <reference> "target" Insertion
    # 
    #    For any <reference> element that does not already have a "target"
    #    attribute, fill the target attribute in if the element has one or
    #    more <seriesinfo> child element(s) and the "name" attribute of the
    #    <seriesinfo> element is "RFC", "Internet-Draft", or "DOI" or other
    #    value for which it is clear what the "target" should be.  The
    #    particular URLs for RFCs, Internet-Drafts, and Digital Object
    #    Identifiers (DOIs) for this step will be specified later by the RFC
    #    Editor and the IESG.  These URLs might also be different before and
    #    after the v3 format is adopted.
    def reference_insert_target(self, e, p):
        target_pattern = {
            "RFC":              os.path.join(self.options.rfc_base_url, 'rfc{value}'),
            "Internet-Draft":   os.path.join(self.options.id_base_url,  '{value}'),
            "DOI":              os.path.join(self.options.doi_base_url, '{value}'),
        }
        # datatracker.ietf.org has code to deal with draft urls (text, html, and pdf) lacking
        # extension, but others may not.  www.ietf.org/archive/id/ only has .txt versions:
        if urlparse(self.options.id_base_url).netloc != 'datatracker.ietf.org':
            target_pattern["Internet-Draft"] = os.path.join(self.options.id_base_url, '{value}.txt')

        if not e.get('target'):
            for c in e.xpath('.//seriesInfo'):
                series_name = c.get('name')
                if series_name in target_pattern.keys():
                    series_value=c.get('value')
                    if series_value:
                        e.set('target', target_pattern[series_name].format(value=series_value))
                        break
                    else:
                        self.err(c, 'Expected a value= attribute value for <seriesInfo name="%s">, but found none' % (series_name, ))

    def reference_insert_work_in_progress(self, e, p):
        if self.options.id_is_work_in_progress:
            for c in e.xpath('.//seriesInfo'):
                series_name = c.get('name')
                if series_name in ['Internet-Draft', ]:
                    for refcontent in e.xpath('.//refcontent'):
                        if refcontent.text == "Work in Progress":
                            break
                    else:
                        refcontent = self.element('refcontent')
                        refcontent.text = "Work in Progress"
                        e.append(refcontent)

    def reference_sort_series_info(self, e, p):
        def series_order(s):
            name = s.get('name')
            series_order = { 'STD': 1, 'BCP': 2, 'FYI': 3, 'RFC': 4, 'DOI': 5, }
            if name in series_order:
                return series_order[name]
            else:
                return sys.maxsize
        front = e.find('front')
        series_info = front.xpath('./seriesInfo')
        series_info.sort(key=lambda x: series_order(x) )
        pos = sys.maxsize
        for s in series_info:
            i = front.index(s)
            if i < pos:
                pos = i
            front.remove(s)
        for s in series_info:
            front.insert(pos, s)
            pos += 1

    def referencegroup_insert_target(self, e, p):
        target_pattern = {
            "BCP": os.path.join(self.options.info_base_url, 'bcp{value}'),
            "STD": os.path.join(self.options.info_base_url, 'std{value}'),
            "FYI": os.path.join(self.options.info_base_url, 'fyi{value}'),
        }

        if not e.get('target'):
            for c in e.xpath('.//seriesInfo'):
                series_name = c.get('name')
                if series_name in target_pattern.keys():
                    series_value=c.get('value')
                    if series_value:
                        e.set('target', target_pattern[series_name].format(value=series_value))
                        break
                    else:
                        self.err(c, 'Expected a value= attribute value for <seriesInfo name="%s">, but found none' % (series_name, ))

    # 
    # 5.4.4.  <name> Slugification
    # 
    #    Add a "slugifiedName" attribute to each <name> element that does not
    #    contain one; replace the attribute if it contains a value that begins
    #    with "n-".
    def name_insert_slugified_name(self, e, p):
        text = ' '.join(list(e.itertext()))
        slug = self.slugify_name('name-'+text) if text else None
        if slug:
            e.set('slugifiedName', slug)
        
    # 
    # 5.4.5.  <reference> Sorting
    # 
    #    If the "sortRefs" attribute of the <rfc> element is true, sort the
    #    <reference> and <referencegroup> elements lexically by the value of
    #    the "anchor" attribute, as modified by the "to" attribute of any
    #    <displayreference> element.  The RFC Editor needs to determine what
    #    the rules for lexical sorting are.  The authors of this document
    #    acknowledge that getting consensus on this will be a difficult task.
    def references_sort(self, e, p):
        sort_refs = (self.root.get('sortRefs', 'true') == 'true') and (self.root.get('symRefs', 'true') == 'true')
        if sort_refs:
            children = e.xpath('./reference') + e.xpath('./referencegroup')
            children.sort(key=lambda x: self.refname_mapping[x.get('anchor')].upper() )
            for c in children:
                e.remove(c)
            if len(e):
                e[-1].tail = ''
            for c in children:
                e.append(c)

    def references_add_derived_anchor(self, e, p):
        children = e.xpath('./reference') + e.xpath('./referencegroup')
        for c in children:
            anchor = c.get('anchor')
            c.set('derivedAnchor', self.refname_mapping[anchor])

    def references_check_usage(self, e, p):
        children = e.xpath('./reference') + e.xpath('./referencegroup')
        for c in children:
            anchor = c.get('anchor')
            if not (   self.root.xpath('.//xref[@target="%s"]'%anchor)
                    or self.root.xpath('.//relref[@target="%s"]'%anchor)):
                        x = c if getattr(c, 'base') == getattr(e, 'base') else c.getparent()
                        self.warn(x, "Unused reference: There seems to be no reference to [%s] in the document" % anchor)

    # 5.4.6.  "pn" Numbering
    # 
    #    Add "pn" attributes for all parts.  Parts are:
    # 
    #    o  <section> in <middle>: pn='s-1.4.2'
    # 
    #    o  <references>: pn='s-12' or pn='s-12.1'
    # 
    #    o  <abstract>: pn='s-abstract'
    # 
    #    o  <note>: pn='s-note-2'
    # 
    #    o  <section> in <boilerplate>: pn='s-boilerplate-1'
    # 
    #    o  <table>: pn='t-3'
    # 
    #    o  <figure>: pn='f-4'
    # 
    #    o  <artwork>, <aside>, <blockquote>, <dt>, <li>, <sourcecode>, <t>:
    #       pn='p-[section]-[counter]'
    #
    # N.B., the pn formats have changed from the above comment.
    #
    def boilerplate_section_add_number(self, e, p):
        self.boilerplate_section_number += 1
        self.set_element_pn(e, '%s-boilerplate.%s' % (pnprefix[e.tag], self.boilerplate_section_number, ))

    def toc_section_add_number(self, e, p):
        self.toc_section_number += 1
        self.set_element_pn(e, '%s-toc.%s' % (pnprefix[e.tag], self.toc_section_number, ))

    def front_abstract_add_number(self, e, p):
        self.set_element_pn(e, '%s-abstract' % pnprefix[e.tag])

    def front_note_add_number(self, e, p):
        self.note_number += 1
        self.set_element_pn(e, '%s-note.%s' % (pnprefix[e.tag], self.note_number, ))

    def middle_section_add_number(self, e, p):
        level = len(list(e.iterancestors('section')))
        if level > self.prev_section_level:
            self.middle_section_number.append(0)
        self.middle_section_number[level] += 1
        if level < self.prev_section_level:
            self.middle_section_number = self.middle_section_number[:level+1]
        self.set_element_pn(e, '%s-%s' % (pnprefix[e.tag], '.'.join([ str(n) for n in self.middle_section_number ]), ))
        self.prev_section_level = level
        self.references_number[0] = self.middle_section_number[0]

    def table_add_number(self, e, p):
        self.table_number += 1
        self.set_element_pn(e, '%s-%s' % (pnprefix[e.tag], self.table_number, ))

    def figure_add_number(self, e, p):
        self.figure_number += 1
        self.set_element_pn(e, '%s-%s' % (pnprefix[e.tag], self.figure_number, ))

    def u_add_number(self, e, p):
        self.unicode_number += 1
        self.set_element_pn(e, '%s-%s' % (pnprefix[e.tag], self.unicode_number, ))

    def references_add_number(self, e, p):
        level = len(list(e.iterancestors('references')))
        if level > self.prev_references_level:
            self.references_number.append(0)
        self.references_number[level] += 1
        if level < self.prev_references_level:
            self.references_number = self.references_number[:level+1]
        self.set_element_pn(e, '%s-%s' % (pnprefix[e.tag], '.'.join([ str(n) for n in self.references_number ]), ))
        self.prev_references_level = level

    def back_section_add_number(self, e, p):
        level = len(list(e.iterancestors('section')))
        if level > self.prev_section_level:
            self.back_section_number.append(0)
        self.back_section_number[level] += 1
        if level < self.prev_section_level:
            self.back_section_number = self.back_section_number[:level+1]
        section_number = self.back_section_number[:]
        if section_number[0] > 26:
            # avoid running off the end of the alphabet when assigning appendix letters
            self.err(e, '<back> has at least %s sections, only 26 supported' % section_number[0])
        section_number[0] = chr(0x60+section_number[0])
        self.set_element_pn(e, '%s-appendix.%s' % (pnprefix[e.tag], '.'.join([ str(n) for n in section_number ]), ))
        self.prev_section_level = level

    def paragraph_add_numbers(self, e, p):
        # In this case, we need to keep track of separate paragraph number
        # sequences as we descend to child levels and return.  Handle this by
        # recursive descent.
        def child(s, prefix=None, num=[]):
            def num2str(num):
                return '.'.join([ str(n) for n in num ])
            #
            para_tags = ['artset', 'artwork', 'aside', 'blockquote', 'list', 'dl', 'dd', 'ol', 'ul', 'dt', 'li', 'sourcecode', 't', 'figure', 'table', ]
            bloc_tags = ['thead', 'tbody', 'tfoot', 'tr', 'td', ]
            sect_tags = ['abstract', 'note', 'section', 'references' ]
            skip_tags = ['reference', ]
            if s.tag in sect_tags:
                if not s.get('pn'):
                    self.warn(s, "Expected a pn number, found none in <%s>" % (s.tag, ))
                prefix = s.get('pn', 'unknown-unknown')+'-'
                num = [0, ]
            for c in s:
                if c.tag in para_tags:
                    if prefix is None:
                        debug.show('s.tag')
                        debug.show('s.items()')
                        debug.show('c.tag')
                        debug.show('c.items()')
                    num[-1] += 1
                    if c.tag not in ['figure', 'table']:
                        self.set_element_pn(c, prefix+num2str(num))
                elif c.tag in bloc_tags:
                    num[-1] += 1
                if c.tag in sect_tags:
                    child(c, num)
                elif c.tag in skip_tags:
                    pass
                else:
                    num.append(0)
                    num = child(c, prefix, num)
                    num = num[:-1]
            return num
        child(e)

    # 5.4.7.  <iref> Numbering
    # 
    #    In every <iref> element, create a document-unique "pn" attribute.
    #    The value of the "pn" attribute will start with 'i-', and use the
    #    item attribute, the subitem attribute (if it exists), and a counter
    #    to ensure uniqueness.  For example, the first instance of "<iref
    #    item='foo' subitem='bar'>" will have the "irefid" attribute set to
    #    'i-foo-bar-1'.
    def iref_add_number(self, e, p):
        def get_anchor(parent):
            # Walk up the tree until an anchored or numbered element is encountered
            while parent is not None:
                # <reference> elements inside a <referencegroup> are not labeled with their
                # own anchor, so skip up to the <referencegroup> element.
                if parent.tag == 'reference':
                    grandparent = parent.getparent()
                    if grandparent.tag == 'referencegroup':
                        parent = grandparent
                anchor = parent.get('anchor') or parent.get('pn')
                if anchor:
                    return anchor, parent.tag
                parent = parent.getparent()
            return None, None

        item = e.get('item')
        sub  = e.get('subitem')
        self.iref_number += 1
        if not item:
            self.err(e, "Expected <iref> to have an item= attribute, but found none")
        else:
            if sub:
                pn = self.slugify_name('%s-%s-%s-%s' % (pnprefix[e.tag], item, sub, self.iref_number))
            else:
                pn = self.slugify_name('%s-%s-%s' % (pnprefix[e.tag], item, self.iref_number))
            self.set_element_pn(e, pn)
            anchor, anchor_tag = get_anchor(p)
            if not anchor:
                self.err(e, "Did not find an anchor to use for <iref item='%s'> in <%s>" % (item, p.tag))
            else:
                self.index_entries.append(index_item(re_spaces.sub(' ', item), sub, anchor, anchor_tag, e))

    def ol_add_counter(self, e, p):
        start = e.get('start')
        if not start.isdigit():
            self.warn(e, "Expected a numeric value for the 'start' attribute, but found %s" % (etree.tostring(e), ))
            start = '1'
        counter = int(start)
        #
        type = e.get('type')
        if not type:
            self.warn(e, "Expected the 'type' attribute to have a string value, but found %s" % (etree.tostring(e), ))
            type = '1'
        #
        if len(type) > 1:
            if '%p' in type:
                pcounter = None
                for p in e.iterancestors('li'):
                    pcounter = p.get('derivedCounter')
                    if pcounter:
                        type = type.replace('%p', pcounter )
                        break
                if not pcounter:
                    self.err(e, "Expected an outer list to fetch the '%p' parent counter value from, but found none")
            formspec = re.search('%([cCdiIoOxX])', type)
            if formspec:
                fchar = formspec.group(1)
                fspec = formspec.group(0)
                format = type.replace(fspec, '%s')
            else:
                self.err(e, "Expected an <ol> format specification of '%%' followed by upper- or lower-case letter, of one of c,d,i,o,x; but found '%s'" % (type, ))
                fchar = 'd'
                format = '%s'
        else:
            fchar = type
            format = '%s.'
        #
        int2str = ol_style_formatter[fchar]
        for c in e.getchildren():
            if c.tag == 'li':           # not PI or Comment
                label = format % int2str(counter)
                counter += 1
                c.set('derivedCounter', label)
                
    # 5.4.8.  <xref> Processing
    # 
    # 5.4.8.1.  "derivedContent" Insertion (with Content)
    # 
    #    For each <xref> element that has content, fill the "derivedContent"
    #    with the element content, having first trimmed the whitespace from
    #    ends of content text.  Issue a warning if the "derivedContent"
    #    attribute already exists and has a different value from what was
    #    being filled in.
    # 
    # 5.4.8.2.  "derivedContent" Insertion (without Content)
    # 
    #    For each <xref> element that does not have content, fill the
    #    "derivedContent" attribute based on the "format" attribute.
    # 
    #    o  For a value of "counter", the "derivedContent" is set to the
    #       section, figure, table, or ordered list number of the element with
    #       an anchor equal to the <xref> target.
    # 
    #    o  For format='default' and the "target" attribute points to a
    #       <reference> or <referencegroup> element, the "derivedContent" is
    #       the value of the "target" attribute (or the "to" attribute of a
    #       <displayreference> element for the targeted <reference>).
    # 
    #    o  For format='default' and the "target" attribute points to a
    #       <section>, <figure>, or <table>, the "derivedContent" is the name
    #       of the thing pointed to, such as "Section 2.3", "Figure 12", or
    #       "Table 4".
    # 
    #    o  For format='title', if the target is a <reference> element, the
    #       "derivedContent" attribute is the name of the reference, extracted
    #       from the <title> child of the <front> child of the reference.
    # 
    #    o  For format='title', if the target element has a <name> child
    #       element, the "derivedContent" attribute is the text content of
    #       that <name> element concatenated with the text content of each
    #       descendant node of <name> (that is, stripping out all of the XML
    #       markup, leaving only the text).
    # 
    #    o  For format='title', if the target element does not contain a
    #       <name> child element, the "derivedContent" attribute is the value
    #       of the "target" attribute with no other adornment.  Issue a
    #       warning if the "derivedContent" attribute already exists and has a
    #       different value from what was being filled in.
    def build_derived_content(self, e):
        def split_pn(t, pn):
            if pn is None:
                self.die(e, "Expected to find a pn= attribute on <%s anchor='%s'> when processing <xref>, but found none" % (t.tag, t.get('anchor')), trace=True)
            type, num, para = self.split_pn(pn)
            if self.is_appendix(pn):
                type = 'appendix'
            return type.capitalize(), num.title(), para
        #
        def get_name(t):
            """Get target element name or None"""
            name = t if t.tag == 'name' else t.find('./name')
            return None if name is None else clean_text(''.join(list(name.itertext())))
        #
        target = e.get('target')
        if not target:
            self.die(e, "Expected <xref> to have a target= attribute, but found none")
        t = self.root.find('.//*[@anchor="%s"]'%(target, ))
        if t is None:
            t = self.root.find('.//*[@pn="%s"]'%(target, ))
            if t is None:
                t = self.root.find('.//*[@slugifiedName="%s"]'%(target, ))
                if t is None:
                    self.die(e, "Found no element to match the <xref> target attribute '%s'" % (target, ))
        #
        p = t
        pn = None
        while p != None and pn == None:
            pn = p.get('pn')
            p = p.getparent()

        #
        format = e.get('format', 'default')
        content = ''
        if format == 'counter':
            if not t.tag in ['section', 'table', 'figure', 'li', 'reference', 'references', 't', 'dt', ]:
                self.die(e, "Using <xref> format='%s' with a <%s> target is not supported" % (format, t.tag, ))
            elif t.tag == 'reference':
                if not e.get('section'):
                    self.die(e, "Using <xref> format='%s' with a <%s> target requires a section attribute" % (format, t.tag, ))
            _, num, _ = split_pn(t, pn)
            if t.tag == 'li':
                parent = t.getparent()
                if not parent.tag == 'ol':
                    self.die(e, "Using <xref> format='counter' with a <%s><%s> target is not supported" %(parent.tag, t.tag, ))
                content = t.get('derivedCounter').rstrip('.')
            elif t.tag == 'reference':
                content = e.get('section')
            else:
                content = num
        elif format == 'default':
            if t.tag in [ 'reference', 'referencegroup' ]:
                anchor = t.get('anchor')
                content = '%s' % self.refname_mapping[anchor] if anchor in self.refname_mapping else anchor
            elif t.tag in [ 't', 'ul', 'ol', 'dl', ]:
                type, num, para = split_pn(t, pn)
                content = "%s %s, Paragraph %s" % (type, num, para)
            elif t.tag in [ 'li', ]:
                type, num, para = split_pn(t, pn)
                para, item = para.split('.', 1)
                content = "%s %s, Paragraph %s, Item %s" % (type, num, para, item)
            elif t.tag == 'u':
                try:
                    content = expand_unicode_element(t, bare=True)
                except (RuntimeError, ValueError) as exc:
                    self.err(t, '%s' % exc)
            elif t.tag in ['author', 'contact']:
                content = full_author_name_expansion(t)
            elif t.tag in ['abstract']:
                content = t.tag.capitalize()
            elif t.tag in ['cref']:
                content = "Comment %s" % target
            else:
                # If section is numbered, refer by number, otherwise use section name if available
                numbered = t.get('numbered') != 'false'
                type, num, _ = split_pn(t, pn)
                if numbered:
                    label = num
                else:
                    label = '"%s"' % (get_name(t) or target)
                content = "%s %s" % (type, label)
        elif format == 'title':
            if t.tag in ['u', 'author', 'contact', ]:
                self.die(e, "Using <xref> format='%s' with a <%s> target is not supported" % (format, t.tag, ))
            elif t.tag == 'reference':
                title = t.find('./front/title')
                if title is None:
                    self.err(t, "Expected a <title> element when processing <xref> to <%s>, but found none" % (t.tag, ))
                content = clean_text(title.text)
            elif t.tag in ['abstract']:
                content = t.tag.capitalize()
            else:
                name = get_name(t)
                content = name if name is not None else target
        elif format == 'none':
            if self.options.verbose and not e.text:
                self.warn(e, 'Expected <%s format="none"> to have text content, but found none.  There will be no text rendered for this element.' % (e.tag, ))
        else:
            self.err(e, "Expected format to be one of 'default', 'title', 'counter' or 'none', but found '%s'" % (format, ) )
        return t, content

    def element_xref(self, e, p):
        section = e.get('section')
        relative = e.get('relative')
        t, content = self.build_derived_content(e)
        is_toc = p.get('pn', '').startswith('section-toc')
        if not (section or relative):
            attr = e.get('derivedContent')
            if self.options.verbose and attr and attr != content:
                self.err(e, "When processing <xref>, found derivedContent='%s' when trying to set it to '%s'" % (attr, content))
            if not is_toc:
                e.set('derivedContent', content)
        else:
            if relative != None and section is None:
                self.err(e, "Cannot render an <%s> with a relative= attribute without also having a section= attribute." % (e.tag))
            if t.tag != 'reference':
                self.err(e, "Expected the target of an <%s> with a section= attribute to be a <reference>, found <%s>" % (e.tag, t.tag, ))
            if relative is None:
                for s in t.xpath('.//seriesInfo'):
                    if s.get('name') in ['RFC', 'Internet-Draft']:
                        if section[0].isdigit():
                            relative = '#section-%s' % section.title()
                        else:
                            relative = '#appendix-%s' % section.title()
                        break
                if not relative:
                    self.err(e, 'Cannot build a href for <%s target="%s"> with a section= attribute without also having a relative= attribute.' % (e.tag, e.get('target')))
            if relative:
                url = t.get('target')
                if self.options.rfc_reference_base_url:
                    ss = t.xpath('.//seriesInfo[@name="RFC"]')
                    if ss:
                        num = ss[0].get('value')
                        url = urljoin(self.options.rfc_reference_base_url, "rfc%s" % num)
                if self.options.id_reference_base_url:
                    ss = t.xpath('.//seriesInfo[@name="Internet-Draft"]')
                    if ss:
                        name = ss[0].get('value')
                        url = urljoin(self.options.id_reference_base_url, name)
                if url is None:
                    self.err(e, "Cannot build a href for <reference anchor='%s'> without having a target= attribute giving the URL." % (t.get('anchor'), ))
                link = urljoin(url, relative, allow_fragments=True)
                e.set('derivedLink', link)
            attr = e.get('derivedContent')
            if attr and attr != content:
                self.err(e, "When processing <xref>, found derivedContent='%s' when trying to set it to '%s'" % (attr, content))
            e.set('derivedContent', content)
            #
            sform  = e.get('sectionFormat')
            if   sform in ['of', 'comma', 'parens', ]:
                if not content:
                    self.err(e, 'Found sectionFormat="%s" with blank derivedContent' % sform)
            elif sform == 'bare':
                format = e.get('format')
                if format in ['title', 'counter', 'none', ]:
                    self.warn(e, 'Unexpected format="%s" used with sectionFormat="bare".  Setting format has no effect with sectionFormat="bare"' % (format, ))
            else:
                self.err(e, 'Unexpected sectionFormat: "%s"' % (sform, ))

    # 5.4.9.  <relref> Processing
    # 
    #    If any <relref> element's "target" attribute refers to anything but a
    #    <reference> element, give an error.
    # 
    #    For each <relref> element, fill in the "derivedLink" attribute.


    # 5.5.  Inclusion
    # 
    #    These steps will include external files into the output document.
    # 
    # 5.5.1.  <artwork> Processing
    # 
    def check_src_scheme(self, e, src):
        permitted_schemes = ['file', 'http', 'https', 'data', ]
        scheme, netloc, path, query, fragment = urlsplit(src)
        if scheme == '':
            scheme = 'file'
        if not scheme in permitted_schemes:
            self.err(e, "Expected an <%s> src scheme of '%s:', but found '%s:'" % (e.tag, scheme, ":', '".join(permitted_schemes)))
        return (scheme, netloc, path, query, fragment)

    def check_src_file_path(self, e, scheme, netloc, path, query, fragment):
        try:
            can_access(self.options, self.xmlrfc.source, path)
        except FileAccessError as err:
            self.err(e, err)
            return None
        #
        dir = os.path.abspath(os.path.dirname(self.xmlrfc.source))
        path = os.path.abspath(os.path.join(dir, path))
        src = urlunsplit((scheme, '', path, '', ''))
        #
        e.set('src', src)
        return src

    def element_artset(self, e, p):
        anchors = [ w.get('anchor') for w in e.xpath('./artwork[@anchor]') ]
        if anchors:
            anchors.sort()
            if not e.get('anchor'):
                e.set('anchor', anchors[0])
                self.warn(e, "Moved anchor '%s' on <artset><artwork> up to <artset>" % anchors[0])
            if len(anchors) > 1:
                if e.get('anchor') == anchors[0]:
                    self.warn(e, "Found multiple anchors on <artwork> within <artset>.  Please use an anchor on <artset> instead.")
                    self.warn(e, "-- Keeping anchor '%s', discarding '%s'." % (anchors[0], "', '".join(anchors[1:])))
                else:
                    self.warn(e, "Found an anchor on <artset>, but also multiple anchors on <artwork> within <artset>.  Please use only the one on <artset>.")
                    self.warn(e, "-- Discarding anchors '%s'." % ("', '".join(anchors)))
            for w in e.xpath('./artwork[@anchor]'):
                del w.attrib['anchor']

    def element_artwork(self, e, p):

    #    1.  If an <artwork> element has a "src" attribute where no scheme is
    #        specified, copy the "src" attribute value to the "originalSrc"
    #        attribute, and replace the "src" value with a URI that uses the
    #        "file:" scheme in a path relative to the file being processed.
    #        See Section 7 for warnings about this step.  This will likely be
    #        one of the most common authoring approaches.

        src = e.get('src','').strip()
        if src:
            original_src = src
            data = None
            scheme, netloc, path, query, fragment = self.check_src_scheme(e, src)

    #    2.  If an <artwork> element has a "src" attribute with a "file:"
    #        scheme, and if processing the URL would cause the processor to
    #        retrieve a file that is not in the same directory, or a
    #        subdirectory, as the file being processed, give an error.  If the
    #        "src" has any shellmeta strings (such as "`", "$USER", and so on)
    #        that would be processed, give an error.  Replace the "src"
    #        attribute with a URI that uses the "file:" scheme in a path
    #        relative to the file being processed.  This rule attempts to
    #        prevent <artwork src='file:///etc/passwd'> and similar security
    #        issues.  See Section 7 for warnings about this step.
            if scheme == 'file':
                src = self.check_src_file_path(e, scheme, netloc, path, query, fragment)

            if src != original_src:
                e.set('originalSrc', original_src)

    #    3.  If an <artwork> element has a "src" attribute, and the element
    #        has content, give an error.

            if e.text and e.text.strip():
                self.err(e, "Found <artwork> with both a 'src' attribute and content.  Please use <artset> with multiple <artwork> instances instead.")
                e.text = None

    #    4.  If an <artwork> element has type='svg' and there is an "src"
    #        attribute, the data needs to be moved into the content of the
    #        <artwork> element.

            if src:                             # Test again, after check_src_file_path()
                awtype = e.get('type')
                if awtype is None:
                    self.warn(e, "No 'type' attribute value provided for <artwork>, cannot process source %s" % src)
                elif awtype == 'svg':

    #        *  If the "src" URI scheme is "data:", fill the content of the
    #           <artwork> element with that data and remove the "src"
    #           attribute.

    #        *  If the "src" URI scheme is "file:", "http:", or "https:", fill
    #           the content of the <artwork> element with the resolved XML
    #           from the URI in the "src" attribute.  If there is no
    #           "originalSrc" attribute, add an "originalSrc" attribute with
    #           the value of the URI and remove the "src" attribute.

                    if scheme in ['file', 'http', 'https', 'data']:
                        with closing(urlopen(src)) as f:
                            data = f.read()
                        svg = etree.fromstring(data)
                        e.append(svg)
                        del e.attrib['src']
                    else:
                        self.err(e, "Unexpected <artwork> src scheme: '%s'" % scheme)

    #        *  If the <artwork> element has an "alt" attribute, and the SVG
    #           does not have a <desc> element, add the <desc> element with
    #           the contents of the "alt" attribute.
                    alt = e.get('alt')
                    if alt and svg != None:
                        if not svg.xpath('.//desc'):
                            desc = self.element('{%s}desc'%namespaces['svg'], line=e.sourceline)
                            desc.text = alt
                            desc.tail = '\n'
                            desc.sourceline = e.sourceline
                            svg.insert(0, desc)
                            del e.attrib['alt']

    #    5.  If an <artwork> element has type='binary-art', the data needs to
    #        be in an "src" attribute with a URI scheme of "data:".  If the
    #        "src" URI scheme is "file:", "http:", or "https:", resolve the
    #        URL.  Replace the "src" attribute with a "data:" URI, and add an
    #        "originalSrc" attribute with the value of the URI.  For the
    #        "http:" and "https:" URI schemes, the mediatype of the "data:"
    #        URI will be the Content-Type of the HTTP response.  For the
    #        "file:" URI scheme, the mediatype of the "data:" URI needs to be
    #        guessed with heuristics (this is possibly a bad idea).  This also
    #        fails for content that includes binary images but uses a type
    #        other than "binary-art".  Note: since this feature can't be used
    #        for RFCs at the moment, this entire feature might be
                elif awtype == 'binary-art':
                    # keep svg in src attribute
                    if scheme in ['http', 'https']:
                        with closing(urlopen(src)) as f:
                            data = f.read()
                            mediatype = f.info().get_content_type()
                        src = build_dataurl(mediatype, data)
                        e.set('src', src)
                    elif scheme == 'file':
                        self.err(e, "Won't guess media-type of file '%s', please use the data: scheme instead." % (src, ))

    #    6.  If an <artwork> element does not have type='svg' or
    #        type='binary-art' and there is an "src" attribute, the data needs
    #        to be moved into the content of the <artwork> element.  Note that
    #        this step assumes that all of the preferred types other than
    #        "binary-art" are text, which is possibly wrong.
    # 
    #        *  If the "src" URI scheme is "data:", fill the content of the
    #           <artwork> element with the correctly escaped form of that data
    #           and remove the "src" attribute.
    # 
    #        *  If the "src" URI scheme is "file:", "http:", or "https:", fill
    #           the content of the <artwork> element with the correctly
    #           escaped form of the resolved text from the URI in the "src"
    #           attribute.  If there is no "originalSrc" attribute, add an
    #           "originalSrc" attribute with the value of the URI and remove
    #           the "src" attribute.
                else:
                    if scheme in ['file', 'http', 'https', 'data']:
                        try:
                            with closing(urlopen(src)) as f:
                                data = f.read().decode('utf-8')
                            e.text = data
                        except Exception as ex:
                            self.err(e, "Discarded unexpected <artwork> content with type='%s': '%s'" % (awtype, ex))
                        del e.attrib['src']
                    else:
                        self.err(e, "Unexpected <artwork> src scheme: '%s'" % scheme)

                if src and not data:
                    self.warn(e, "No image data found in source %s" % src)

        if e.get('type') == 'ascii-art' and e.text:
            self.normalize_whitespace(e)

    # 5.5.2.  <sourcecode> Processing

    def element_sourcecode(self, e, p):
    #    1.  If a <sourcecode> element has a "src" attribute where no scheme
    #        is specified, copy the "src" attribute value to the "originalSrc"
    #        attribute and replace the "src" value with a URI that uses the
    #        "file:" scheme in a path relative to the file being processed.
    #        See Section 7 for warnings about this step.  This will likely be
    #        one of the most common authoring approaches.
        src = e.get('src','').strip()
        if src:
            original_src = src
            scheme, netloc, path, query, fragment = self.check_src_scheme(e, src)


    #    2.  If a <sourcecode> element has a "src" attribute with a "file:"
    #        scheme, and if processing the URL would cause the processor to
    #        retrieve a file that is not in the same directory, or a
    #        subdirectory, as the file being processed, give an error.  If the
    #        "src" has any shellmeta strings (such as "`", "$USER", and so on)
    #        that would be processed, give an error.  Replace the "src"
    #        attribute with a URI that uses the "file:" scheme in a path
    #        relative to the file being processed.  This rule attempts to
    #        prevent <sourcecode src='file:///etc/passwd'> and similar
    #        security issues.  See Section 7 for warnings about this step.
            if scheme == 'file':
                src = self.check_src_file_path(e, scheme, netloc, path, query, fragment)
                if src != original_src:
                    e.set('originalSrc', original_src)

    #    3.  If a <sourcecode> element has a "src" attribute, and the element
    #        has content, give an error.
            srctext = (' '.join(list(e.itertext()))).strip()
            if srctext:
                self.err(e, "Expected either external src= content, or element content for <%s>, but found both" % (e.tag, ))

    #    4.  If a <sourcecode> element has a "src" attribute, the data needs
    #        to be moved into the content of the <sourcecode> element.
    # 
    #        *  If the "src" URI scheme is "data:", fill the content of the
    #           <sourcecode> element with that data and remove the "src"
    #           attribute.
    # 
    #        *  If the "src" URI scheme is "file:", "http:", or "https:", fill
    #           the content of the <sourcecode> element with the resolved XML
    #           from the URI in the "src" attribute.  If there is no
    #           "originalSrc" attribute, add an "originalSrc" attribute with
    #           the value of the URI and remove the "src" attribute.

            if src:                             # Test again, after check_src_file_path()
                with closing(urlopen(src)) as f:
                    data = f.read()
                e.text = data
                del e.attrib['src']

        if e.text:
            self.normalize_whitespace(e)
        
    #
    # 5.4.2.4  "Table of Contents" Insertion
    # 5.4.2.4  "Table of Contents" Insertion
    def toc_insert_table_of_contents(self, e, p):
        if self.prepped and self.rfcnumber:
            return
        self.keep_toc_lines = 3
        # Number of lines to keep as a block at the start of the ToC
        def copy_reduce(e):
            """
            <xref> content may not contain all elements permitted in <name>,
            so we need to reduce any child elements of <name> which are not
            permitted in <xref> to plain text.
            """
            ee = copy.deepcopy(e)
            for c in ee.iterdescendants():
                if not c.tag in self.xref_tags:
                    # bcp14 cref eref iref xref
                    # The following is simplified.  both <xref> and <eref> could do with more
                    # sophisticated rendering.
                    prev = c.getprevious()
                    if prev != None:
                        if   c.tag == 'xref' and not c.text:
                            prev.tail = (prev.tail or '') + c.get('derivedContent', '') + (c.tail or '')
                        elif c.tag == 'eref' and not c.text:
                            prev.tail = (prev.tail or '') + c.get('target', '') + (c.tail or '')
                        else:                    
                            prev.tail = (prev.tail or '') + (c.text or '') + (c.tail or '')
                    else:
                        prnt = c.getparent()
                        if c.tag == 'xref' and not c.text:
                            prnt.text = (prnt.text or '') + c.get('derivedContent', '') + (c.tail or '')
                        else:                    
                            prnt.text = (prnt.text or '') + (c.text or '') + (c.tail or '')
                    c.getparent().remove(c)
            return ee
            
        def toc_entry_t(s):
            name = s.find('./name')
            if name is None:
                self.die(s, "No name entry found for section, can't continue")
            numbered = s.get('numbered')=='true' or (self.check_refs_numbered() if s.tag == 'references' else False)

            pn = s.get('pn')
            if not pn:
                self.warn(s, "Expected a pn number, found none in <%s>" % (s.tag, ))
                self.die(s, "No no pn entry found for section, can't continue: %s" % (etree.tostring(s)))

            if not numbered:
                num = ''
                num_format = 'none'
            else:
                # numbered
                _, num, _ = self.split_pn(pn)
                num = num.title()
                if self.is_appendix(pn) and self.is_top_level_section(num):
                    num_format = 'default'
                    num = 'Appendix %s' % num
                else:
                    num_format = 'counter'
            #
            if self.keep_toc_lines > 0:
                t = self.element('t', keepWithNext='true')
                self.keep_toc_lines -= 1
            else:
                t = self.element('t')

            xref = self.element('xref', target=pn, format=num_format, derivedContent=num)
            xref.tail = ('.'+self.spacer) if num.strip() else ( self.spacer if num else '')
            t.append(xref)
            # <xref> can only contain text, not markup. so we need to reduce
            # the name content to plain text:
            text = clean_text(''.join(name.itertext()))
            if text:
                slug = name.get('slugifiedName')
                if not slug:
                    self.warn(name, "Internal error: missing slugifiedName for %s" % (etree.tostring(name)))
                    slug = self.slugify_name('name-'+text)
                    name.set('slugifiedName', slug)
                xref = self.element('xref', target=slug, format='title', derivedContent='')
                cc = copy_reduce(name)
                xref.text = cc.text
                xref.extend(cc.getchildren())
                t.append(xref)
            return t
        def toc_entries(e):
            toc = e.get('toc')
            if toc == 'include' or e.tag in ['rfc', 'front', 'middle', 'back', 'references', ]:
                sub = []
                for c in e:
                    l = toc_entries(c)
                    if l:
                        sub += l
                if sub:
                    li = sub[0]
                    m = len(li.find('t').find('xref').get('derivedContent'))
                    for li in sub:
                        xref = li.find('t').find('xref')
                        num = xref.get('derivedContent')
                        l = len(num)
                        if (l > m
                            and xref.tail[-1] in [' ', '\u00a0', ] and xref.tail[-2] in [' ', '\u00a0', ]
                            and not num.startswith('Appendix')):
                            xref.tail = xref.tail[:-1]
                if e.tag in ['section', 'references', ]:
                    li = self.element('li')
                    li.append(toc_entry_t(e))
                    if sub:
                        ul = self.element('ul', empty='true', spacing='compact', bare="true", indent="2")
                        for s in sub:
                            ul.append(s)
                        li.append(ul)
                    return [ li ]
                else:
                    return sub
            return []
        if self.root.get('tocInclude') == 'true':
            toc = self.element('section', numbered='false', toc='exclude', anchor='toc')
            name = self.element('name')
            name.text = "Table of Contents"
            toc.append(name)
            self.name_insert_slugified_name(name, toc)
            ul = self.element('ul', empty='true', spacing='compact', bare="true", indent="2")
            toc.append(ul)
            for s in toc_entries(self.root):
                ul.append(s)
            e.append(toc)
            #
            self.toc_section_add_number(toc, e)
            self.paragraph_add_numbers(toc, e)

    #
    def back_insert_index(self, e, p):
        oldix = self.root.find('./back/section/t[@anchor="rfc.index.index"]')
        if oldix != None:
            self.warn(e, "Found an existing Index section, not inserting another one")
            return

        # Helper methods
        def mkxref(self, text, **kwargs):
            kwargs = sdict(kwargs)
            xref = self.element('xref', **kwargs)
            if text:
                xref.text = text
            return xref

        def bin_item_entries(item_entries, bin_by='item'):
            """Bin together item entries with like attributes

            Returns a dict whose keys are items and values are an ordered list of entries.
            Items with no value for the attr will appear with '' as the key.
            """
            binned = defaultdict(lambda: [])  # missing values initialized to empty lists
            for entry in item_entries:
                binned[getattr(entry, bin_by) or ''].append(entry)
            return binned

        def letter_li(letter, letter_entries):
            """Generate <li> element for a letter's entries

            <li>
              <t><xref>A</xref></t>
              <ul><li>
                <dl>
                  <dt>item 1</dt><dd>[references]</dd>
                  <dt/><dd> [only if there are subitems]
                    [contents from sub_dl()]
                  </dd>
                  <dt>item 2</dt><dd>[references]</dd>
                  [...]
                </dl>
              </li></ul>
            </li>
            """
            binned_entries = bin_item_entries(letter_entries)
            anchor = letter_anchor(letter)
            li = self.element('li')
            t = self.element('t', anchor=anchor, keepWithNext='true')
            t.text = '\n' + ' ' * 12
            xref = mkxref(self, letter, target=anchor, format='none')
            xref.tail = (xref.tail or '') + '\n'
            t.append(xref)
            li.append(t)
            #
            ul = self.element('ul', empty='true', spacing='compact')
            li.append(ul)
            li2 = self.element('li')
            ul.append(li2)
            dl = self.element('dl', spacing='compact')
            li2.append(dl)
            # sort entries - py36 does not guarantee order and later versions use LIFO order
            for item in sorted(binned_entries, key=str.casefold):
                regular_entries = []
                sub_entries = []
                for i in binned_entries[item]:
                    if i.sub is None:
                        regular_entries.append(i)
                    else:
                        sub_entries.append(i)
                # first add the item heading and any regular entries
                for elt in entry_dt_dd(item, regular_entries, 18):
                    dl.append(elt)
                # now add any sub-entries
                if len(sub_entries) > 0:
                    dl.append(self.element('dt'))
                    sub_dd = self.element('dd')
                    dl.append(sub_dd)
                    sub_dd.append(sub_dl(sub_entries))
            return li

        def sub_dl(sub_elements):
            """Generate <dl> for a subitem entry

            <dl>
              <dt>subitem 1</dt>
              <dd>[references]</dd>
              [...]
            </dl>
            """
            binned_subs = bin_item_entries(sub_elements, bin_by='sub')
            sub_dl = self.element('dl', spacing='compact')
            for sub in sorted(binned_subs):
                entries = binned_subs[sub]
                for elt in entry_dt_dd(sub, entries, 22):
                    sub_dl.append(elt)
            return sub_dl

        def entry_dt_dd(label, entries, indent):
            """Definition list <dt>/<dd> pair for either a list item or subitem

            <dt>item</dt>
            and
            <dd>
              <t>
                <xref target="first entry"/>
                <xref target="second entry"/>
                [...]
              </t>
            </dd>
            """
            dt = self.element('dt')
            dt.text = label
            dd = self.element('dd')
            if len(entries) > 0:
                t = self.element('t')
                t.text = '\n' + ' ' * (indent + 2)
                dd.append(t)
                anchored_entries = [e for e in entries if e.anchor]
                for index, ent in enumerate(anchored_entries):
                    xr = mkxref(
                        self,
                        text='Reference' if ent.anchor_tag in ['reference', 'referencegroup'] else None,
                        target=ent.anchor,
                    )
                    if ent.iref.get('primary') == 'true':
                        xr_em = self.element('em')
                        xr_em.append(xr)
                        xr = self.element('strong')
                        xr.append(xr_em)
                    t.append(xr)
                    if index < len(anchored_entries) - 1:
                        xr.tail = '; '
                    xr.tail = (xr.tail or '') + '\n'
            return dt, dd

        def index_letter(entry):
            return entry.item[0].upper()

        def letter_anchor(letter):
            """Get an anchor string for a letter

            The anchor must be a valid XML name, restricted to US ASCII A-Z,a-z,0-9,_,-,.,:,
            with 0-9, ., and - disallowed for leading characters. To guarantee this, even for
            non-alphanumeric "letters," the letter character is encoded to UTF8 bytes and
            its decimal representation is used in the anchor string.
            """
            return 'rfc.index.u{}'.format(int.from_bytes(letter.encode(), byteorder='big'))

        def index_sort(letters):
            """Sort letters for the index

            Sorts symbols ahead of alphanumerics to keep ASCII symbols together.
            """
            return sorted(
                letters,
                key=lambda letter: (letter.isalnum(), letter)
            )

        # done defining helpers, resume back_insert_index() flow
        if self.index_entries and self.root.get('indexInclude') == 'true':
            # remove duplicate entries
            entries = {}
            for entry in self.index_entries:
                uniq_key = (entry.item, entry.anchor)
                entries.setdefault(uniq_key, entry)  # keeps only the first for each key
            self.index_entries = list(entries.values())
            #
            index = self.element('section', numbered='false', toc='include')
            name = self.element('name')
            name.text = 'Index'
            index.append(name)
            self.name_insert_slugified_name(name, index)
            #
            index_index = self.element('t', anchor='rfc.index.index')
            index_index.text = '\n'+' '*8
            index.append(index_index)
            # sort the index entries
            self.index_entries.sort(key=lambda i: '%s~%s' % (i.item, i.sub or ''))
            # get the first letters
            letters = index_sort(uniq([ index_letter(i) for i in self.index_entries ]))
            # set up the index index
            for letter in letters:
                xref = mkxref(self, letter, target=letter_anchor(letter), format='none')
                xref.tail = '\n'
                index_index.append(xref)
            # one letter entry per letter
            index_ul = self.element('ul', empty='true', spacing='normal')
            index.append(index_ul)
            for letter in letters:
                letter_entries = [ i for i in self.index_entries if index_letter(i) == letter ]
                index_ul.append(letter_li(letter, letter_entries))
            #
            e.append(index)
            #
            self.back_section_add_number(index, e)
            self.paragraph_add_numbers(index, e)


    def back_insert_author_address(self, e, p):
        if self.prepped:
            return
        old = self.root.find('./back/section[@anchor="authors-addresses"]')
        if old != None:
            self.warn(e, "Found an existing Authors' Addresses section, not inserting another one")
            return
        authors = self.root.findall('./front/author')
        # Exclude contributors
        authors = [ a for a in authors if a.get('role') != 'contributor' ]
        back = self.root.find('./back')
        line = back[-1].sourceline or back.sourceline if len(back) else back.sourceline
        s = self.element('section', toc='include', numbered='false', anchor='authors-addresses', line=line)
        n = self.element('name', line=line+1)
        if len(authors) > 1:
            n.text = "Authors' Addresses"
        else:
            n.text = "Author's Address"
        n.set('slugifiedName', self.slugify_name('name-'+n.text))
        s.append(n)
        for e in self.root.find('./front'):
            if e.tag in ['author', etree.PI, ]:
                s.append(copy.copy(e))
        back.append(s)
        #
        self.back_section_add_number(s, e)
        self.paragraph_add_numbers(s, e)


    # 5.6.  RFC Production Mode Cleanup
    # 
    #    These steps provide extra cleanup of the output document in RFC
    #    production mode.
    # 
    # 5.6.1.  <note> Removal
    # 
    #    In RFC production mode, if there is a <note> or <section> element
    #    with a "removeInRFC" attribute that has the value "true", remove the
    #    element.
    def attribute_removeinrfc_true(self, e, p):
        if self.options.rfc:
            p.remove(e)

    # 5.6.2.  <cref> Removal
    # 
    #    If in RFC production mode, remove all <cref> elements.
    def cref_removal(self, e, p):
        if self.options.rfc:
            self.remove(p, e)

    # 5.6.3.  <link> Processing
    def attribute_link_rel_alternate_removal(self, e, p):
        if self.options.rfc:
    #    1.  If in RFC production mode, remove all <link> elements whose "rel"
    #        attribute has the value "alternate".
            if e.get('rel') == 'alternate':
                p.remove(e)
                return

    #    2.  If in RFC production mode, check if there is a <link> element
    #        with the current ISSN for the RFC series (2070-1721); if not, add
    #        <link rel="item" href="urn:issn:2070-1721">.
    def check_links_required(self, e, p):
        if self.options.rfc:
            item_href = "urn:issn:2070-1721"
            urnlink = e.find('.//link[@rel="item"][@href="%s"]' % (item_href, ))
            if urnlink is None :
                e.insert(0, self.element('link', href=item_href, rel='alternate'))
    #    3.  If in RFC production mode, check if there is a <link> element
    #        with a DOI for this RFC; if not, add one of the form <link
    #        rel="describedBy" href="https://dx.doi.org/10.17487/rfcdd"> where
    #        "dd" is the number of the RFC, such as
    #        "https://dx.doi.org/10.17487/rfc2109".  The URI is described in
    #        [RFC7669].  If there was already a <link> element with a DOI for
    #        this RFC, check that the "href" value has the right format.  The
    #        content of the href attribute is expected to change in the
    #        future.
            doi_href = "https://dx.doi.org/10.17487/rfc%s" % self.rfcnumber
            doilink = e.find('.//link[@href="%s"]' % (doi_href, ))
            if doilink is None:
                e.insert(0, self.element('link', href=doi_href, rel='alternate'))

    # 
    #    4.  If in RFC production mode, check if there is a <link> element
    #        with the file name of the Internet-Draft that became this RFC the
    #        form <link rel="convertedFrom"
    #        href="https://datatracker.ietf.org/doc/draft-tttttttttt/">.  If
    #        one does not exist, give an error.
            converted_from = e.find('.//link[@rel="prev"]')
            if converted_from is None:
                docName = self.root.get("docName")
                if docName:
                    e.insert(0, self.element('link', rel='prev', href="https://datatracker.ietf.org/doc/%s"%(docName, ), line=e.sourceline))
                else:
                    self.warn(e, 'Expected a <link> with rel="prev" providing the datatracker url for the origin draft,'
                                 ' or alternatively a "docName" attribute on <rfc> from which to construct such a <link> element.'
                        )
            else:
                converted_from_href = converted_from.get('href', '')
                if not converted_from_href.startswith("https://datatracker.ietf.org/doc/draft-"):
                    self.err(converted_from, "Expected the <link rel='prev'> href= to have the form 'https://datatracker.ietf.org/doc/draft-...', but found '%s'" % (converted_from_href, ))

    # 5.6.4.  XML Comment Removal
    # 
    #    If in RFC production mode, remove XML comments.
    def comment_removal(self, e, p):
        if self.options.rfc:
            self.remove(p, e)

    # 5.6.5.  "xml:base" and "originalSrc" Removal
    # 
    #    If in RFC production mode, remove all "xml:base" or "originalSrc"
    #    attributes from all elements.
    def attribute_removal(self, e, p):
        if self.options.rfc:
            for c in e.iterfind('.//*[@xml:base]', namespaces=namespaces):
                del c.attrib['{http://www.w3.org/XML/1998/namespace}base']
            for c in e.iterfind('.//*[@originalSrc]'):
                del c.attrib['originalSrc']

    # 5.6.6.  Compliance Check
    # 
    #    If in RFC production mode, ensure that the result is in full
    #    compliance to the v3 schema, without any deprecated elements or
    #    attributes and give an error if any issues are found.

    # implemented in parent class: validate_after(self, e, p):

    # 5.7.  Finalization
    # 
    #    These steps provide the finishing touches on the output document.

    # 5.7.1.  "scripts" Insertion
    # 
    #    Determine all the characters used in the document and fill in the
    #    "scripts" attribute for <rfc>.
    def insert_scripts(self, e, p):
        text = ' '.join(e.itertext())
        scripts = ','.join(sorted(list(get_scripts(text))))
        e.set('scripts', scripts)

    # 5.7.2.  Pretty-Format
    # 
    #    Pretty-format the XML output.  (Note: there are many tools that do an
    #    adequate job.)

    # ------------------------------------------------------------------------

    # Other post-processing

    def remove_pis(self):
        self.keep_pis = []
        for i in self.root.xpath('.//processing-instruction()'):
            self.processing_instruction_removal(i, i.getparent())
