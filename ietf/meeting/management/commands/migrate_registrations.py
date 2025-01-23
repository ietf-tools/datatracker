# Copyright The IETF Trust 2025, All Rights Reserved
# -*- coding: utf-8 -*-

from django.core.management.base import BaseCommand
from ietf.meeting.utils import migrate_registrations

'''
This command migrates ietf.stats.MeetingRegistration records to
ietf.meeting.Registration records. 
'''

class Command(BaseCommand):
    help = "Migrate stats.MeetingRegistration to meeting.Registration"

    def add_arguments(self, parser):
        parser.add_argument(
            '--initial', action='store_true', help='Migrate all records. Otherwise only current meetings.'
        )

    def handle(self, **options):
        """Migrate MeetingRegistration to Registration."""
        migrate_registrations(initial=options['initial'])
