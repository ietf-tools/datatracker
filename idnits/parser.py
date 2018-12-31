# Copyright 2018-2019 IETF Trust, All Rights Reserved
# -*- coding: utf-8 indent-with-tabs: 0 -*-

from __future__ import unicode_literals, print_function, division

import io
import lxml
import os
import six
import xml2rfc

from id2xml.utils import strip_pagebreaks
from idnits.utils import Line, build_paragraphs
from winmagic import magic

try:
    import debug
    assert debug
except ImportError:
    pass

# ----------------------------------------------------------------------

class Doc(object):
    def __init__(self, name=None, raw=None, xml=None, type=None):
        self.name = name
        self.txt = raw
        self.xml = xml
        self.root = None
        self.err = []
        self.type = type                # Input type: 'txt' or 'xml'

def get_mime_type(filename):
    m = magic.Magic(mime=True, mime_encoding=True)
    return m.from_file(filename)

def parse(filename, options):

    doc = Doc(name=filename)

    content_type = get_mime_type(filename)
    mime, charset = content_type.split(';')
    doc.type = mime

    key, enc = charset.split('=')
    doc.encoding = enc
    with io.open(filename, "rb") as file:
        doc.raw = file.read()
    if mime in ['text/plain', ]:
        with io.open(filename, "rb") as file:
            doc.raw = file.read()
        with io.open(filename, encoding=enc) as file:
            doc.txt = file.read()
        doc.lines, __ = strip_pagebreaks(doc.txt.expandtabs())
        doc.paras = build_paragraphs(doc.lines)
        doc.root = None
#         basename = os.path.basename(filename)
#         options.doc_stream = None
#         options.skip_memo = False
#         options.schema = 'v3'
#         options.silent = True
#         idparser = id2xml.parser.DraftParser(basename, doc.txt, options)
#         doc.xml = idparser.parse_to_xml()
    elif mime in ['application/xml', 'text/xml', ]:
        #doc.xml = lxml.etree.parse(filename)
        logfile = io.BytesIO()
        # capture errors
        xml2rfc.log.write_err = logfile
        try:
            parser = xml2rfc.XmlRfcParser(filename)
            doc.xmlrfc = parser.parse()
            doc.xml  = doc.xmlrfc.tree
            try:
                doc.xml.xinclude()
            except lxml.etree.XIncludeError as e:
                doc.err.append("XInclude processing failed: %s" % e)
            doc.root = doc.xml.getroot()
        except Exception as e:
            doc.err.append(e)
        log = logfile.getvalue()
        for line in log.splitlines():
            if 'Error' in line or 'Warning' in line:
                doc.err.append(line)
            else:
                print(line)
        #
        if doc.xml:
            encoding = doc.xmlrfc.tree.docinfo.encoding
            with io.open(filename, encoding=encoding) as file:
                try:
                    doc.txt = file.read()
                except UnicodeDecodeError as e:
                    sys.exit("Tried to read XML file with declared encoding (%s) but got %s."
                        "Cannot continue, quitting now." % encoding)
            doc.lines = [ Line(n, l) for (n, l) in enumerate(doc.txt.splitlines()) ]
    return doc
