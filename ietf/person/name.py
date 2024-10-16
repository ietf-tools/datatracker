# Copyright The IETF Trust 2011-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import re
import unidecode

import debug                            # pyflakes:ignore


def name_particle_match(name):
    return re.search(r" (af|al|Al|de|De|der|di|Di|du|el|El|Hadi|in 't|Le|st\.?|St\.?|ten|ter|van|van der|van 't|Van|von|von der|Von|zu) ", name)

def name_parts(name):
    prefix, first, middle, last, suffix = "", "", "", "", ""

    if not name.strip():
        return prefix, first, middle, last, suffix

    # if we got a name on the form "Some Name (Foo Bar)", get rid of
    # the paranthesized part
    name_with_paren_match = re.search(r"^([^(]+)\s*\(.*\)$", name)
    if name_with_paren_match:
        name = name_with_paren_match.group(1)

    parts = name.split()
    if len(parts) > 2 and parts[0] in ["M", "M.", "Sri", ] and "." not in parts[1]:
        prefix = parts[0];
        parts = parts[1:]
    prefix = []
    while len(parts) > 1 and parts[0] in ["Mr", "Mr.", "Mrs", "Mrs.", "Ms", "Ms.", "Miss", "Dr",
        "Dr.", "Doctor", "Prof", "Prof.", "Professor", "Sir", "Lady", "Dame", 
        "Gen.", "Col.", "Maj.", "Capt.", "Lieut.", "Lt.", "Cmdr.", "Col.", ]:
        prefix.append(parts[0])
        parts = parts[1:]
    prefix = " ".join(prefix)
    if len(parts) > 2:
        if parts[-1] in ["Jr", "Jr.", "II", "2nd", "III", "3rd", "Ph.D."]:
            suffix = parts[-1]
            parts = parts[:-1]
    if len(parts) > 2:
        # Check if we have a surname with nobiliary particle
        full = " ".join(parts)
        if full.upper() == full:
            full = full.lower()         # adjust case for all-uppercase input
        # This is an incomplete list.  Adjust as needed to handle known ietf
        # participant names correctly:
        particle = name_particle_match(full)
        if particle:
            pos = particle.start()
            parts = full[:pos].split() + [full[pos+1:]]
    if len(parts) > 2:
        first = parts[0]
        last = parts[-1]
        middle = " ".join(parts[1:-1])
    elif len(parts) == 2:
        first, last = parts
    else:
        last = parts[0]
    if len(parts) >= 2:
        # Handle reverse-order names with uppercase surname correctly
        if len(first)>1 and re.search("^[A-Z-]+$", first) and first != "JP":
            first, last = last, first.capitalize()
    # Handle exception for RFC Editor
    if (prefix, first, middle, last, suffix) == ('', 'Editor', '', 'Rfc', ''):
        first = 'RFC'
        last = 'Editor'
    return prefix, first, middle, last, suffix

def initials(name):
    prefix, first, middle, last, suffix = name_parts(name)
    given = first
    if middle:
        given += " "+middle
    # Don't use non-word characters as initials.
    # Example: The Bulgarian transcribed name "'Rnest Balkanska" should not have an initial of "'".
    given = re.sub(r'[^ .\w]', '', given)
    initials = " ".join([ n[0].upper()+'.' for n in given.split() ])
    return initials

def plain_name(name):
    prefix, first, middle, last, suffix = name_parts(name)
    return " ".join( n for n in (first, last) if n)

def capfirst(s):
    # Capitalize the first word character, skipping non-word characters and
    # leaving following word characters untouched:
    letters = list(s)
    for i,l in enumerate(letters):
        if l.isalpha():
            letters[i] = l.capitalize()
            break
    return ''.join(letters)

def unidecode_name(uname):
    """
    unidecode() of cjk ideograms can produce strings which contain spaces.
    Strip leading and trailing spaces, and reduce double-spaces to single.

    For some other ranges, unidecode returns all-lowercase names; fix these
    up with capitalization.
    """
    # Fix double spacing
    name = unidecode.unidecode(uname)
    if name == uname:
        return name
    name = re.sub('  +', ' ', name.strip().replace('@', '').replace('"', ''))
    name = re.sub(r'(\w)\.(\w)', r'\1\2', name)
    # Fix all-upper and all-lower names:
    # Check for name particles -- don't capitalize those
    m = name_particle_match(name)
    particle = m.group(1) if m else None
    # Get the name parts
    prefix, first, middle, last, suffix = name_parts(name)
    # Capitalize names
    first = first.title()
    middle = ' '.join([ capfirst(p) for p in middle.split() ])
    last   = ' '.join([ capfirst(p) for p in last.split() ])
    if len(last) == 1:
        last = (last+last).capitalize()
    # Restore the particle, if any
    if particle and last.startswith(capfirst(particle)+' '):
        last = ' '.join([ particle, last[len(particle)+1:] ])
    # Recombine the parts
    parts = prefix, first, middle, last, suffix
    name = ' '.join([ p for p in parts if p and p.strip() != '' ])
    name = re.sub('  +', ' ', name)
    return name

def normalize_name(s):
    # There is probably more to be done here, but we start by normalising
    # spaces:
    s = re.sub('  +', ' ', s)
    return s

if __name__ == "__main__":
    import sys
    name = " ".join(sys.argv[1:])
    print(name_parts(name))
    print(initials(name))
    
