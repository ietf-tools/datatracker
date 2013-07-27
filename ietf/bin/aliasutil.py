#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- Python -*-
#
# $Id: aliasutil.py $
#
# Author: Markus Stenberg <mstenber@cisco.com>
#
"""

Mailing list alias dumping utilities

"""

def rewrite_email_address(email, is_ad):
    """ Prettify the email address (and if it's empty, skip it by
    returning None). """
    if not email:
        return
    email = email.strip()
    if not email:
        return
    if email[0]=='<' and email[-1] == '>':
        email = email[1:-1]
    # If it doesn't look like email, skip
    if '@' not in email and '?' not in email:
        return
    return email

def rewrite_address_list(l):
    """ This utility function makes sure there is exactly one instance
    of an address within the result list, and preserves order
    (although it may not be relevant to start with) """
    h = {}
    for address in l:
        #address = address.strip()
        if h.has_key(address): continue
        h[address] = True
        yield address

def dump_sublist(alias, f, wg, is_adlist=False):
    if f:
        l = f(wg)
    else:
        l = wg
    if not l:
        return
    # Nones in the list should be skipped
    l = filter(None, l)

    # Make sure emails are sane and eliminate the Nones again for
    # non-sane ones
    l = [rewrite_email_address(e, is_adlist) for e in l]
    l = filter(None, l)

    # And we'll eliminate the duplicates too but preserve order
    l = list(rewrite_address_list(l))
    if not l:
        return
    try:
        print '%s: %s' % (alias, ', '.join(l))
    except UnicodeEncodeError:
        # If there's unicode in email address, something is badly
        # wrong and we just silently punt
        # XXX - is there better approach?
        print '# Error encoding', alias, repr(l)
        return
    return l

