# Copyright The IETF Trust 2017-2019, All Rights Reserved
# Copyright 2016 IETF Trust

import datetime
import syslog

from django.core.management.base import BaseCommand, CommandError

import debug                            # pyflakes:ignore

from ietf.meeting.models import Meeting
from ietf.stats.utils import get_meeting_registration_data

logtag = __name__.split('.')[-1]
logname = "user.log"
syslog.openlog(str(logtag), syslog.LOG_PID, syslog.LOG_USER)

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
            meetings = Meeting.objects.filter(type="ietf", date__lte=datetime.datetime.today()).order_by("-date")[:options['latest']]
        else:
            raise CommandError("Please use one of --meeting, --all or --latest")

        for meeting in meetings:
            added, processed, total = get_meeting_registration_data(meeting)
            msg = "Fetched data for meeting %3s: %4d processed, %4d added, %4d in table" % (meeting.number, processed, added, total)
            if self.stdout.isatty():
                self.stdout.write(msg+'\n') # make debugging a bit easier
            else:
                syslog.syslog(msg)
        
