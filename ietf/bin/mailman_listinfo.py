#!/usr/bin/python2.7
# Copyright The IETF Trust 2022, All Rights Reserved
# Note the shebang. This specifically targets deployment on IETFA and intends to use its system python2.7.

# This is an adaptor to pull information out of Mailman2 using its python libraries (which are only available for python2).
# It is NOT django code, and does not have access to django.conf.settings.

import json
import sys

from collections import defaultdict

def main():

    sys.path.append('/usr/lib/mailman')

    have_mailman = False
    try:
        from Mailman import Utils
        from Mailman import MailList
        from Mailman import MemberAdaptor
        have_mailman = True
    except ImportError:
        pass


    if not have_mailman:
        sys.stderr.write("Could not import mailman modules -- skipping import of mailman list info")
        sys.exit()

    names = list(Utils.list_names())

    # need to emit dict of names, each name has an mlist, and each mlist has description, advertised, and members (calculated as below)
    result = defaultdict(dict)
    for name in names:
        mlist = MailList.MailList(name, lock=False)
        result[name] = dict()
        result[name]['internal_name'] = mlist.internal_name()
        result[name]['real_name'] = mlist.real_name
        result[name]['description'] = mlist.description # Not attempting to change encoding
        result[name]['advertised'] = mlist.advertised
        result[name]['members'] = list()
        if mlist.advertised:
            members = mlist.getRegularMemberKeys() + mlist.getDigestMemberKeys()
            members = set([ m for m in members if mlist.getDeliveryStatus(m) == MemberAdaptor.ENABLED ])
            result[name]['members'] = list(members)
    json.dump(result, sys.stdout)

if __name__ == "__main__":
    main()
