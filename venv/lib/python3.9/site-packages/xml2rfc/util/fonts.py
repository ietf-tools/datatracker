# Copyright The IETF Trust 2018, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, division

# ----------------------------------------------------------------------
# Font operations

def get_noto_serif_family_for_script(script):
    """
    This translates from the official unicode script names to the fonts
    actually available in the Noto font family.  The set of fonts known
    to have serif versions is up-to-date as of 05 Dec 2018, for the
    Noto font pack built on 2017-10-24, available as
    https://noto-website-2.storage.googleapis.com/pkgs/Noto-unhinted.zip
    """
    fontname = {
        'Latin':    'Noto Serif',
        'Common':   'Noto Serif',
        'Greek':    'Noto Serif',
        'Cyrillic': 'Noto Serif',
        'Tai_Viet': 'Noto Serif',
        # Script names that don't match font names
        'Han':      'Noto Serif CJK SC',
        'Hangul':   'Noto Serif CJK KR',
        'Hiragana': 'Noto Serif CJK JP',
        'Katakana': 'Noto Serif CJK JP',
        # Script names available in Serif
        'Armenian':	'Noto Serif Armenian',
        'Bengali':	'Noto Serif Bengali',
        'Devanagari':'Noto Serif Devanagari',
        'Display':	'Noto Serif Display',
        'Ethiopic':	'Noto Serif Ethiopic',
        'Georgian':	'Noto Serif Georgian',
        'Gujarati':	'Noto Serif Gujarati',
        'Hebrew':	'Noto Serif Hebrew',
        'Kannada':	'Noto Serif Kannada',
        'Khmer':	'Noto Serif Khmer',
        'Lao':	'Noto Serif Lao',
        'Malayalam':'Noto Serif Malayalam',
        'Myanmar':	'Noto Serif Myanmar',
        'Sinhala':	'Noto Serif Sinhala',
        'Tamil':	'Noto Serif Tamil',
        'Telugu':	'Noto Serif Telugu',
        'Thai':	'Noto Serif Thai',
        # Other names may be available in Sans
    }
    if script in fontname:
        family = "%s" % fontname[script]
    else:
        script = script.replace('_', ' ')
        family = "Noto Sans %s" % script
    return family
    