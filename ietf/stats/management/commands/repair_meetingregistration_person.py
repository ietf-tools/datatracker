# Copyright The IETF Trust 2021, All Rights Reserved

import debug # pyflakes:ignore

from django.core.management.base import BaseCommand

from ietf.stats.utils import repair_meetingregistration_person

class Command(BaseCommand):
    help = "Repair MeetingRegistration objects that have no person but an email matching a person"

    def add_arguments(self, parser):
        parser.add_argument('--meeting',action='append')

    def handle(self, *args, **options):
        meetings = options['meeting'] or None
        repaired = repair_meetingregistration_person(meetings)
        print(f'Repaired {repaired} MeetingRegistration objects')