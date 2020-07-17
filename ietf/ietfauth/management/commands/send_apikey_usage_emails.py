# Copyright The IETF Trust 2017-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import datetime

from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand

import debug                            # pyflakes:ignore

from ietf.person.models import PersonalApiKey, PersonApiKeyEvent
from ietf.utils.mail import send_mail


class Command(BaseCommand):
    """
    Send out emails to all persons who have personal API keys about usage.

    Usage is show over the given period, where the default period is 7 days.
    """

    help = dedent(__doc__).strip()
            
    def add_arguments(self, parser):
        parser.add_argument('-d', '--days', dest='days', type=int, default=7,
            help='The period over which to show usage.')

    def handle(self, *filenames, **options):
        """
        """

        self.verbosity = int(options.get('verbosity'))
        days = options.get('days')

        keys = PersonalApiKey.objects.filter(valid=True)
        for key in keys:
            earliest = datetime.datetime.now() - datetime.timedelta(days=days)
            events = PersonApiKeyEvent.objects.filter(key=key, time__gt=earliest)
            count = events.count()
            events = events[:32]
            if count:
                key_name = key.hash()[:8]
                subject = "API key usage for key '%s' for the last %s days" %(key_name, days)
                to = key.person.email_address()
                frm = settings.DEFAULT_FROM_EMAIL
                send_mail(None, to, frm, subject, 'utils/apikey_usage_report.txt',  {'person':key.person,
                    'days':days, 'key':key, 'key_name':key_name, 'count':count, 'events':events, } )
                
