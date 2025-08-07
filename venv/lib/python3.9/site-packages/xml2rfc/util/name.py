 # Copyright The IETF Trust 2017, All Rights Reserved
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function

from xml2rfc.uniscripts import is_script

try:
    from xml2rfc import debug
    debug.debug = True
except ImportError:
    pass

def get_initials(a):
    initials = a.get('initials')
    pp = a.getparent().getparent()
    if pp.tag == 'reference':
        s = pp.find('seriesInfo[@name="RFC"]')
        if s != None:
            number = s.get('value')
            if number and number.isdigit() and int(number) <= 1272:
                # limit to one initial for RFC 1272 and earlier
                if initials:
                    initials = initials.split('.')[0]
    return initials

def short_author_name_parts(a):
    initials = get_initials(a)
    surname  = a.get('surname')
    if initials!=None and surname!=None:
        if initials and not initials.endswith('.') and is_script(initials, 'Latin'):
            initials += '.'

        parts = [initials, surname]
    else:
        fullname = a.get('fullname') or ''
        if fullname:
            if is_script(fullname, 'Latin'):
                if len(fullname.split())>1:
                    parts = fullname.split()
                    initials = ' '.join([ "%s."%n[0].upper() if len(n) > 1 else n.upper() for n in parts[:-1] ])
                    surname  = parts[-1]
                    parts = [initials, surname ]
                else:
                    parts = [ None, fullname ]
            else:
                parts = [ None, fullname ]
        else:
            parts = [None, None]
    return parts

def short_author_name(a):
    return ' '.join(n for n in short_author_name_parts(a) if n)

def short_author_ascii_name_parts(a):
    initials = a.get('asciiInitials')
    surname  = a.get('asciiSurname')
    if initials!=None and surname!=None:
        if initials and not initials.endswith('.'):
            initials += '.'
        parts = [initials, surname]
    else:
        fullname = a.get('asciiFullname')
        if fullname:
            if len(fullname.split())>1:
                parts = fullname.split()
                initials = ' '.join([ "%s."%n[0].upper() if len(n) > 1 else n.upper() for n in parts[:-1] ])
                surname  = parts[-1]
                parts = [ initials, surname ]
            else:
                parts = [ None, fullname ]
        else:
            parts = [ None, None ]
    return parts if parts!=[None,None] else short_author_name_parts(a)

def short_author_ascii_name(a):
    return ' '.join(n for n in short_author_ascii_name_parts(a) if n)

def short_author_name_set(a):
    name = short_author_name(a)
    ascii = None
    if name:
        if is_script(name, 'Latin'):
            ascii = None
        else:
            ascii = short_author_ascii_name(a)
        if name == ascii:
            ascii = None
    return name, ascii

def ref_author_name_first(a):
    """
    Returns a tuple, with the second set only if the first part has
    non-Latin codepoints.  The initials and surname order is as needed
    for the first and following reference author names, but not for
    the last author.
    """
    i, s = short_author_name_parts(a)
    name = ', '.join(p for p in [s, i] if p)
    if name:
        if is_script(name, 'Latin'):
            ascii = None
        else:
            i, s = short_author_ascii_name_parts(a)
            ascii = ', '.join(p for p in [s, i] if p)
    else:
        name = short_org_name(a)
        if is_script(name, 'Latin'):
            ascii = None
        else:
            ascii = short_org_ascii_name(a)
    if name == ascii:
        ascii = None
    return name, ascii

def ref_author_name_last(a):
    """
    Returns a tuple, with the second set only if the first part has
    non-Latin codepoints.  The initials and surname order is as needed
    for the last author name in a list of reference author names.
    """
    name = short_author_name(a)
    if name:
        if is_script(name, 'Latin'):
            ascii = None
        else:
            ascii = short_author_ascii_name(a)
    else:
        name = short_org_name(a)
        if is_script(name, 'Latin'):
            ascii = None
        else:
            ascii = short_org_ascii_name()
    if name == ascii:
        ascii = None
    return name, ascii


def full_author_name(a, latin=False):
    if latin:
        return full_author_ascii_name(a)
    fullname = a.get('fullname')
    if fullname:
        return fullname
    else:
        initials = get_initials(a)
        surname  = a.get('surname')
        if initials and not initials.endswith('.') and is_script(initials, 'Latin'):
            initials += '.'
        return ' '.join( n for n in [initials, surname] if n )

def full_author_ascii_name(a):
    fullname = a.get('asciiFullname')
    if fullname:
        full = fullname
    else:
        initials = a.get('asciiInitials') or get_initials(a)
        surname  = a.get('asciiSurname')  or a.get('surname')
        if initials and not initials.endswith('.'):
            initials += '.'
        full = ' '.join( n for n in [initials, surname] if n )
    return full or full_author_name(a)

def full_author_name_set(a):
    name = full_author_name(a)
    if name:
        if is_script(name, 'Latin'):
            ascii = None
        else:
            ascii = full_author_ascii_name(a)
    else:
        name = full_org_name(a)
        ascii = full_org_ascii_name(a)
    if name == ascii:
        ascii = None
    return name, ascii

def full_author_name_expansion(a):
    name, ascii = full_author_name_set(a)
    return "%s (%s)" % (name, ascii) if ascii else name

def short_author_role(a):
    role = a.get('role')
    text = ''
    if role:
        if role == 'editor':
            text = 'Ed.'
        else:
            text = role.title()
    return text

def short_org_name(a):
    org = a.find('organization')
    return org.get('abbrev') or org.text or '' if org != None else ''

def short_org_ascii_name(a):
    org = a.find('organization')
    if org == None:
        return ''
    org_name = (a.get('asciiAbbrev') or org.get('ascii')
                or org.get('abbrev') or org.text or '')
    return org_name
    
def short_org_name_set(a):
    name = short_org_name(a)
    if name:
        if is_script(name, 'Latin'):
            ascii = None
        else:
            ascii = short_org_ascii_name(a)
    else:
        ascii = None
    if name == ascii:
        ascii = None
    return name, ascii

def full_org_name(a):
    org = a.find('organization')
    return org.text or '' if org != None else ''

def full_org_ascii_name(a):
    org = a.find('organization')
    if org == None:
        return ''
    if is_script(org.text, 'Latin'):
        org_name = org.text
    else:
        org_name = org.get('ascii') or ''
    return org_name
    
