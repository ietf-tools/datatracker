# -*- coding: utf-8 -*-
# Copied from https://github.com/leoboiko/uniscripts and modified.

'''Python interface to query Unicode UCD script data (UAX #24).

Tests whether a character belongs to a script, and so on.  This module is quite
dumb and slow.
'''
from __future__ import absolute_import

from .unidata import RANGES#, SCRIPT_ABBREVS

def in_any_seq(item, seq_seq):
    """Returns: true if item is present in any sequence of the sequence of sequences.

    >>> in_any_seq(1, [(2,3,4),(3,2,1)])
    True
    >>> in_any_seq(1, [[2,3,4],[3,2,3]])
    False

    """

    for seq in seq_seq:
        if item in seq:
            return True
    return False

def is_script(string, script, ignore=['Inherited', 'Common', 'Unknown']):
    """Returns: true if all chars in string belong to script.

    Args:
        string: A string to test (may be a single char).
        script: Script long name, as in Unicode UCD's Scripts.txt (viz.).
        ignore: A list of scripts that will always suceed for matching purposes.
            For example, ASCII punctuation is listed as 'Common', so 'A.' will
            match as 'Latin', and 'あ.' will match as 'Hiragana'.  See UAX #24
            for details.

    >>> is_script('A', 'Latin')
    True
    >>> is_script('Artemísia', 'Latin')
    True
    >>> is_script('ἀψίνθιον ', 'Latin')
    False
    >>> is_script('Let θι = 3', 'Latin', ignore=['Greek', 'Common', 'Inherited', 'Unknown'])
    True
    >>> is_script('はるはあけぼの', 'Hiragana')
    True
    >>> is_script('はるは:あけぼの.', 'Hiragana')
    True
    >>> is_script('はるは:あけぼの.', 'Hiragana', ignore=[])
    False

    """

    if ignore == None: ignore = []
    ignore_ranges = []
    for ignored in ignore:
        ignore_ranges += RANGES[ignored]

    for char  in string:
        cp = ord(char)
        if ((not in_any_seq(cp, RANGES[script.capitalize()]))
            and not in_any_seq(cp, ignore_ranges)):
            return False
    return True

def which_scripts(char):
    """Returns: list of scripts that char belongs to.

    >>> which_scripts('z')
    ['Latin']
    >>> which_scripts('.')
    ['Common']
    >>> which_scripts('は')
    ['Hiragana']
    >>> sorted(which_scripts('،')) # u+060c
    ['Arabic', 'Common', 'Syriac', 'Thaana']
    >>> sorted(which_scripts('゙')) # u+3099
    ['Hiragana', 'Inherited', 'Katakana']
    >>> which_scripts("\ue000")
    ['Unknown']
    """

    cp = ord(char)
    scripts = []
    for script, ranges in RANGES.items():
        if in_any_seq(cp, ranges):
            scripts.append(script)
    if scripts:
        return(scripts)
    else:
        return(['Unknown'])

if __name__ == "__main__":
    import doctest
    doctest.testmod()
