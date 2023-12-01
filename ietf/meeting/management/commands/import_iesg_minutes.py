# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import os
import re
import shutil

from django.conf import settings
from django.core.management import BaseCommand

from pathlib import Path
from zoneinfo import ZoneInfo
from ietf.doc.models import DocAlias, DocEvent, Document

from ietf.meeting.models import (
    Meeting,
    SchedTimeSessAssignment,
    Schedule,
    SchedulingEvent,
    Session,
    TimeSlot,
)
from ietf.name.models import DocTypeName


def add_time_of_day(bare_datetime):
    """Add a time for the iesg meeting based on a date and make it tzaware

    From the secretariat - the telechats happened at these times:
    2015-04-09 to present: 0700 PT America/Los Angeles
    1993-02-01 to 2015-03-12: 1130 ET America/New York
    1991-07-30 to 1993-01-25: 1200 ET America/New York
    """
    dt = None
    if bare_datetime.year > 2015:
        dt = bare_datetime.replace(hour=7).astimezone(ZoneInfo("America/Los_Angeles"))
    elif bare_datetime.year == 2015:
        if bare_datetime.month >= 4:
            dt = bare_datetime.replace(hour=7).astimezone(
                ZoneInfo("America/Los_Angeles")
            )
        else:
            dt = bare_datetime.replace(hour=11, minute=30).astimezone(
                ZoneInfo("America/New_York")
            )
    elif bare_datetime.year > 1993:
        dt = bare_datetime.replace(hour=11, minute=30).astimezone(
            ZoneInfo("America/New_York")
        )
    elif bare_datetime.year == 1993:
        if bare_datetime.month >= 2:
            dt = bare_datetime.replace(hour=11, minute=30).astimezone(
                ZoneInfo("America/New_York")
            )
        else:
            dt = bare_datetime.replace(hour=12).astimezone(ZoneInfo("America/New_York"))
    else:
        dt = bare_datetime.replace(hour=12).astimezone(ZoneInfo("America/New_York"))

    return dt.astimezone(datetime.timezone.utc)


class Command(BaseCommand):
    help = "Performs a one-time import of IESG minutes, creating Meetings to attach them to"

    def handle(self, *args, **options):
        old_minutes_root = (
            "/a/www/www6/iesg/minutes"
            if settings.SERVER_MODE == "production"
            else "/assets/www6/iesg/minutes"
        )
        minutes_dir = Path(old_minutes_root)
        date_re = re.compile(r"\d{4}-\d{2}-\d{2}")
        datetimes = set()
        for file_prefix in ["minutes", "narrative"]:
            paths = list(minutes_dir.glob(f"[12][09][0129][0-9]/{file_prefix}*.txt"))
            for path in paths:
                s = date_re.search(path.name)
                if s:
                    datetimes.add(
                        add_time_of_day(
                            datetime.datetime.strptime(s.group(), "%Y-%m-%d")
                        )
                    )
        year_seen = None
        for dt in sorted(datetimes):
            if dt.year != year_seen:
                counter = 1
                year_seen = dt.year
            meeting_name = f"interim-{dt.year}-iesg-{counter:02d}"
            meeting = Meeting.objects.create(
                number=meeting_name,
                type_id="interim",
                date=dt.date(),
                days=1,
                time_zone=dt.tzname(),
            )
            schedule = Schedule.objects.create(
                meeting=meeting,
                owner_id=1,  # the "(System)" person
                visible=True,
                public=True,
            )
            meeting.schedule = schedule
            meeting.save()
            session = Session.objects.create(
                meeting=meeting,
                group_id=2,  # The IESG group
                type_id="regular",
                purpose_id="regular",
                name="Formal Telechat",
            )
            SchedulingEvent.objects.create(
                session=session,
                status_id="sched",
                by_id=1,  # (System)
            )
            timeslot = TimeSlot.objects.create(
                meeting=meeting,
                type_id="regular",
                time=dt,
                duration=datetime.timedelta(seconds=2 * 60 * 60),
            )
            SchedTimeSessAssignment.objects.create(
                timeslot=timeslot, session=session, schedule=schedule
            )

            for type_id in ["minutes", "narrativeminutes"]:
                source_file_prefix = (
                    "minutes" if type_id == "minutes" else "narrative-minutes"
                )
                source = (
                    minutes_dir
                    / f"{dt.year}"
                    / f"{source_file_prefix}-{dt:%Y-%m-%d}.txt"
                )
                if source.exists():
                    prefix = DocTypeName.objects.get(slug=type_id).prefix
                    doc_name = f"{prefix}-interim-{dt.year}-iesg-{counter:02d}-{dt:%Y%m%d%H%M}"  # Unlike iab minutes, follow the usual convention
                    doc_filename = f"{doc_name}-00.txt"
                    verbose_type = (
                        "Minutes" if type_id == "minutes" else "Narrative Minutes"
                    )
                    doc = Document.objects.create(
                        name=doc_name,
                        type_id=type_id,
                        title=f"{verbose_type} {meeting_name} {dt:%Y-%m-%d %H:%M}",
                        group_id=2,  # the IESG group
                        rev="00",
                        uploaded_filename=doc_filename,
                    )
                    DocAlias.objects.create(name=doc_name).docs.add(
                        doc
                    )  # Cry for the merge pain
                    e = DocEvent.objects.create(
                        type="comment",
                        doc=doc,
                        rev="00",
                        by_id=1,  # "(System)"
                        desc=f"{verbose_type} moved into datatracker",
                    )
                    doc.save_with_history([e])
                    session.sessionpresentation_set.create(document=doc, rev=doc.rev)
                    dest = (
                        Path(settings.AGENDA_PATH)
                        / meeting_name
                        / type_id
                        / doc_filename
                    )
                    if dest.exists():
                        print(f"WARNING: {dest} already exists - not overwriting it.")
                    else:
                        os.makedirs(dest.parent, exist_ok=True)
                        shutil.copy(source, dest)

            counter += 1

        # Deal with the one BoF- document
        # import the rest of the bof- documents
