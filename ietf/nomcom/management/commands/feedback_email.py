# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import sys
from textwrap import dedent

from django.core.management import CommandError

from ietf.utils.log import log
from ietf.utils.management.base import EmailOnFailureCommand
from ietf.nomcom.models import NomCom
from ietf.nomcom.utils import create_feedback_email
from ietf.nomcom.fields import EncryptedException

import debug  # pyflakes:ignore


class Command(EmailOnFailureCommand):
    help = ("Receive nomcom email, encrypt and save it.")
    nomcom = None
    msg = None  # incoming message

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--nomcom-year', dest='year', help='NomCom year')
        parser.add_argument('--email-file', dest='email', help='File containing email (default: stdin)')

    def handle(self, *args, **options):
        email = options.get('email', None)
        year = options.get('year', None)
        help_message = 'Usage: feeback_email --nomcom-year <nomcom-year> --email-file <email-file>'

        if not year:
            log("Error: missing nomcom-year")
            raise CommandError("Missing nomcom-year\n\n" + help_message)

        try:
            self.nomcom = NomCom.objects.get(group__acronym__icontains=year,
                                             group__state__slug='active')
        except NomCom.DoesNotExist:
            raise CommandError("NomCom %s does not exist or it isn't active" % year)

        if not email:
            self.msg = io.open(sys.stdin.fileno(), 'rb').read()
        else:
            self.msg = io.open(email, "rb").read()

        try:
            feedback = create_feedback_email(self.nomcom, self.msg)
            log("Received nomcom email from %s" % feedback.author)
        except (EncryptedException, ValueError) as e:
            raise CommandError(e)

    # Configuration for the email to be sent on failure
    failure_email_includes_traceback = False  # error messages might contain pieces of the feedback email
    failure_subject = '{nomcom}: error during feedback email processing'
    failure_message = dedent("""\
        An error occurred in the nomcom feedback_email management command while
        processing feedback for {nomcom}.
        
        {error_summary}
        """)
    @property
    def failure_recipients(self):
        return self.nomcom.chair_emails() if self.nomcom else super().failure_recipients

    def make_failure_message(self, error, **extra):
        failure_message = super().make_failure_message(
            error,
            nomcom=self.nomcom or 'nomcom',
            **extra
        )
        if self.nomcom and self.msg:
            # Attach incoming message if we have it and are sending to the nomcom chair.
            # Do not attach it if we are sending to the admins. Send as a generic
            # mime type because we don't know for sure that it was actually a valid
            # message.
            failure_message.add_attachment(
                self.msg,
                'application', 'octet-stream',  # mime type
                filename='original-message',
            )
        return failure_message
