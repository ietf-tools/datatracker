# Copyright The IETF Trust 2016-2019, All Rights Reserved

import sys
import time
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
from ietf.utils.log import log
from ietf.utils.text import decode

mark = time.time()

def import_mailman_listinfo(verbosity=0):
    def note(msg):
        if verbosity > 2:
            sys.stdout.write(msg)
            sys.stdout.write('\n')
    def log_time(msg):
        global mark
        if verbosity > 1:
            t = time.time()
            log(msg+' (%.1fs)'% (t-mark))
            mark = t

    if not have_mailman:
        note("Could not import mailman modules -- skipping import of mailman list info")
        return

    log("Starting import of list info from Mailman")
    names = list(Utils.list_names())
    names.sort()
    log_time("Fetched list of mailman list names")
    addr_max_length = Subscribed._meta.get_field('email').max_length
    
    subscribed = { l.name: set(l.subscribed_set.values_list('email', flat=True)) for l in List.objects.all().prefetch_related('subscribed_set') }
    log_time("Computed dictionary of list members")

    for name in names:
        mlist = MailList.MailList(name, lock=False)
        note("List: %s" % mlist.internal_name())
        log_time("Fetched Mailman list object for %s" % name)

        lists = List.objects.filter(name=mlist.real_name)
        if lists.count() > 1:
            # Arbitrary choice; we'll update the remaining item next
            for item in lists[1:]:
                item.delete()
        mmlist, created = List.objects.get_or_create(name=mlist.real_name)
        dirty = False
        desc = decode(mlist.description)[:256]
        if mmlist.description != desc:
            mmlist.description = desc
            dirty = True
        if mmlist.advertised != mlist.advertised:
            mmlist.advertised = mlist.advertised
            dirty = True
        if dirty:
            mmlist.save()
        log_time("  Updated database List object for %s" % name)
        # The following calls return lowercased addresses
        if mlist.advertised:
            members = mlist.getRegularMemberKeys() + mlist.getDigestMemberKeys()
            log_time("  Fetched list of list members")
            members = set([ m for m in members if mlist.getDeliveryStatus(m) == MemberAdaptor.ENABLED ])
            log_time("  Filtered list of list members")
            if not mlist.real_name in subscribed:
                log("Note: didn't find '%s' in the dictionary of subscriptions" % mlist.real_name)
                continue
            known = subscribed[mlist.real_name]
            log_time("  Fetched known list members from database")            
            to_remove = known - members
            to_add = members - known
            for addr in to_remove:
                    note("  Removing subscription: %s" % (addr))
                    old = Subscribed.objects.get(email=addr)
                    log_time("    Fetched subscribed object")
                    old.lists.remove(mmlist)
                    log_time("    Removed %s from %s" % (mmlist, old))
                    if old.lists.count() == 0:
                        note("    Removing address with no subscriptions: %s" % (addr))
                        old.delete()
                        log_time("      Removed %s" % old)
            log_time("  Removed addresses no longer subscribed")
            if to_remove:
                log("  Removed %s addresses from %s" % (len(to_remove), name))
            for addr in to_add:
                if len(addr) > addr_max_length:
                    sys.stderr.write("    **  Email address subscribed to '%s' too long for table: <%s>\n" % (name, addr))
                    continue
                note("  Adding subscription: %s" % (addr))
                try:
                    new, created = Subscribed.objects.get_or_create(email=addr)
                except MultipleObjectsReturned as e:
                    sys.stderr.write("    **  Error handling %s in %s: %s\n" % (addr, name, e))
                    continue
                new.lists.add(mmlist)
            log_time("  Added new addresses")
            if to_add:
                log("  Added %s addresses to %s" % (len(to_add), name))
    log("Completed import of list info from Mailman")    

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
