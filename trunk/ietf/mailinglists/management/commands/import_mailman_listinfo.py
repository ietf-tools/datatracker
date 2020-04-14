# Copyright The IETF Trust 2016-2019, All Rights Reserved

import sys
from textwrap import dedent

import debug                            # pyflakes:ignore

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.exceptions import MultipleObjectsReturned

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
from ietf.utils.text import decode

def import_mailman_listinfo(verbosity=0):
    def note(msg):
        if verbosity > 1:
            sys.stdout.write(msg)
            sys.stdout.write('\n')

    if not have_mailman:
        note("Could not import mailman modules -- skipping import of mailman list info")
        return

    names = list(Utils.list_names())
    names.sort()
    addr_max_length = Subscribed._meta.get_field('email').max_length
    for name in names:
        mlist = MailList.MailList(name, lock=False)
        note("List: %s" % mlist.internal_name())

        lists = List.objects.filter(name=mlist.real_name)
        if lists.count() > 1:
            # Arbitrary choice; we'll update the remaining item next
            for item in lists[1:]:
                item.delete()
        mmlist, created = List.objects.get_or_create(name=mlist.real_name)
        mmlist.description = decode(mlist.description)[:256]
        mmlist.advertised = mlist.advertised
        mmlist.save()
        # The following calls return lowercased addresses
        if mlist.advertised:
            members = mlist.getRegularMemberKeys() + mlist.getDigestMemberKeys()
            members = [ m for m in members if mlist.getDeliveryStatus(m) == MemberAdaptor.ENABLED ]
            known = Subscribed.objects.filter(lists__name=name).values_list('email', flat=True)
            for addr in known:
                if not addr in members:
                    note("  Removing subscription: %s" % (addr))
                    old = Subscribed.objects.get(email=addr)
                    old.lists.remove(mmlist)
                    if old.lists.count() == 0:
                        note("    Removing address with no subscriptions: %s" % (addr))
                        old.delete()
            for addr in members:
                if len(addr) > addr_max_length:
                    sys.stderr.write("    **  Email address subscribed to '%s' too long for table: <%s>\n" % (name, addr))
                    continue
                if not addr in known:
                    note("  Adding subscription: %s" % (addr))
                    try:
                        new, created = Subscribed.objects.get_or_create(email=addr)
                    except MultipleObjectsReturned as e:
                        sys.stderr.write("    **  Error handling %s in %s: %s\n" % (addr, name, e))
                        continue
                    new.lists.add(mmlist)
    

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
