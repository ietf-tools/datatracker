# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import copy
import datetime

from codecs import open

try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass

from lxml import etree


from xml2rfc import log
from xml2rfc.utils import namespaces, sdict
from xml2rfc.writers.base import default_options, BaseV3Writer, RfcWriterError


class UnPrepWriter(BaseV3Writer):
    """ Writes an XML file where many of the preptool additions have been removed"""

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None, liberal=None, keep_pis=['v3xml2rfc']):
        super(UnPrepWriter, self).__init__(xmlrfc, quiet=quiet, options=options, date=date)
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

    def validate(self, when, warn=False):
        return super(UnPrepWriter, self).validate(when='%s running unprep'%when, warn=warn)

    def write(self, filename):
        """ Public method to write the XML document to a file """

        if not self.options.quiet:
            self.log(' Unprepping %s' % self.xmlrfc.source)
        self.unprep()
        if self.errors:
            raise RfcWriterError("Not creating output file due to errors (see above)")

        with open(filename, 'w', encoding='utf-8') as file:
            # Use lxml's built-in serialization
            text = etree.tostring(self.root.getroottree(),
                                            xml_declaration=True,
                                            encoding='utf-8',
                                            pretty_print=True)
            file.write(text.decode('utf-8'))

            if not self.options.quiet:
                self.log(' Created file %s' % filename)

    def unprep(self):

        ## Selector notation: Some selectors below have a handler annotation,
        ## with the selector and the annotation separated by a semicolon (;).
        ## Everything from the semicolon to the end of the string is stripped
        ## before the selector is used.
        tree = self.dispatch(self.selectors)
        log.note(" Completed unprep run")
        return tree

    selectors = [
#        '.;validate_before()',
        '/rfc[@prepTime]',
        './/ol[@group]',
        './front/boilerplate',
        './front/toc',
        './/name[@slugifiedName]',
        './/*;remove_attribute_defaults()',
        './/*[@pn]',
        './/xref',
        './back/section/t[@anchor="rfc.index.index"]/..',  # remove entire index section
        './back/section[@anchor="authors-addresses"]',
        './/section[@toc]',
        './/*[@removeInRFC="true"]',
#            '.;validate_after()',
        '.;pretty_print_prep()',
    ]

    def attribute_rfc_preptime(self, e, p):
        del e.attrib['prepTime']

    def attribute_ol_group(self, e, p):
        group = e.get('group')
        start = e.get('start')
        if not group in self.ol_counts:
            self.ol_counts[group] = 1
        if start and int(start) == int(self.ol_counts[group]):
            del e.attrib['start']
        self.ol_counts[group] += len(list(e.iterchildren('li')))

    def attribute_removeinrfc_true(self, e, p):
        warning_text = "This %s is to be removed before publishing as an RFC." % e.tag
        top_para = e.find('t')
        if top_para!=None and top_para.text != warning_text:
            e.remove(top_para)

    def remove_element(self, e, p):
        self.remove(p, e)

    element_front_boilerplate = remove_element
    element_front_toc = remove_element
    attribute_back_section_anchor_authors_addresses = remove_element
    attribute_back_section_t_anchor_rfcindexindex = remove_element

    def attribute_name_slugifiedname(self, e, p):
        del e.attrib['slugifiedName']

    def remove_attribute_defaults(self, e, p):
        g = p.getparent() if p != None else None
        ptag = p.tag if p != None else None
        gtag = g.tag if g != None else None
        if not (gtag in ['reference', ] or ptag in ['reference', ]):
            defaults = self.get_attribute_defaults(e.tag)
            for k in defaults:
                if k in e.attrib:
                    if (e.tag, k) in [('rfc', 'consensus')]:
                        continue
                    #debug.say('L%-5s: Setting <%s %s="%s">' % (e.sourceline, e.tag, k, defaults[k]))
                    if ':' in k:
                        ns, tag = k.split(':',1)
                        q = etree.QName(namespaces[ns], tag)
                        if e.get(q) == defaults[k]:
                            del e.attrib[q]
                    else:
                        if e.get(k) == defaults[k]:
                            del e.attrib[k]

    def attribute_pn(self, e, p):
        del e.attrib['pn']

    def attribute_section_toc(self, e, p):
        del e.attrib['toc']

    def element_xref(self, e, p):
        if e.get('derivedContent'):
            del e.attrib['derivedContent']
        if e.get('derivedLink'):
            del e.attrib['derivedLink']

