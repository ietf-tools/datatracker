# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import json
import zoneinfo

from pathlib import PurePath

from django.core.management.base import BaseCommand

from ietf.doc.models import Document, DocAlias
from ietf.meeting.models import Meeting, Schedule, Session, SchedulingEvent, SchedTimeSessAssignment, TimeSlot

def nametimes_by_year():
    with open(PurePath(__file__).parent.joinpath("data_for_import_iab_minutes"),"r") as file:
        return json.loads(file.read())
class Command(BaseCommand):

    help = "Performs a one-time import of older IAB minutes, creating Meetings to attach them to"

    def handle(self, *args, **options):

        ntby = nametimes_by_year()
        for year in ntby:
            counter = 1
            for month, day, ext, start_hour, start_minute, duration in ntby[year]:
                start = datetime.datetime(year, month, day, start_hour, start_minute, tzinfo=datetime.timezone.utc)
                meeting_name = f"interim-{year}-iab-{counter:02d}"
                minutes_docname = f"minutes-interim-{year}-iab-{counter:02d}-{start:%Y%m%d}" # Note violating the convention of having the start time...
                minutes_filename = f"{minutes_docname}-00.{ext}"  # I plan to use a management command to put the files in place after the migration is run.
                # Create Document
                doc = Document.objects.create(
                    name = minutes_docname,
                    type_id = "minutes",
                    title = f"Minutes {meeting_name} {start:%Y-%m-%d}", # Another violation of convention,
                    group_id = 7, # The IAB group
                    rev = "00",
                    uploaded_filename = minutes_filename,
                )
                DocAlias.objects.create(name=doc.name).docs.add(doc)
                # Create Meeting - Add a note about noon utc fake meeting times
                meeting = Meeting.objects.create(
                    number=meeting_name,
                    type_id='interim',
                    date=start.date(),
                    days=1,
                    time_zone=start.tzname())
                schedule = Schedule.objects.create(
                    meeting=meeting,
                    owner_id=1, # The "(System)" person
                    visible=True,
                    public=True)
                meeting.schedule = schedule
                if start.timetz() == datetime.time(12, 0, 0, tzinfo=datetime.timezone.utc):
                    meeting.agenda_note = "The actual time of this meeting was not recorded and was likely not at noon UTC"
                meeting.save()
                # Create Session
                session = Session.objects.create(
                    meeting = meeting,
                    group_id = 7, # The IAB group
                    type_id = "regular",
                    purpose_id = "regular",
                )
                # Schedule the Session
                SchedulingEvent.objects.create(
                    session=session,
                    status_id="sched",
                    by_id=1, # (System)
                )
                timeslot = TimeSlot.objects.create(
                    meeting=meeting,
                    type_id = "regular",
                    time = start,
                    duration = datetime.timedelta(seconds=duration),
                )
                SchedTimeSessAssignment.objects.create(
                    timeslot=timeslot,
                    session=session,
                    schedule=schedule
                )
                # Add Document to Session
                session.sessionpresentation_set.create(document=doc,rev=doc.rev)

                counter += 1
