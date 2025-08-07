# Copyright The IETF Trust 2011-2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

# Static values
__version__ = '3.30.0'
NAME         = 'xml2rfc'
VERSION      = [ int(i) if i.isdigit() else i for i in __version__.split('.') ]
CACHES       = ['/var/cache/xml2rfc', '~/.cache/xml2rfc']  # Ordered by priority
CACHE_PREFIX = ''
NET_SUBDIRS  = ['bibxml', 'bibxml-misc', 'bibxml-ids', 'bibxml-w3c', 'bibxml-3gpp', 'bibxml-ieee', 'bibxml-rfcsubseries']
V3_PI_TARGET = 'v3xml2rfc'

from xml2rfc.parser import  XmlRfcError, CachingResolver, XmlRfcParser, XmlRfc

from xml2rfc.writers import ( BaseRfcWriter, RawTextRfcWriter, PaginatedTextRfcWriter,
	 HtmlRfcWriter, NroffRfcWriter, ExpandedXmlWriter, RfcWriterError,
         V2v3XmlWriter, PrepToolWriter, TextWriter, HtmlWriter, PdfWriter,
         ExpandV3XmlWriter, UnPrepWriter, DocWriter, DatatrackerToBibConverter,
     )

# This defines what 'from xml2rfc import *' actually imports:
__all__ = ['XmlRfcError', 'CachingResolver', 'XmlRfcParser', 'XmlRfc',
           'BaseRfcWriter', 'RawTextRfcWriter', 'PaginatedTextRfcWriter',
           'HtmlRfcWriter', 'NroffRfcWriter', 'ExpandedXmlWriter',
           'RfcWriterError', 'V2v3XmlWriter', 'PrepToolWriter', 'TextWriter',
           'HtmlWriter', 'PdfWriter', 'ExpandV3XmlWriter', 'UnPrepWriter', 
           'DocWriter', 'DatatrackerToBibConverter',
       ]

try:
    import weasyprint
    HAVE_WEASYPRINT = True
except (ImportError, OSError, ValueError):
    weasyprint = False
    HAVE_WEASYPRINT = False
try:
    from weasyprint.text.ffi import pango
    HAVE_PANGO = True
    PANGO_VERSION = pango.pango_version
except (ImportError, OSError, AttributeError):
    HAVE_PANGO = False
    PANGO_VERSION = None


def get_versions():
    import sys
    versions = []
    try:
        from importlib import metadata
        from re import split
        this = metadata.distribution(NAME)
        for p in [split(r'[\s=<>!]', x)[0] for x in this.requires]:
            try:
                dist = metadata.distribution(p)
                versions.append((dist.metadata['name'], dist.metadata['version']))
            except:
                pass
    except:
        pass

    versions.sort(key=lambda x: x[0].lower())
    versions = [
            (NAME, __version__),
            ('Python', sys.version.split()[0]),
        ] + versions

    return versions
