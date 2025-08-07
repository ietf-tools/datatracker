# Copyright The IETF Trust 2024, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

from io import open
from lxml import etree
from urllib.parse import urlparse

from xml2rfc.writers.preptool import PrepToolWriter


class DatatrackerToBibConverter(PrepToolWriter):
    """Writes a duplicate XML file but with datratracker references replaced with bib.ietf.org"""

    def write(self, filename):
        """Public method to write the XML document to a file"""
        self.convert()
        with open(filename, "w", encoding="utf-8") as file:
            text = etree.tostring(self.tree, encoding="unicode")
            file.write("<?xml version='1.0' encoding='utf-8'?>\n")
            file.write(text)
            if not self.options.quiet:
                self.log(" Created file %s" % filename)

    def convert(self):
        version = self.root.get("version", "3")
        if version not in [
            "3",
        ]:
            self.die(self.root, 'Expected <rfc> version="3", but found "%s"' % version)
        self.convert_xincludes()

    def convert_xincludes(self):
        ns = {"xi": b"http://www.w3.org/2001/XInclude"}
        xincludes = self.root.xpath("//xi:include", namespaces=ns)
        for xinclude in xincludes:
            href = urlparse(xinclude.get("href"))

            if href.netloc == "datatracker.ietf.org":
                reference_file = href.path.split("/")[-1]
                xinclude.set(
                    "href", f"https://bib.ietf.org/public/rfc/bibxml-ids/{reference_file}"
                )
