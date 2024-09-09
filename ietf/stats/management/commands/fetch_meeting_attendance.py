# Copyright The IETF Trust 2017-2019, All Rights Reserved
# Copyright 2016 IETF Trust

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

import debug                            # pyflakes:ignore

from ietf.meeting.models import Meeting
from ietf.stats.utils import fetch_attendance_from_meetings
from ietf.utils import log


class Command(BaseCommand):
    help = "Fetch meeting attendee figures from ietf.org/registration/attendees."

    def add_arguments(self, parser):
        parser.add_argument("--meeting", help="meeting to fetch data for")
        parser.add_argument("--all", action="store_true", help="fetch data for all meetings")
        parser.add_argument("--latest", type=int, help="fetch data for latest N meetings")

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']

        meetings = Meeting.objects.none()
        if options['meeting']:
            meetings = Meeting.objects.filter(number=options['meeting'], type="ietf")
        elif options['all']:
            meetings = Meeting.objects.filter(type="ietf").order_by("date")
        elif options['latest']:
            meetings = Meeting.objects.filter(type="ietf", date__lte=timezone.now()).order_by("-date")[:options['latest']]
        else:
            raise CommandError("Please use one of --meeting, --all or --latest")

        for meeting, stats in zip(meetings, fetch_attendance_from_meetings(meetings)):
            msg = "Fetched data for meeting {:>3}: {:4d} processed, {:4d} added, {:4d} in table".format(
                meeting.number, stats.processed, stats.added, stats.total
            )
            if self.stdout.isatty():
                self.stdout.write(msg+'\n') # make debugging a bit easier
            else:
                log.log(msg)
