# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import sys

from django.core.management.base import BaseCommand, CommandError

from ietf.utils.log import log
from ietf.nomcom.models import NomCom
from ietf.nomcom.utils import create_feedback_email
from ietf.nomcom.fields import EncryptedException

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    help = ("Receive nomcom email, encrypt and save it.")

    def add_arguments(self, parser):
         parser.add_argument('--nomcom-year', dest='year', help='NomCom year')
         parser.add_argument('--email-file', dest='email', help='File containing email (default: stdin)')

    def handle(self, *args, **options):
        email = options.get('email', None)
        year = options.get('year', None)
        msg = None
        nomcom = None
        help_message = 'Usage: feeback_email --nomcom-year <nomcom-year> --email-file <email-file>'

        if not year:
            log("Error: missing nomcom-year")
            raise CommandError("Missing nomcom-year\n\n"+help_message)

        if not email:
            msg = io.open(sys.stdin.fileno(), 'rb').read()
        else:
            msg = io.open(email, "rb").read()

        try:
            nomcom = NomCom.objects.get(group__acronym__icontains=year,
                                        group__state__slug='active')
        except NomCom.DoesNotExist:
            raise CommandError("NomCom %s does not exist or it isn't active" % year)

        try:
            feedback = create_feedback_email(nomcom, msg)
            log("Received nomcom email from %s" % feedback.author)
        except (EncryptedException, ValueError) as e:
            raise CommandError(e)
