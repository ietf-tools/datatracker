# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


import email
import datetime

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.message.models import Message
from ietf.utils.mail import parseaddr

class Command(BaseCommand):
    help = """

    Show outgoing messages that have been saved as Message objects.  By default
    all messages from the last 2 weeks are shown.  Selection can be made based
    on date and sent/unsent state.  With the --pk option, only a list of primary
    keys are shown, otherwise, creation and send date, message-id, sender and
    primary recipients, and subject line is shown.  The list of primary keys is
    suitable for input to the send_messages management command.

    """

    def add_arguments(self, parser):
        default_start = datetime.datetime.now() - datetime.timedelta(days=14)
        parser.add_argument(
            '-t', '--start', '--from', type=str, default=default_start.strftime('%Y-%m-%d %H:%M'),
            help='Limit the list to messages saved after the given time (default %(default)s).',
        )
        parser.add_argument(
            '--stop', '--to', type=str, default=None, 
            help='Limit the list to messages saved after the given time.',
        )
        parser.add_argument(
            '-p', '--pk', action="store_true", default=False,
            help='output only a list of primary keys.',
        )
        selection = parser.add_mutually_exclusive_group()
        selection.add_argument(
            '-a', '--all', action='store_const', dest='state', const='all',
            help='Shows a list of all messages.',
        )
        selection.add_argument(
            '-u', '--unsent', action='store_const', dest='state', const='unsent',
            help='Shows a list of unsent messages',
        )
        selection.add_argument(
            '-s', '--sent', action='store_const', dest='state', const='sent',
            help='Shows a list of sent messages.',
        )


    def handle(self, *args, **options):
        messages = Message.objects.all()
        if options['state'] == 'sent':
            messages = messages.filter(sent__isnull=False)
        elif options['state'] == 'unsent':
            messages = messages.filter(sent__isnull=True)
        else:
            options['state'] = 'all'
        messages = messages.filter(time__gte=options['start'])
        if options['stop']:
            messages = messages.filter(sent__lte=options['stop'])
            selection_str = "%s messages between %s and %s" % (options['state'], options['start'], options['stop'])

        else:
            selection_str = "%s messages since %s" % (options['state'], options['start'])
        self.stdout.write("\nShowimg %s:\n\n" % selection_str)

        if options['pk']:
            self.stdout.write(','.join([ str(pk) for pk in messages.values_list('pk', flat=True)] ))
        else:
            for m in messages:
                def addr(f):
                    return parseaddr(f)[1]
                to = ','.join( a[1] for a in email.utils.getaddresses([m.to]) )
                self.stdout.write('%s  %16s  %16s  %56s  %s -> %s  "%s"\n' %
                    (m.pk, m.time.strftime('%Y-%m-%d %H:%M'), m.sent and m.sent.strftime('%Y-%m-%d %H:%M') or '',
                        m.msgid.strip('<>'), addr(m.frm), to, m.subject.strip()))
            self.stdout.write("\n%s messages (%s)\n" % (messages.count(), selection_str))
