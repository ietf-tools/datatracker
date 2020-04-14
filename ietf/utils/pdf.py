# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import re

def pdf_pages(filename):
    """Return number of pages in PDF."""
    try:
        infile = io.open(filename, "rb")
    except IOError:
        return 0
    for line in infile:
        m = re.match(br'\] /Count ([0-9]+)',line)
        if m:
            return int(m.group(1))
    return 0
    
