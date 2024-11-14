# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import sys
from textwrap import dedent

from django.core.management import CommandError

from ietf.utils.management.base import EmailOnFailureCommand
from ietf.ipr.mail import process_response_email, UndeliverableIprResponseError

import debug                            # pyflakes:ignore

class Command(EmailOnFailureCommand):
    help = ("Process incoming email responses to ipr mail")
    msg_bytes = None

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--email-file', dest='email', help='File containing email (default: stdin)')

    def handle(self, *args, **options):
        email = options.get('email', None)
        if email:
            binary_input = io.open(email, 'rb')
            self.msg_bytes = binary_input.read()
            binary_input.close()
        else:
            self.msg_bytes = sys.stdin.buffer.read()
        try:
            process_response_email(self.msg_bytes)
        except (ValueError, UndeliverableIprResponseError) as e:
            raise CommandError(e)

    failure_subject = 'Error during ipr email processing'
    failure_message = dedent("""\
        An error occurred in the ipr process_email management command.

        {error_summary}
        """)
    def make_failure_message(self, error, **extra):
        msg = super().make_failure_message(error, **extra)
        if self.msg_bytes is not None:
            msg.add_attachment(
                self.msg_bytes,
                'application', 'octet-stream',  # mime type
                filename='original-message',
            )
        return msg
