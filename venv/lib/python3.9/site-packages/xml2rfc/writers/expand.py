# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

from io import open
from lxml import etree

from xml2rfc.writers.preptool import PrepToolWriter

class ExpandV3XmlWriter(PrepToolWriter):
    """ Writes a duplicate XML file but with all includes expanded """

    # Note -- we don't need to subclass BaseRfcWriter because the behavior
    # is so different and so trivial

    def write(self, filename):
        """ Public method to write the XML document to a file """
        self.expand()
        with open(filename, 'w', encoding='utf-8') as file:
            # Use lxml's built-in serialization
            text = etree.tostring(self.tree,
                                    encoding='unicode',
                                    doctype='<!DOCTYPE rfc SYSTEM "rfc2629-xhtml.ent">',
                                    pretty_print=True)

            # Use entities for some selected unicode code points, for later
            # editing readability and convenience
            text = text.replace(u'\u00A0', u'&nbsp;')
            text = text.replace(u'\u200B', u'&zwsp;')
            text = text.replace(u'\u2011', u'&nbhy;')
            text = text.replace(u'\u2028', u'&br;')
            text = text.replace(u'\u2060', u'&wj;')

            file.write(u"<?xml version='1.0' encoding='utf-8'?>\n")
            file.write(text)
            if not self.options.quiet:
                self.log(' Created file %s' % filename)

    def expand(self):
        version = self.root.get('version', '3')
        if version not in ['3', ]:
            self.die(self.root, 'Expected <rfc> version="3", but found "%s"' % version)
        self.xinclude()
        self.dispatch(self.selectors)

    selectors = [
        './/artwork',
        './/sourcecode',
        '.;pretty_print_prep()',
    ]

