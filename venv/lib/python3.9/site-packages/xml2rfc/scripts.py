# Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

import intervaltree
import os
from codecs import open

try:
    import debug
    debug.debug = True
except ImportError:
    pass

scripts = intervaltree.IntervalTree()

def init():
    # Clocked to less than 0.2 seconds on a 2GHz core 08 Feb 2018
    fn = os.path.join(os.path.dirname(__file__), 'data', 'Scripts.txt')
    with open(fn, encoding='utf-8') as f:
        text = f.read()
    for line in text.splitlines():
        if line.startswith('#'):
            continue
        if not line:
            continue
        line = line.strip()
        data, comment = line.split('#', 1)
        codepoints, script = data.split(';', 1)
        if '..' in codepoints:
            start, stop = [ int(x.strip(), base=16) for x in codepoints.split('..') ]
            scripts[start:stop+1] = script.strip()
        else:
            start = int(codepoints.strip(), base=16)
            scripts[start:start+1] = script.strip()

def get_scripts(text):
    """"Return the unicode scripts used in text.

    Assumes that ascii characters are common in the input.
    Clocked to about 0.5 seconds per million characters
    on a 2Ghz core given input with about 60% ascii.
    """
    scriptset = set()
    for i, c in enumerate(text):
        o = ord(c)
        if i < 100 or o > 127:
            scriptset |= scripts[o]
    return set([ s.data for s in scriptset ])

init()

