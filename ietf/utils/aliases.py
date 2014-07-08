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

from django.conf import settings

def rewrite_email_address(email):
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

def dump_sublist(afile, vfile, alias, emails):
    if not emails:
        return emails
    # Nones in the list should be skipped
    emails = filter(None, emails)

    # Make sure emails are sane and eliminate the Nones again for
    # non-sane ones
    emails = [rewrite_email_address(e) for e in emails]
    emails = filter(None, emails)

    # And we'll eliminate the duplicates too but preserve order
    emails = list(rewrite_address_list(emails))
    if not emails:
        return emails
    try:
        virtualname = 'xalias-%s' % (alias, )
        expandname  = 'expand-%s' % (alias)
        aliasaddr   = '%s@ietf.org' % (alias, )

        vfile.write('%-64s  %s\n' % (aliasaddr, virtualname))
        afile.write('%-64s  "|%s filter %s"\n' % (virtualname+':', settings.POSTCONFIRM_PATH, expandname))
        afile.write('%-64s  %s\n' % (expandname+':', ', '.join(emails)))

    except UnicodeEncodeError:
        # If there's unicode in email address, something is badly
        # wrong and we just silently punt
        # XXX - is there better approach?
        print '# Error encoding', alias, repr(emails)
        return []
    return emails

