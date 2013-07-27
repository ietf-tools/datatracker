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

ad_replacement = {
    # 2009 Ad replacements
    'chris.newman@sun.com': 'alexey.melnikov@isode.com',
    'townsley@cisco.com': 'rdroms@cisco.com',
    'jon.peterson@neustar.biz': 'rjsparks@nostrum.com',
    'dward@cisco.com': 'adrian@olddog.co.uk',

    # 2010 AD replacements -- activate after spring ietf
    'lisa@osafoundation.org': 'stpeter@stpeter.im',
    'fluffy@cisco.com': 'gonzalo.camarillo@ericsson.com',
    'rcallon@juniper.net': 'stbryant@cisco.com',
    'pasi.eronen@nokia.com': 'turners@ieca.com',
    'magnus.westerlund@ericsson.com': 'ietfdbh@comcast.net',

    # 2011 AD replacements -- activate after spring ietf
    'alexey.melnikov@isode.com': 'presnick@qualcomm.com',
    'tim.polk@nist.gov': 'stephen.farrell@cs.tcd.ie',
    'lars.eggert@nokia.com': 'wes@mti-systems.com',

    #2013 AD replacements
    'housley@vigilsec.com': 'jari.arkko@piuha.net',
    'rdroms.ietf@gmail.com': 'ted.lemon@nominum.com',
    'rbonica@juniper.net': 'jjaeggli@zynga.com',
    'rjsparks@nostrum.com': 'rbarnes@bbn.com',
    }

email_replacement = {
    'barryleiba@computer.org': 'barryleiba@gmail.com',
    'greg.daley@eng.monash.edu.au': 'gdaley@netstarnetworks.com',
    'radia.perlman@sun.com': 'radia@alum.mit.edu',
    'lisa@osafoundation.org': 'lisa.dusseault@gmail.com',
    'lisa.dusseault@messagingarchitects.com': 'lisa.dusseault@gmail.com',
    'scott.lawrence@nortel.com': 'scottlawrenc@avaya.com',
    'charliep@computer.org': 'charliep@computer.org, charles.perkins@earthlink.net',
    'yaronf@checkpoint.com': 'yaronf.ietf@gmail.com',
    'mary.barnes@nortel.com': 'mary.ietf.barnes@gmail.com',
    'scottlawrenc@avaya.com': 'xmlscott@gmail.com',
    'henk@ripe.net': 'henk@uijterwaal.nl',
    'jonne.soininen@nsn.com': 'jonne.soininen@renesasmobile.com',
    'tom.taylor@rogers.com': 'tom.taylor.stds@gmail.com',
    'rahul@juniper.net': 'raggarwa_1@yahoo.com',
    'dward@juniper.net': 'dward@cisco.com',
    'alan.ford@roke.co.uk': 'alanford@cisco.com',
    'rod.walsh@nokia.com': 'roderick.walsh@tut.fi',
    'bob.hinden@nokia.com': 'bob.hinden@gmail.com',
    'martin.thomson@commscope.com': 'martin.thomson@gmail.com',
    'rjs@estacado.net': 'rjsparks@nostrum.com',
    'rbarnes@bbn.com': 'rlb@ipv.sx',
}


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
    if is_ad:
        email = ad_replacement.get(email, email)
    email = email_replacement.get(email, email)
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

