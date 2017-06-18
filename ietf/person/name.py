import re

import debug                            # pyflakes:ignore

def name_parts(name):
    prefix, first, middle, last, suffix = u"", u"", u"", u"", u""

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
        full = u" ".join(parts)
        if full.upper() == full:
            full = full.lower()         # adjust case for all-uppercase input
        # This is an incomplete list.  Adjust as needed to handle known ietf
        # participant names correctly:
        particle = re.search(r" (af|al|Al|de|der|di|Di|du|el|El|Hadi|Le|st\.?|St\.?|ten|ter|van|van der|Van|von|von der|Von|zu) ", full)
        if particle:
            pos = particle.start()
            parts = full[:pos].split() + [full[pos+1:]]
    if len(parts) > 2:
        first = parts[0]
        last = parts[-1]
        # Handle reverse-order names with uppercase surname correctly
        if re.search("^[A-Z-]+$", first):
            first, last = last, first
        middle = u" ".join(parts[1:-1])
    elif len(parts) == 2:
        first, last = parts
    else:
        last = parts[0]
    return prefix, first, middle, last, suffix
    
def initials(name):
    prefix, first, middle, last, suffix = name_parts(name)
    given = first
    if middle:
        given += u" "+middle
    initials = u" ".join([ n[0]+'.' for n in given.split() ])
    return initials

def plain_name(name):
    prefix, first, middle, last, suffix = name_parts(name)
    return u" ".join([first, last])

if __name__ == "__main__":
    import sys
    name = u" ".join(sys.argv[1:])
    print name_parts(name)
    print initials(name)
    
