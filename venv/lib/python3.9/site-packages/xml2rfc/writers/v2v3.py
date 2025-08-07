# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

import os
import re
import lxml.etree
import traceback as tb

from collections import OrderedDict
from io import open
from lxml.etree import Element, Comment, CDATA

import xml2rfc
from xml2rfc import log
from xml2rfc.utils import hastext, isempty, sdict, slugify, iscomment
from xml2rfc.writers.base import default_options, BaseV3Writer


try:
    from xml2rfc import debug
    assert debug
except ImportError:
    pass

def idref(s):
    s = re.sub(r'^[^A-Za-z_]', '_', s)
    s = re.sub(r'[^-._A-Za-z0-9]', '_', s)
    return s

def stripattr(e, attrs):
    for a in attrs:
        if a in e.keys():
            del e.attrib[a]

def copyattr(a, b):
    for k in a.keys():
        v = a.get(k)
        b.set(k, v)

class V2v3XmlWriter(BaseV3Writer):
    """ Writes an XML file with v2 constructs converted to v3"""

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None):
        super(V2v3XmlWriter, self).__init__(xmlrfc, quiet=quiet, options=options, date=date)
        if not quiet is None:
            options.quiet = quiet
        self.xmlrfc = xmlrfc
        self.tree = xmlrfc.tree
        self.root = self.tree.getroot()
        self.options = options

    def validate(self):
        return super(V2v3XmlWriter, self).validate(when='when running v2v3 conversion', warn=True)

    def add_xinclude(self):
        for e in self.root.xpath('.//back//reference'):
            p = e.getparent()
            for si in e.xpath('.//seriesInfo'):
                if si.get('name') == 'RFC':
                    num = si.get('value', '')
                    if num and num.isdigit():
                        xi = self.element('{http://www.w3.org/2001/XInclude}include',
                                    nsmap=self.xmlrfc.nsmap,
                                    line=e.sourceline,
                                    href="https://bib.ietf.org/public/rfc/bibxml/reference.RFC.%04d.xml"%int(num))
                        xi.tail = e.tail
                        i = p.index(e)
                        p.remove(e)
                        p.insert(i, xi)
                    else:
                        self.warn(e, 'Invalid value in %s' % lxml.etree.tostring(e))
                elif si.get('name') == 'Internet-Draft':
                    name = si.get('value', '')
                    if name:
                        tag = name[len('draft-'):] if name.startswith('draft-') else name
                        if re.search(r'-\d\d$', tag) and self.options.draft_revisions:
                            xi = self.element('{http://www.w3.org/2001/XInclude}include',
                                        nsmap=self.xmlrfc.nsmap,
                                        line=e.sourceline,
                                        href="https://bib.ietf.org/public/rfc/bibxml3/reference.I-D.draft-%s.xml"%tag)
                        else:
                            tag = re.sub(r'-\d\d$', '', tag)
                            xi = self.element('{http://www.w3.org/2001/XInclude}include',
                                        nsmap=self.xmlrfc.nsmap,
                                        line=e.sourceline,
                                        href="https://bib.ietf.org/public/rfc/bibxml3/reference.I-D.%s.xml"%tag)
                        xi.tail = e.tail
                        i = p.index(e)
                        p.remove(e)
                        p.insert(i, xi)
                    else:
                        self.warn(e, 'Invalid value in %s' % lxml.etree.tostring(e))
#        lxml.etree.cleanup_namespaces(self.root, top_nsmap=self.xmlrfc.nsmap)
                else:
                    self.note(e, "Not implemented: xi:include handling for %s:%s" % (si.get('name'), si.get('value')))

    def post_process_lines(self, lines):
        output = [ line.replace(u'\u00A0', ' ') for line in lines ]
        return output

    def write(self, filename):
        """ Public method to write the XML document to a file """

        self.convert2to3()
        if self.options.add_xinclude:
            self.add_xinclude()

        # Use an internal DTD to declare entities
        doctype_string = """<!DOCTYPE rfc [
  <!ENTITY nbsp    "&#160;">
  <!ENTITY zwsp   "&#8203;">
  <!ENTITY nbhy   "&#8209;">
  <!ENTITY wj     "&#8288;">
]>"""
        with open(filename, 'w', encoding='utf-8') as file:
            # Use lxml's built-in serialization
            text = lxml.etree.tostring(self.root.getroottree(),
                                       encoding='unicode',
                                       doctype=doctype_string,
                                       pretty_print=True)

            file.write(u"<?xml version='1.0' encoding='utf-8'?>\n")
            file.write(text)

            if not self.options.quiet:
                self.log(' Created file %s' % filename)

    # --- Element Operations -------------------------------------------

    def element(self, tag, line=None, **kwargs):
        e = Element(tag, **sdict(kwargs))
        if line:
            e.sourceline = line
        elif self.options.debug:
            filename, lineno, caller, code = tb.extract_stack()[-2]
            e.base = os.path.basename(filename)
            e.sourceline = lineno
        return e

    def copy(self, e, tag):
        n = self.element(tag, line=e.sourceline)
        n.text = e.text
        n.tail = e.tail
        copyattr(e, n)
        for c in e.iterchildren():
            n.append(c)                 # moves c from e to n
        return n

    def replace(self, a, b, comments=None):
        if isinstance(b, type('')):
            b = self.element(b)
        if comments is None:
            if b is None:
                comments = ['Removed deprecated tag <%s/>' % (a.tag, ) ]
            else:
                comments = ['Replaced <%s/> with <%s/>' % (a.tag, b.tag) ]
        if not isinstance(comments, list):
            comments = [comments]
        p = a.getparent()
        if p != None:
            i = p.index(a)
            c = None
            if self.options.verbose:
                for comment in comments:
                    c = Comment(" v2v3: %s " % comment.strip())
                    c.tail = ''
                    p.insert(i, c)
                    i += 1
            if not b is None:
                if a.text and a.text.strip():
                    b.text = a.text
                if a.tail != None:
                    b.tail = a.tail
                if a.sourceline:
                    b.sourceline = a.sourceline
                copyattr(a, b)
                for child in a.iterchildren():
                    b.append(child)         # moves child from a to b
                p.replace(a, b)
            else:
                if iscomment(a):
                    a.text = ''
                for text in [a.text, a.tail]:
                    if text:
                        if c is None:
                            p.text = p.text + text if p.text else text
                        else:
                            c.tail += text
                p.remove(a)
        if b != None and a.sourceline:
            b.sourceline = a.sourceline
        return b

    def move_after(self, a, b, comments=None):
        if comments is None:
            comments = ["Moved <%s/> to a new position"]
        if not isinstance(comments, list):
            comments = [comments]
        pa = a.getparent()
        pb = b.getparent()
        sa = a.getprevious()
        if a.tail:
            if sa != None:
                if sa.tail:
                    sa.tail += ' ' + a.tail
                else:
                    sa.tail = a.tail
            else:
                if pa.text and pa.text.strip():
                    pa.text += ' ' + a.tail
                else:
                    if a.tail and a.tail.strip():
                        pa.text = a.tail
            a.tail = None
        i = pb.index(b)+1
        pb.insert(i, a)
        if self.options.verbose:
            for comment in comments:
                c = Comment(" v2v3: %s " % comment.strip())
                pb.insert(i, c)

    def promote(self, e, t):
        assert t.tag == 't'
        pp = t.getparent()
        i = pp.index(t)+1
        t2 = self.element('t', line=e.sourceline)
        t2.text = e.tail
        e.tail = None
        for s in e.itersiblings():
            t2.append(s)                # removes s from t
        if not isempty(t2):
            pp.insert(i, t2)
        pp.insert(i, e)                 # removes e from t
        if self.options.verbose:
            pp.insert(i, Comment(" v2v3: <%s/> promoted to be child of <%s/>, and the enclosing <t/> split. " % (e.tag, pp.tag)))
        if isempty(t):
            pp.remove(t)

    def wrap_content(self, e, t=None):
        if t is None:
            t = self.element('t', line=e.sourceline)
        t.text = e.text
        if e.sourceline:
            t.sourceline = e.sourceline
        e.text = None
        for c in e.iterchildren():
            t.append(c)
        e.append(t)
        return t

    # ------------------------------------------------------------------

    def convert2to3(self):
        if self.root.get('version') in ['3', ]:
            return self.tree
        log.note(' Converting v2 to v3: %s' % self.xmlrfc.source)

        selectors = [
            # we need to process list before block elements that might get
            # promoted out of their surrounding <t/>, as <list/> uses one <t/>
            # per list item, and if we promote block elements earlier, they
            # will not be picked up as part of the list items
            './/list',                      # 3.4.  <list>
            #
            './/artwork',                   # 2.5.  <artwork>
                                            # 2.5.4.  "height" Attribute
                                            # 2.5.8.  "width" Attribute
                                            # 2.5.9.  "xml:space" Attribute
            './/back',
            './/code',
            './/date',
            # We need to process preamble and postamble before figure,
            # because artwork or sourcecode within a figure could later be
            # promoted and the figure discarded.
            './/postamble',                 # 3.5.  <postamble>
            './/preamble',                  # 3.6.  <preamble>
            './/figure',                    # 2.25.  <figure>
                                            # 2.25.1.  "align" Attribute
                                            # 2.25.2.  "alt" Attribute
                                            # 2.25.4.  "height" Attribute
                                            # 2.25.5.  "src" Attribute
                                            # 2.25.6.  "suppress-title" Attribute
                                            # 2.25.8.  "width" Attribute
            './/relref',                    # Deprecated after 7991
            './/reference',                 #        <reference>
            '.',                            # 2.45.  <rfc>
                                            # 2.45.1.  "category" Attribute
                                            # 2.45.2.  "consensus" Attribute
                                            # 2.45.3.  "docName" Attribute
                                            # 2.45.7.  "number" Attribute
                                            # 2.45.10.  "seriesNo" Attribute
            #Disabled 
            #'.//seriesInfo',                # 2.47.  <seriesInfo>
            './/t',                         # 2.53.  <t>
                                            # 2.53.2.  "hangText" Attribute
            './/xref',                      # 2.66.  <xref>
                                            # 2.66.1.  "format" Attribute
                                            # 2.66.2.  "pageno" Attribute
            './/facsimile',                 # 3.2.  <facsimile>
            './/format',                    # 3.3.  <format>
            './/spanx',                     # 3.7.  <spanx>
            './/texttable',                 # 3.8.  <texttable>
            './/vspace',                    # 3.10.  <vspace>
            # attribute selectors
            './/*[@title]',
                                            # 2.25.7.  "title" Attribute
                                            # 2.33.2.  "title" Attribute
                                            # 2.42.2.  "title" Attribute
                                            # 2.46.4.  "title" Attribute
            './/*[@anchor]',
            './/xref[@target]',
            '//processing-instruction()',  # 1.3.2
            # handle mixed block/non-block content surrounding all block nodes
            './/*[self::artwork or self::dl or self::figure or self::ol or self::sourcecode or self::t or self::ul]',
            '//*[@*="yes" or @*="no"]',      # convert old attribute false/true
            '.;pretty_print_prep()',
        ]

        # Remove any DOCTYPE declaration
        self.tree.docinfo.clear()

        for s in selectors:
            slug = slugify(s.replace('self::', '').replace(' or ','_').replace(';','_'))
            if '@' in s:
                func_name = 'attribute_%s' % slug
            elif "()" in s:
                func_name = slug
            else:
                if not slug:
                    slug = 'rfc'
                func_name = 'element_%s' % slug
            # get rid of selector annotation
            ss = s.split(';')[0]
            func = getattr(self, func_name, None)
            if func:
                if self.options.debug:
                    log.note("Calling %s()" % func_name)
                for e in self.root.xpath(ss):
                    func(e, e.getparent())
            else:
                log.warn("No handler for function %s, slug %s" % (func_name, slug, ))

        self.root.set('version', '3')

        # Add a comment about the converter version
        conversion_version = Comment(' xml2rfc v2v3 conversion %s ' % xml2rfc.__version__)
        conversion_version.tail = '\n  '
        self.root.insert(0, conversion_version)

        # This is a workaround for not being able to do anything about
        # namespaces other than when creating an element.  It lets us retain
        # a namespace declaration for xi: in the root element.
#         dummy = self.element('{http://www.w3.org/2001/XInclude}include', nsmap=self.xmlrfc.nsmap)
#         self.root.insert(0, dummy)
#         lxml.etree.cleanup_namespaces(self.root, top_nsmap=self.xmlrfc.nsmap, keep_ns_prefixes='xi')
#         self.root.remove(dummy)
        log.note(' Completed v2 to v3 conversion')
        return self.tree

    # ----------------------------------------------------------------------

    # 1.3.2.  New Attributes for Existing Elements
    # 
    #    o  Add "sortRefs", "symRefs", "tocDepth", and "tocInclude" attributes
    #       to <rfc> to cover Processing Instructions (PIs) that were in v2
    #       that are still needed in the grammar.  ...
    def processing_instruction(self, e, p):
        if e.target != 'rfc':
            return
        rfc_element = self.root.find('.')
        pi_name = {
            'sortrefs': 'sortRefs',
            'symrefs':  'symRefs',
            'tocdepth': 'tocDepth',
            'toc':      'tocInclude',
        }
        for k, a in pi_name.items():
            if k in e.attrib:
                v = e.get(k)
                if v == 'yes':
                    v = 'true'
                elif v == 'no':
                    v = 'false'
                rfc_element.set(a, v)
                self.replace(e, None, 'Moved %s PI to <rfc %s="%s"' % (k, a, v))
                break
        else:
            self.replace(e, None, 'Removed %s PI"' % (k,))

    # 1.3.4.  Additional Changes from v2
    # 
    #    o  Make <seriesInfo> a child of <front>, and deprecated it as a child
    #       of <reference>.  This also deprecates some of the attributes from
    #       <rfc> and moves them into <seriesInfo>.
    def element_seriesinfo(self, e, p):
        if   p.tag == 'front':
            pass
        elif p.tag == 'reference':
            title = p.find('./front/title')
            if title != None:
                self.move_after(e, title, "Moved <seriesInfo/> inside <front/> element")

    # 1.3.4.  Additional Changes from v2
    #
    #    o  <t> now only contains non-block elements, so it no longer contains
    #       <figure> elements.
    def element_artwork_dl_figure_ol_sourcecode_t_ul(self, e, p):
        # check if we have any text or non-block-elements next to the
        # element.  If so, embed in <t/> and then promote the element.
        nixmix_tags = [ 'blockquote', 'li', 'dd', 'td', 'th']
        text_items = hastext(p)
        if p.tag in nixmix_tags and text_items:
            if self.options.verbose:
                self.warn(e, "Found mixed content in <%s>: Both <%s> and inline content: '%s'" % (p.tag, e.tag, (' '.join(str(t) for t in text_items))[:40].strip().replace('\n',' ')))
            self.wrap_content(p)
        p = e.getparent()
        #pp = p.getparent()
        if p.tag == 't':
            #debug.say('Promote %s (parent %s, grandparent %s) ...'%(e.tag, p.tag, pp.tag))
            self.promote(e, p)

    # 2.5.  <artwork>
    # 
    # 2.5.4.  "height" Attribute
    # 
    #    Deprecated.
    # 
    # 2.5.8.  "width" Attribute
    # 
    #    Deprecated.
    # 
    # 2.5.9.  "xml:space" Attribute
    # 
    #    Deprecated.
    def element_artwork(self, e, p):
        if e.text and e.text.strip() and not ']]>' in e.text:
            e.text = CDATA(e.text)          # prevent text from being mucked up by other processors
        stripattr(e, ['height', '{http://www.w3.org/XML/1998/namespace}space', 'width', ])
        if e.text and re.search(r'^\s*<CODE BEGINS>', e.text):
            # We have source code.  Permitted attributes: anchor, name,
            # source, type.
            e = self.replace(e, 'sourcecode')
            e.set('markers', 'true')
            match = re.search(r'(?s)^\s*<CODE BEGINS>(\s+file\s+"([^"]*)")?(.*?)(<CODE ENDS>(.*))?$', e.text)
            file = match.group(1)
            name = match.group(2)
            body = match.group(3)
            ends = match.group(4)
            tail = match.group(5)
            if file and name:
                e.set('name', name)
            e.text = CDATA(body)
            if not ends:
                self.warn(e, "Found <CODE BEGINS> without matching <CODE ENDS>")
            if ends and tail.strip() != "":
                self.warn(e, "Found non-whitespace content after <CODE ENDS>")
                e.tail = tail
            stripattr(e, ['align', 'alt', 'height', 'suppress-title', 'width', ])
        src = e.get('src')
        if e.text and e.text.strip() and src:
            # We have both text content and a src attribute -- convert to
            # <artset> with 2 <artwork)
            ext = os.path.splitext(src)[1][1:]
            artset = self.element('artset', line=e.sourceline)
            extart = self.copy(e, 'artwork')
            extart.text = None
            extart.tail = None
            extart.set('type', ext)
            artset.append(extart)
            stripattr(e, ['src'])
            e.set('type', 'ascii-art')
            artset.append(e)
            p.append(artset)


    def element_back(self, e, p):
        # XXXX The RFCs don't say anything about the text rendering of
        # references.  The following transforms multiple <references> in
        # <back> to be encapsulated within one <references>.
        references = list(e.iterchildren('references'))
        if len(references) > 1:
            pos = e.index(references[0])
            refs = self.element('references', line=references[0].sourceline)
            name = self.element('name', line=references[0].sourceline)
            name.text = "References"
            refs.append(name)
            e.insert(pos, refs)
            for r in references:
                refs.append(r)          # moves r


    def element_code(self, e, p):
        if e.text and re.search(r'^[A-Z][A-Z]?-', e.text):
            cc, num = e.text.split('-', 1)
            if cc in ['AX', 'CH', 'FI', 'HR', 'FL', 'LT', 'L', 'MC', 'MD', 'SE', 'SI', ]:
                e.text = num

    def element_date(self, e, p):
        year = e.get('year')
        if year and not year.isdigit():
            del e.attrib['year']
            e.text = year

    # 2.25.  <figure>
    # 
    # 2.25.1.  "align" Attribute
    # 
    #    Deprecated.
    # 
    # 2.25.2.  "alt" Attribute
    # 
    #    Deprecated.  If the goal is to provide a single URI for a reference,
    #    use the "target" attribute in <reference> instead.
    # 
    # 2.25.4.  "height" Attribute
    # 
    #    Deprecated.
    # 
    # 2.25.5.  "src" Attribute
    # 
    #    Deprecated.
    # 
    # 2.25.6.  "suppress-title" Attribute
    # 
    #    Deprecated.
    # 
    #    Allowed values:
    # 
    #    o  "true"
    # 
    #    o  "false" (default)
    # 
    # 2.25.7.  "title" Attribute
    # 
    #    Deprecated.  Use <name> instead.
    # 
    # 2.25.8.  "width" Attribute
    # 
    #    Deprecated.
    # 
    def element_figure(self, e, p):
        comments = []
        embedded = e.find('.//artwork')
        if embedded == None:
            embedded = e.find('./sourcecode')
        if embedded != None:
            for attr in ['align', 'alt', 'src', ]:
                if attr in e.attrib:
                    fattr = e.get(attr)
                    if attr in embedded.attrib:
                        aattr = embedded.get(attr)
                        if fattr != aattr:
                            comments.append('Warning: The "%s" attribute on artwork differs from the one on figure.  Using only "%s" on artwork.' % (attr, attr))
                    else:
                        if embedded.tag == 'artwork' or attr == 'src':
                            embedded.set(attr, fattr)
                    stripattr(e, [ attr ])
            # if we have <artwork> and either no anchor and no title, or suppress-title='true',
            # then promote the <artwork> and get rid of the <figure>
        if embedded != None and ((not e.get('anchor') and (not e.get('title')) or e.get('suppress-title') == 'true')
            and e.find('name')==None and e.find('preamble')==None and e.find('postamble')==None ):
            pos = p.index(e)
            embedded.tail = e.tail
            children = e.getchildren()
            p.remove(e)
            for c in children:
                p.insert(pos, c)
                pos += 1
        else:
            stripattr(e, ['align', 'height', 'src', 'suppress-title', 'width', ])
            if self.options.strict:
                stripattr(e, ['alt', ])



    # 2.25.7.  "title" Attribute
    # 
    #    Deprecated.  Use <name> instead.
    # 
    # 2.33.2.  "title" Attribute
    # 
    #    Deprecated.  Use <name> instead.
    # 
    # 2.42.2.  "title" Attribute
    # 
    #    Deprecated.  Use <name> instead.
    # 
    # 2.46.4.  "title" Attribute
    # 
    #    Deprecated.  Use <name> instead.
    # 
    # 3.8.5.  "title" Attribute
    # 
    #    Deprecated.
    def attribute_title(self, e, p):
        n = self.element('name', line=e.sourceline)
        n.text = e.get('title').strip()
        if n.text:
            e.insert(0, n)
            if self.options.verbose:
                c = Comment(" v2v3: Moved attribute title to <name/> ")
                e.insert(0, c)
        stripattr(e, ['title', ])

    def element_reference(self, e, p):
        if 'quote-title' in e.attrib:
            v = 'true' if e.get('quote-title') in ['true', 'yes'] else 'false'
            if v != 'true':             # no need to set default value
                e.set('quoteTitle', v)
        stripattr(e, ['quote-title'])

    def element_relref(self, e, p):
        if 'displayFormat' in e.attrib:
            e.attrib['sectionFormat'] = e.attrib['displayFormat']
            del e.attrib['displayFormat']
        e.tag = 'xref'

    # 2.45.  <rfc>
    # 
    # 2.45.1.  "category" Attribute
    # 
    #    Deprecated; instead, use the "name" attribute in <seriesInfo>.
    # 
    # 2.45.2.  "consensus" Attribute
    # 
    #    Affects the generated boilerplate.  Note that the values of "no" and
    #    "yes" are deprecated and are replaced by "false" (the default) and
    #    "true".
    # 
    # 2.45.3.  "docName" Attribute
    # 
    #    Deprecated; instead, use the "value" attribute in <seriesInfo>.
    # 
    # 2.45.7.  "number" Attribute
    # 
    #    Deprecated; instead, use the "value" attribute in <seriesInfo>.
    # 
    # 2.45.10.  "seriesNo" Attribute
    # 
    #    Deprecated; instead, use the "value" attribute in <seriesInfo>.
    def element_rfc(self, e, p):
#         category_strings = {
#             "std": "Standards Track",
#             "bcp": "Best Current Practice",
#             "exp": "Experimental",
#             "historic": "Historic",
#             "info": "Informational",
#         }
        def equal(e1, e2):
            return (e1.get('name'), e1.get('value')) ==  (e2.get('name'), e2.get('value'))
        if e.get('ipr') == 'none':
            return
        front = e.find('./front')
        title = e.find('./front/title')
        i = front.index(title) + 1 if title!=None else 0
        series = front.xpath('seriesInfo') if front!=None else []
        if 'category' in e.attrib and 'seriesNo' in e.attrib:
            attr = {
                'name': e.get('category'),
                'value': e.get('seriesNo')
            }
            new = self.element('seriesInfo', line=e.sourceline, **attr)
            if not [ s for s in series if equal(s, new) ]:
                front.insert(i, new)
            stripattr(e, ['seriesNo', ]) # keep 'category' for use in preptool
        if 'number' in e.attrib:
            new = self.element('seriesInfo', name="RFC", value=e.get('number'), line=e.sourceline)
            if not [ s for s in series if equal(s, new) ]:
                front.insert(i, new)
            if 'docName' in e.attrib:
                e.insert(0, self.element('link', rel='prev', href="https://datatracker.ietf.org/doc/%s"%(e.get('docName'), ), line=e.sourceline))
        elif 'docName' in e.attrib:
            value=e.get('docName')
            new = self.element('seriesInfo', name="Internet-Draft", value=value, line=e.sourceline)
            if not 'Internet-Draft' in [ s.get('name') for s in series ]:
                front.insert(i, new)

        stripattr(e, ['xi', ])

    # 2.47.  <seriesInfo>
    # 
    #    ...
    #    
    #    This element appears as a child element of <front> (Section 2.26) and
    #    <reference> (Section 2.40; deprecated in this context).
    # 
    # 
    # 2.53.  <t>
    # 
    # 2.53.2.  "hangText" Attribute
    # 
    #    Deprecated.  Instead, use <dd> inside of a definition list (<dl>).
    def element_t(self, e, p):
        if p.tag != 'list':
            stripattr(e, ['hangText', ])

    # 
    # 
    # 2.66.  <xref>
    # 
    # 2.66.1.  "format" Attribute
    # 
    #    "none"
    # 
    #       Deprecated.
    # 
    # 1.3.3.  Elements and Attributes Deprecated from v2
    # 
    #    o  Deprecate the "pageno" attribute in <xref> because it was unused
    #       in v2.  Deprecate the "none" values for the "format" attribute in
    #       <xref> because it makes no sense semantically.
    #
    def element_xref(self, e, p):
        stripattr(e, ['pageno'])

    # 2.66.2.  "pageno" Attribute
    # 
    #    Deprecated.
    # 
    # 
    # 3.  Elements from v2 That Have Been Deprecated
    # 
    #    This section lists the elements from v2 that have been deprecated.
    #    Note that some elements in v3 have attributes from v2 that are
    #    deprecated; those are not listed here.
    # 
    # 
    # 3.1.  <c>
    # 
    #    Deprecated.  Instead, use <tr>, <td>, and <th>.
    # 
    #    This element appears as a child element of <texttable> (Section 3.8).
    # 
    # 
    # 3.2.  <facsimile>
    # 
    #    Deprecated.  The <email> element is a much more useful way to get in
    #    touch with authors.
    # 
    #    This element appears as a child element of <address> (Section 2.2).
    def element_facsimile(self, e, p):
            e.text = ''
            self.replace(e, None)

    # 3.3.  <format>
    # 
    #    Deprecated.  If the goal is to provide a single URI for a reference,
    #    use the "target" attribute in <reference> instead.
    # 
    #    This element appears as a child element of <reference>
    #    (Section 2.40).
    def element_format(self, e, p):
        ptarget = p.get('target')
        ftarget = e.get('target')
        if ptarget:
            if ftarget == ptarget:
                self.replace(e, None, "<format/> element with duplicate target (%s) removed" % ftarget)
            # The following, while implementing RFC 7991, seems dubious, and
            # has been commented out.  Why would you disallow pointing to
            # multiple versions of a reference?
            #else:
            #    self.replace(e, None, "Warning: <format/> element with alternative target (%s) removed" % ftarget)
        else:
            p.set('target', ftarget)
            self.replace(e, None, "<format/> element removed, target value (%s) moved to parent" % ftarget)

    # 3.3.1.  "octets" Attribute
    # 
    #    Deprecated.
    # 
    # 3.3.2.  "target" Attribute
    # 
    #    Deprecated.
    # 
    # 3.3.3.  "type" Attribute (Mandatory)
    # 
    #    Deprecated.
    # 
    # 
    # 3.4.  <list>
    # 
    #    Deprecated.  Instead, use <dl> for list/@style "hanging"; <ul> for
    #    list/@style "empty" or "symbols"; and <ol> for list/@style "letters",
    #    "numbers", "counter", or "format".
    # 
    #    This element appears as a child element of <t> (Section 2.53).
    def element_list(self, e, p):
        # convert to dl, ul, or ol
        nstyle = None
        style = e.get('style', '').strip()
        attribs = OrderedDict()
        comments = []
        if not style:
            # otherwise look for the nearest list parent with a style and use it
            for parent in e.iterancestors():
                if parent.tag == 'list':
                    style = parent.get('style')
                elif parent.tag == 'dl':
                    style = 'hanging'
                elif parent.tag == 'ul':
                    style = 'symbols'
                elif parent.tag == 'ol':
                    style = 'inherit'
                    nstyle = parent.get('type')
                    # alternate letter case in sub-lists:
                    if   nstyle in 'ai':
                        nstyle = nstyle.upper()
                    elif nstyle in 'AI':
                        nstyle = nstyle.lower()                        
                if style:
                    break
        if not style:
            style = 'empty'
        #
        if   style == 'empty':
            tag = 'ul'
            attribs['empty'] = 'true'
        elif style == 'symbols':
            tag = 'ul'
        elif style == 'hanging':
            tag = 'dl'
            attribs["newline"] = "false"
        elif style in ['numbers', 'inherit']:
            tag = 'ol'
            attribs['type'] = nstyle if nstyle else '1'
        elif style == 'letters':
            tag = 'ol'
            attribs['type'] = nstyle if nstyle else 'a'
        elif style.startswith('format'):
            tag = 'ol'
            attribs['type'] = style[len('format '):]
        else:
            tag = 'ul'
            comments.append("Warning: unknown list style: '%s'" % style)
        #
        comments.append('Replaced <list style="%s"/> with <%s/>' % (style, tag))
        if tag=='ol' and 'counter' in e.keys():
            attribs['group'] = e.get('counter')
            comments.append("Converting <list counter=...> to <%s group=...> " % tag)
        #
        attribs['spacing'] = 'compact' if hasattr(e, 'pis') and e.pis['subcompact'] in ['yes', 'true'] else 'normal'
        #
        stripattr(e, ['counter', 'style', ])
        l = self.element(tag, **attribs)
        self.replace(e, l, comments)
        indent = l.get('hangIndent')
        stripattr(l, ['hangIndent'])
        if tag in ['ol', 'ul']:
            for t in l.findall('./t'):
                new = self.element('t', line=t.sourceline)
                self.wrap_content(t, new)
                self.replace(t, 'li')
        elif tag == 'dl':
            if indent:
                l.set('indent', indent)
            for t in l.findall('./t'):
                dt = self.element('dt', line=t.sourceline)
                dt.text = t.get('hangText')
                if not dt.text is None:
                    del t.attrib['hangText']
                # Convert <vspace> at the start of hanging list text to
                # attribute hanging='true' on <dl>
                if not t.text or not t.text.strip():
                    if len(t) and t[0].tag == 'vspace':
                        t.text = t[0].tail
                        t.remove(t[0])
                        l.set('newline', 'true')
                i = l.index(t)
                l.insert(i, dt)
                self.replace(t, 'dd')
        else:
            self.warn(e, "Unexpected tag when processing <list/>: '%s'" % tag)

    # 3.4.1.  "counter" Attribute
    # 
    #    Deprecated.  The functionality of this attribute has been replaced
    #    with <ol>/@start.
    # 
    # 3.4.2.  "hangIndent" Attribute
    # 
    #    Deprecated.  Use <dl> instead.
    # 
    # 3.4.3.  "style" Attribute
    # 
    #    Deprecated.
    # 
    # 
    # 3.5.  <postamble>
    # 
    #    Deprecated.  Instead, use a regular paragraph after the figure or
    #    table.
    # 
    #    This element appears as a child element of <figure> (Section 2.25)
    #    and <texttable> (Section 3.8).
    def element_postamble(self, e, p):
        e = self.replace(e, 't')
        e.set('keepWithPrevious', 'true')
        self.move_after(e, p)

    # 3.6.  <preamble>
    # 
    #    Deprecated.  Instead, use a regular paragraph before the figure or
    #    table.
    # 
    #    This element appears as a child element of <figure> (Section 2.25)
    #    and <texttable> (Section 3.8).
    def element_preamble(self, e, p):
        e = self.replace(e, 't')
        e.set('keepWithNext', 'true')
        s = p.getprevious()
        if not s is None:
            self.move_after(e, s)
        else:
            pp = p.getparent()
            i = pp.index(p)
            pp.insert(i, e)             # this relies on there being no surrounding text

    # 1.3.3.  Elements and Attributes Deprecated from v2
    #
    #    o  Deprecate <spanx>; replace it with <strong>, <em>, and <tt>.
    #
    # 3.7.  <spanx>
    # 
    #    Deprecated.
    # 
    #    This element appears as a child element of <annotation>
    #    (Section 2.3), <c> (Section 3.1), <postamble> (Section 3.5),
    #    <preamble> (Section 3.6), and <t> (Section 2.53).
    # 
    # 3.7.1.  "style" Attribute
    # 
    #    Deprecated.  Instead of <spanx style="emph">, use <em>; instead of
    #    <spanx style="strong">, use <strong>; instead of <spanx
    #    style="verb">, use <tt>.
    # 
    # 3.7.2.  "xml:space" Attribute
    # 
    #    Deprecated.
    # 
    #    Allowed values:
    # 
    #    o  "default"
    # 
    #    o  "preserve" (default)
    # 
    def element_spanx(self, e, p):
        style = e.get('style', 'emph')
        tags = {
            'emph':     'em',
            'strong':   'strong',
            'verb':     'tt',
        }
        if style in tags:
            tag = tags[style]
        else:
            self.warn(e, "Unexpected style in <spanx/>: '%s'" % style)
            tag = 'em'
        stripattr(e, ['style', '{http://www.w3.org/XML/1998/namespace}space', ])
        self.replace(e, tag, 'Replaced <spanx style="%s"/> with <%s/>' % (style, tag))

    # 1.3.3.  Elements and Attributes Deprecated from v2
    # 
    #    o  Deprecate <texttable>, <ttcol>, and <c>; replace them with the new
    #       table elements (<table> and the elements that can be contained
    #       within it).
    # 
    # 3.8.  <texttable>
    # 
    #    Deprecated.  Use <table> instead.
    # 
    #    This element appears as a child element of <aside> (Section 2.6) and
    #    <section> (Section 2.46).
    #
    # 3.8.1.  "align" Attribute
    # 
    #    Deprecated.
    # 
    # 3.8.2.  "anchor" Attribute
    # 
    #    Deprecated.
    # 
    # 3.8.3.  "style" Attribute
    # 
    #    Deprecated.
    # 
    # 3.8.4.  "suppress-title" Attribute
    # 
    #    Deprecated.
    def element_texttable(self, e, p):
        # The tree has been verified to follow the schema on parsing, so we
        # assume that elements occur in the right order here:
        colcount = 0
        cellcount = 0
        thead = None
        tbody = None
        tr = None
        align = []
        table = self.element('table', line=e.sourceline)
        copyattr(e, table)
        for x in e.iterchildren():
            if   x.tag == 'preamble':
                # will be handled separately
                pass
            elif x.tag == 'ttcol':
                if colcount == 0:
                    thead = self.element('thead', line=x.sourceline)
                    table.append(thead)
                    tr = self.element('tr', line=x.sourceline)
                    thead.append(tr)
                align.append(x.get('align', None))
                th = self.copy(x, 'th')
                stripattr(th, ['width'])
                tr.append(th)
                colcount += 1
            elif x.tag == 'c':
                col = cellcount % colcount
                if cellcount == 0:
                    tbody = self.element('tbody', line=x.sourceline)
                    table.append(tbody)
                if col == 0:
                    tr = self.element('tr', line=x.sourceline)
                    tbody.append(tr)
                td = self.copy(x, 'td')
                if align[col]:
                    td.set('align', align[col])
                tr.append(td)
                stripattr(td, ['width'])
                cellcount += 1
            elif x.tag == 'postamble':
                # will be handled separately
                pass
        stripattr(table, ['style', 'suppress-title',])
        #stripattr(table, ['style', 'suppress-title',])
        p.replace(e, table)


    # 
    # 
    # 
    # 3.9.  <ttcol>
    # 
    #    Deprecated.  Instead, use <tr>, <td>, and <th>.
    # 
    #    This element appears as a child element of <texttable> (Section 3.8).
    # 
    # 3.9.1.  "align" Attribute
    # 
    #    Deprecated.
    # 
    #    Allowed values:
    # 
    #    o  "left" (default)
    # 
    #    o  "center"
    # 
    #    o  "right"
    # 
    # 3.9.2.  "width" Attribute
    # 
    #    Deprecated.
    def element_ttcol(self, e, p):
        # handled in element_texttable()
        pass


    # 3.10.  <vspace>
    # 
    #    Deprecated.  In earlier versions of this format, <vspace> was often
    #    used to get an extra blank line in a list element; in the v3
    #    vocabulary, that can be done instead by using multiple <t> elements
    #    inside the <li> element.  Other uses have no direct replacement.
    # 
    #    This element appears as a child element of <t> (Section 2.53).
    # 
    #    Content model: this element does not have any contents.
    def element_vspace(self, e, p):
        t = p
        if t.tag != 't':
            #bare text inside other element -- wrap in t first
            t = self.wrap_content(t)
        l = t.getparent()
        if l.tag in ['dd', 'li', ]:
            i = l.index(t) + 1
            t2 = self.element('t', line=e.sourceline)
            if e.tail and e.tail.strip():
                t2.text = e.tail
            for s in e.itersiblings():
                t2.append(s)
            t.remove(e)
            l.insert(i, t2)
            if self.options.verbose:
                c = Comment(" v2v3: <vspace/> inside list converted to sequence of <t/> ")
                t.insert(i, c)
            if isempty(t):
                l.remove(t)
        else:
            self.replace(e, None, "<vspace/> deprecated and removed")
            self.warn(e, "Deprecated <vspace/> element removed, but no good conversion found  The output will most likely need fixup.")

    # 3.10.1.  "blankLines" Attribute
    # 
    #    Deprecated.
    # 
    # 
    # A.3.  The "consensus" Attribute
    # 
    #    The consensus attribute can be used to supply this information.  The
    #    acceptable values are "true" (the default) and "false"; "yes" and
    #    "no" from v2 are deprecated.
    # 

    # v3 is stricter than v2 on where only IDREF is permitted.  Fix this
    def attribute_anchor(self, e, p):
        k = 'anchor'
        if k in e.keys():
            v = e.get(k)
            id = idref(v.strip())
            if id != v:
                e.set(k, id)
                

    def attribute_xref_target(self, e, p):
        k = 'target'
        if k in e.keys():
            v = e.get(k)
            id = idref(v.strip())
            if id != v:
                e.set(k, id)

    def attribute_yes_no(self, e, p):
        for k,v in e.attrib.items():
            if   v == 'yes':
                e.set(k, 'true')
            elif v == 'no':
                e.set(k, 'false')

#     def pretty_print_prep(self, e, p):
#         # apply this to elements that can't appear with text, i.e., don't have
#         # any of these as parent:
#         skip_parents = set([
#             "annotation", "blockquote", "preamble", "postamble", "name", "refcontent", "c", "t",
#             "cref", "dd", "dt", "li", "td", "th", "tt", "em", "strong", "sub", "sup", ])
#         for c in e.iter():
#             p = c.getparent()
#             if p != None and p.tag in skip_parents:
#                 continue
#             if c.tail != None:
#                 if c.tail.strip() == '':
#                     c.tail = None
