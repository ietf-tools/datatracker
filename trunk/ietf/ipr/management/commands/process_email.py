# Copyright The IETF Trust 2014-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import io
import sys

from django.core.management.base import BaseCommand, CommandError

from ietf.ipr.mail import process_response_email

import debug                            # pyflakes:ignore

class Command(BaseCommand):
    help = ("Process incoming email responses to ipr mail")

    def add_arguments(self, parser):
        parser.add_argument('--email-file', dest='email', help='File containing email (default: stdin)')

    def handle(self, *args, **options):
        email = options.get('email', None)
        msg = None

        if not email:
            msg = sys.stdin.read()
        else:
            msg = io.open(email, "r").read()

        try:
            process_response_email(msg)
        except ValueError as e:
            raise CommandError(e)
