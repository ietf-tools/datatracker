# Copyright The IETF Trust 2020, All Rights Reserved
# -*- coding: utf-8 -*-


import email
import smtplib

from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.message.models import Message
from ietf.utils.mail import send_mail_message

class Command(BaseCommand):
    help = """

    Send (or re-send) messages saved as Message objects as outgoing emails.  To
    show existing Message objects, use the show_messages management command.
    Messages to send can be indicateb by date ranges, a list of primary keys, or
    a list of Message-IDs.  Unless the --resend switch is given, the inclusion
    of already sent messages in the date range or message lists will result in
    an error exit, in order to prevent inadvertent re-sending of message.
    Alternatively, the --unsent switch can be used to send only messages marked
    as not already sent from a date range or message list.
    
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--pks', dest='primary_keys',
            help="Send the messages with the given primary keys. Accepts a comma-separated list of keys.",
        )
        parser.add_argument(
            '--resend', action="store_true", default=False,
            help="Re-send messages (ignoring that they are marked as already sent)."
        )
        parser.add_argument(
            '-t', '--start', '--from', type=str, default=None,
            help='Limit the list to messages saved after the given time (default %(default)s).',
        )
        parser.add_argument(
            '--stop', '--to', type=str, default=None, 
            help='Limit the list to messages saved after the given time.',
        )
        parser.add_argument(
            '--unsent', action="store_true", default=False,
            help="Send only the unsent messages from the PKs or date range given",
        )

    def handle(self, *args, **options):
        start = options['start']
        stop  = options['stop']
        pks   = options['primary_keys']
        resend= options['resend']
        unsent= options['unsent']

        if pks:
            primary_keys = [pk.strip() for pk in pks.split(',')]
        else:
            primary_keys = []

        messages = Message.objects.all()
        if primary_keys:
            messages = messages.filter(pk__in=primary_keys)
        if start:
            messages = messages.filter(time__gte=start)
        if stop:
            messages = messages.filter(sent__lte=stop)
        sent = messages.filter(sent__isnull=False)
        if sent.exists() and not resend and not unsent:
            self.stderr.write("Error: Asked to send one or more already sent messages, and --resend not given")
            for m in sent:
                to = ','.join( a[1] for a in email.utils.getaddresses([m.to]) )
                self.stderr.write('  sent %s: %s  %s -> %s  "%s"' % (m.sent.strftime('%Y-%m-%d %H:%M'), m.pk, m.frm, to, m.subject.strip()))
        else:
            if unsent:
                messages = messages.filter(sent__isnull=True)
            for m in messages:
                to = ','.join( a[1] for a in email.utils.getaddresses([m.to]) )
                try:
                    send_mail_message(None, m)
                    self.stdout.write('%s  %s -> %s  "%s"' % (m.pk, m.frm, to, m.subject.strip()))
                except smtplib.SMTPException as e:
                    self.stdout.write('Failure %s:  %s  %s -> %s  "%s"' % (e, m.pk, m.frm, to, m.subject.strip()))
