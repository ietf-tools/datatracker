# Copyright The IETF Trust 2015-2019, All Rights Reserved
import re

def pdf_pages(filename):
    """Return number of pages in PDF."""
    try:
        infile = open(filename, "r")
    except IOError:
        return 0
    for line in infile:
        m = re.match(r'\] /Count ([0-9]+)',line)
        if m:
            return int(m.group(1))
    return 0
    
