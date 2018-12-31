# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 indent-with-tabs: 0 -*-

from __future__ import unicode_literals, print_function, division

# Static values
__version__  = '3.0.0'
NAME         = 'idnits'
VERSION      = [ int(i) if i.isdigit() else i for i in __version__.split('.') ]

DESCRIPTION  = """Report issues with a draft or RFC document.

The idnits program inspects Internet-Draft documents for a variety of
conditions that should be adjusted to bring the document into line with
policies from the IETF, the IETF Trust, and the RFC Editor. 

The determination of which issues are to be repored is based on:

 * Requirements in https://www.ietf.org/id-info/1id-guidelines.txt
 * Requirements in https://www.ietf.org/id-info/checklist
 * Additional requirements captured from ADs and authors over time
 * Requirements in https://iaoc.ietf.org/documents/idnits-SOW-00.pdf

"""

class Options(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            if not k.startswith('__'):
                setattr(self, k, v)
    pass

default_options = Options(debug=False, docs=[], mode='normal', silent=False, verbose=False, version=False, )

