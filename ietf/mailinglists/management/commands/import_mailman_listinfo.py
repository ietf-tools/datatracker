# Copyright The IETF Trust 2016, All Rights Reserved

import sys
from textwrap import dedent

import debug                            # pyflakes:ignore

from django.conf import settings
from django.core.management.base import BaseCommand

sys.path.append(settings.MAILMAN_LIB_DIR)

from Mailman import Utils
from Mailman import MailList

from ietf.mailinglists.models import List, Subscribed

def import_mailman_listinfo(verbosity=0):
    def note(msg):
        if verbosity > 1:
            sys.stdout.write(msg)
            sys.stdout.write('\n')

    for name in Utils.list_names():
        mlist = MailList.MailList(name, lock=False)
        note("List: %s" % mlist.internal_name())
        if mlist.advertised:
            list, created = List.objects.get_or_create(name=mlist.real_name, description=mlist.description, advertised=mlist.advertised)
            # The following calls return lowercased addresses
            members = mlist.getRegularMemberKeys() + mlist.getDigestMemberKeys()
            known = [ s.email for s in Subscribed.objects.filter(lists__name=name) ]
            for addr in members:
                if not addr in known:
                    note("  Adding subscribed: %s" % (addr))
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
