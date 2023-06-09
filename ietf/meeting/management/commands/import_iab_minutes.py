# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import json
import os
import shutil
import subprocess
import tempfile

from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand

from ietf.doc.models import Document, DocAlias, DocEvent
from ietf.meeting.models import Meeting, Schedule, Session, SchedulingEvent, SchedTimeSessAssignment, TimeSlot

def nametimes_by_year():
    with Path(__file__).parent.joinpath("data_for_import_iab_minutes").open() as file:
        return json.loads(file.read())
class Command(BaseCommand):

    help = "Performs a one-time import of older IAB minutes, creating Meetings to attach them to"

    def handle(self, *args, **options):

        tmpdir = tempfile.mkdtemp()
        process = subprocess.Popen(["git","clone","https://github.com/kesara/iab-scraper.git",tmpdir],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if not Path(tmpdir).joinpath("iab_minutes","2022-12-14.md").exists():
            print("Git clone of the iab-scraper directory did not go as expected")
            print("stdout:", stdout)
            print("stderr:", stderr)
            print(f"Clean up {tmpdir} manually")
            exit(-1)
        

        ntby = nametimes_by_year()
        for year in ntby:
            counter = 1
            for month, day, ext, start_hour, start_minute, duration in ntby[year]:
                start = datetime.datetime(int(year), month, day, start_hour, start_minute, tzinfo=datetime.timezone.utc)
                meeting_name = f"interim-{year}-iab-{counter:02d}"
                minutes_docname = f"minutes-interim-{year}-iab-{counter:02d}-{start:%Y%m%d}" # Note violating the convention of having the start time...
                minutes_filename = f"{minutes_docname}-00.{ext}"
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
                e = DocEvent.objects.create(
                        type="comment",
                        doc = doc,
                        rev = "00",
                        by_id = 1, # The "(System)" person
                        desc = "Minutes moved into datatracker from iab wordpress website",
                )
                doc.save_with_history([e])
                # Create Meeting - Add a note about noon utc fake meeting times
                meeting = Meeting.objects.create(
                    number=meeting_name,
                    type_id="interim",
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

                # Put file in place
                source = Path(tmpdir).joinpath("iab_minutes",f"{year}-{month:02d}-{day:02d}.{ext}")
                dest = Path(settings.AGENDA_PATH).joinpath(meeting_name, "minutes", minutes_filename)
                if dest.exists():
                    print(f"WARNING: {dest} already exists - not overwriting it.")
                else:
                    os.makedirs(dest.parent, exist_ok=True)
                    shutil.copy(source, dest)

                counter += 1

        shutil.rmtree(tmpdir)
