# --------------------------------------------------
# Copyright The IETF Trust 2011, All Rights Reserved
# --------------------------------------------------

import lxml.etree
import xml2rfc
from io import open
from xml2rfc.writers.base import default_options

class ExpandedXmlWriter:
    """ Writes a duplicate XML file but with all references expanded """

    # Note -- we don't need to subclass BaseRfcWriter because the behavior
    # is so different and so trivial

    def __init__(self, xmlrfc, quiet=None, options=default_options, date=None):
        if not quiet is None:
            options.quiet = quiet
        self.root = xmlrfc.getroot()
        self.options = options

    def post_process_lines(self, lines):
        output = [ line.replace(u'\u00A0', ' ') for line in lines ]
        return output

    def write(self, filename):
        """ Public method to write the XML document to a file """

        with open(filename, 'w', encoding='ascii') as file:
            # Use lxml's built-in serialization
            text = lxml.etree.tostring(self.root.getroottree(),
                                           xml_declaration=True,
                                           encoding='ascii',
                                           doctype='<!DOCTYPE rfc SYSTEM "rfc2629.dtd">',
                                           pretty_print=True)
            file.write(text.decode('ascii'))

            if not self.options.quiet:
                xml2rfc.log.write(' Created file', filename)
