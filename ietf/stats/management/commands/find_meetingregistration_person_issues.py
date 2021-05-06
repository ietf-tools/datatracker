# Copyright The IETF Trust 2021, All Rights Reserved

import debug # pyflakes:ignore

from django.core.management.base import BaseCommand

from ietf.stats.utils import find_meetingregistration_person_issues

class Command(BaseCommand):
    help = "Find possible Person/Email objects to repair based on MeetingRegistration objects"

    def add_arguments(self, parser):
        parser.add_argument('--meeting',action='append')

    def handle(self, *args, **options):
        meetings = options['meeting'] or None
        summary = find_meetingregistration_person_issues(meetings)

        print(f'{summary.ok_records} records are OK')

        for msg in summary.could_be_fixed:
            print(msg)

        for msg in summary.maybe_address:
            print(msg)

        for msg in summary.different_person:
            print(msg)

        for msg in summary.no_person:
            print(msg)

        for msg in summary.maybe_person:
            print(msg)

        for msg in summary.no_email:
            print(msg)
