# Copyright The IETF Trust 2015-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from __future__ import absolute_import, print_function, unicode_literals


import collections
import datetime

import django
django.setup()

from django.core.management.base import BaseCommand #, CommandError

import debug                            # pyflakes:ignore

from ietf.doc.models import NewRevisionDocEvent

RevInfo = collections.namedtuple('RevInfo', ['doc', 'event', 'rev'])

class Command(BaseCommand):
    help = """
    Check that new revision events for drafts have monotonically increasing
    revision numbers and that the latest event revision number matches the
    document revision number.
    """

    def add_arguments(self, parser):
        default_start = datetime.datetime.now() - datetime.timedelta(days=60)
        parser.add_argument(
            '-d', '--from', type=str, default=default_start.strftime('%Y-%m-%d'),
            help='Limit the list to messages saved after the given date (default %(default)s).',
        )
        parser.add_argument('documents', nargs='*',
            help="One or more files to process")

    def handle(self, *args, **options):
        #verbosity = options.get("verbosity", 1)

        self.stdout.write("Checking submissions from %s" % options['from'])

        doc_rev = {}
        events = NewRevisionDocEvent.objects.filter(time__gte=options['from'], doc__type_id='draft').order_by('time')
        if options['documents']:
            events = events.filter(doc__name__in=options['documents'])
        for event in events:
            if not event.rev:
                self.stdout.write("Bad revision number: %s %-52s: '%s'" % (event.time, event.doc.name, event.rev))
                continue
            rev = int(event.rev.lstrip('0') or '0')
            doc = event.doc
            #self.stdout.write("%s %-52s %02s" % (event.time, event.doc.name, event.rev))
            if doc.name in doc_rev:
                if rev <= doc_rev[doc.name].rev:
                    self.stderr.write("%s %-50s %02d -> %02d" % (event.time, event.doc.name, doc_rev[doc.name].rev, rev))
            doc_rev[doc.name] = RevInfo(doc, event, rev)
        for doc, event, rev in doc_rev.values():
            if not doc.rev == event.rev:
                self.stderr.write("%-50s: doc.rev: %s != event.rev: %s" % (doc.name, doc.rev, event.rev))
