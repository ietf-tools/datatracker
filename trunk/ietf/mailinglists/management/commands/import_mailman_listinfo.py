# Copyright The IETF Trust 2016, All Rights Reserved

import sys
from textwrap import dedent

import debug                            # pyflakes:ignore

from django.conf import settings
from django.core.management.base import BaseCommand

sys.path.append(settings.MAILMAN_LIB_DIR)

have_mailman = False
try:
    from Mailman import Utils
    from Mailman import MailList
    from Mailman import MemberAdaptor
    have_mailman = True
except ImportError:
    pass

from ietf.mailinglists.models import List, Subscribed

def import_mailman_listinfo(verbosity=0):
    def note(msg):
        if verbosity > 1:
            sys.stdout.write(msg)
            sys.stdout.write('\n')

    if not have_mailman:
        note("Could not import mailman modules -- skipping import of mailman list info")
        return

    for name in Utils.list_names():
        mlist = MailList.MailList(name, lock=False)
        note("List: %s" % mlist.internal_name())
        if mlist.advertised:
            list, created = List.objects.get_or_create(name=mlist.real_name, description=mlist.description, advertised=mlist.advertised)
            # The following calls return lowercased addresses
            members = mlist.getRegularMemberKeys() + mlist.getDigestMemberKeys()
            members = [ m for m in members if mlist.getDeliveryStatus(m) == MemberAdaptor.ENABLED ]
            known = Subscribed.objects.filter(lists__name=name).values_list('email', flat=True)
            for addr in known:
                if not addr in members:
                    note("  Removing subscription: %s" % (addr))
                    old = Subscribed.objects.get(email=addr)
                    old.lists.remove(list)
                    if old.lists.count() == 0:
                        note("    Removing address with no subscriptions: %s" % (addr))
                        old.delete()
            for addr in members:
                if not addr in known:
                    note("  Adding subscription: %s" % (addr))
                    new, created = Subscribed.objects.get_or_create(email=addr)
                    new.lists.add(list)
    

class Command(BaseCommand):
    """
    Import list information from Mailman.

    Import announced list names, descriptions, and subscribers, by calling the
    appropriate Mailman functions and adding entries to the database.

    Run this from cron regularly, with sufficient permissions to access the
    mailman database files.

    """

    help = dedent(__doc__).strip()
            
    #option_list = BaseCommand.option_list + (       )


    def handle(self, *filenames, **options):
        """

        * Import announced lists, with appropriate meta-information.

        * For each list, import the members.

        """

        verbosity = int(options.get('verbosity'))

        import_mailman_listinfo(verbosity)
