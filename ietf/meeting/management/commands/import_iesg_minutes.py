# Copyright The IETF Trust 2023, All Rights Reserved

from collections import namedtuple
import datetime
import os
import re
import shutil

from django.conf import settings
from django.core.management import BaseCommand

from pathlib import Path
from zoneinfo import ZoneInfo
from ietf.doc.models import DocEvent, Document

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
        dt = bare_datetime.replace(hour=7).replace(
            tzinfo=ZoneInfo("America/Los_Angeles")
        )
    elif bare_datetime.year == 2015:
        if bare_datetime.month >= 4:
            dt = bare_datetime.replace(hour=7).replace(
                tzinfo=ZoneInfo("America/Los_Angeles")
            )
        else:
            dt = bare_datetime.replace(hour=11, minute=30).replace(
                tzinfo=ZoneInfo("America/New_York")
            )
    elif bare_datetime.year > 1993:
        dt = bare_datetime.replace(hour=11, minute=30).replace(
            tzinfo=ZoneInfo("America/New_York")
        )
    elif bare_datetime.year == 1993:
        if bare_datetime.month >= 2:
            dt = bare_datetime.replace(hour=11, minute=30).replace(
                tzinfo=ZoneInfo("America/New_York")
            )
        else:
            dt = bare_datetime.replace(hour=12).replace(
                tzinfo=ZoneInfo("America/New_York")
            )
    else:
        dt = bare_datetime.replace(hour=12).replace(tzinfo=ZoneInfo("America/New_York"))

    return dt.astimezone(datetime.timezone.utc)


def build_bof_coord_data():
    CoordTuple = namedtuple("CoordTuple", "meeting_number source_name")

    def utc_from_la_time(time):
        return time.replace(tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(
            datetime.timezone.utc
        )

    data = dict()
    data[utc_from_la_time(datetime.datetime(2016, 6, 10, 7, 0))] = CoordTuple(
        96, "2015/bof-minutes-ietf-96.txt"
    )
    data[utc_from_la_time(datetime.datetime(2016, 10, 6, 7, 0))] = CoordTuple(
        97, "2016/BoF-Minutes-2016-10-06.txt"
    )
    data[utc_from_la_time(datetime.datetime(2017, 2, 15, 8, 0))] = CoordTuple(
        98, "2017/bof-minutes-ietf-98.txt"
    )
    data[utc_from_la_time(datetime.datetime(2017, 6, 7, 8, 0))] = CoordTuple(
        99, "2017/bof-minutes-ietf-99.txt"
    )
    data[utc_from_la_time(datetime.datetime(2017, 10, 5, 7, 0))] = CoordTuple(
        100, "2017/bof-minutes-ietf-100.txt"
    )
    data[utc_from_la_time(datetime.datetime(2018, 2, 5, 11, 0))] = CoordTuple(
        101, "2018/bof-minutes-ietf-101.txt"
    )
    data[utc_from_la_time(datetime.datetime(2018, 6, 5, 8, 0))] = CoordTuple(
        102, "2018/bof-minutes-ietf-102.txt"
    )
    data[utc_from_la_time(datetime.datetime(2018, 9, 26, 7, 0))] = CoordTuple(
        103, "2018/bof-minutes-ietf-103.txt"
    )
    data[utc_from_la_time(datetime.datetime(2019, 2, 15, 9, 0))] = CoordTuple(
        104, "2019/bof-minutes-ietf-104.txt"
    )
    data[utc_from_la_time(datetime.datetime(2019, 6, 11, 7, 30))] = CoordTuple(
        105, "2019/bof-minutes-ietf-105.txt"
    )
    data[utc_from_la_time(datetime.datetime(2019, 10, 9, 6, 30))] = CoordTuple(
        106, "2019/bof-minutes-ietf-106.txt"
    )
    data[utc_from_la_time(datetime.datetime(2020, 2, 13, 8, 0))] = CoordTuple(
        107, "2020/bof-minutes-ietf-107.txt"
    )
    data[utc_from_la_time(datetime.datetime(2020, 6, 15, 8, 0))] = CoordTuple(
        108, "2020/bof-minutes-ietf-108.txt"
    )
    data[utc_from_la_time(datetime.datetime(2020, 10, 9, 7, 0))] = CoordTuple(
        109, "2020/bof-minutes-ietf-109.txt"
    )
    data[utc_from_la_time(datetime.datetime(2021, 1, 14, 13, 30))] = CoordTuple(
        110, "2021/bof-minutes-ietf-110.txt"
    )
    data[utc_from_la_time(datetime.datetime(2021, 6, 1, 8, 0))] = CoordTuple(
        111, "2021/bof-minutes-ietf-111.txt"
    )
    data[utc_from_la_time(datetime.datetime(2021, 9, 15, 9, 0))] = CoordTuple(
        112, "2021/bof-minutes-ietf-112.txt"
    )
    data[utc_from_la_time(datetime.datetime(2022, 1, 28, 7, 0))] = CoordTuple(
        113, "2022/bof-minutes-ietf-113.txt"
    )
    data[utc_from_la_time(datetime.datetime(2022, 6, 2, 10, 0))] = CoordTuple(
        114, "2022/bof-minutes-ietf-114.txt"
    )
    data[utc_from_la_time(datetime.datetime(2022, 9, 13, 9, 0))] = CoordTuple(
        115, "2022/bof-minutes-ietf-115.txt"
    )
    data[utc_from_la_time(datetime.datetime(2023, 2, 1, 9, 0))] = CoordTuple(
        116, "2023/bof-minutes-ietf-116.txt"
    )
    data[utc_from_la_time(datetime.datetime(2023, 6, 1, 7, 0))] = CoordTuple(
        117, "2023/bof-minutes-ietf-117.txt"
    )
    data[utc_from_la_time(datetime.datetime(2023, 9, 15, 8, 0))] = CoordTuple(
        118, "2023/bof-minutes-ietf-118.txt"
    )
    return data


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
        meeting_times = set()
        for file_prefix in ["minutes", "narrative"]:
            paths = list(minutes_dir.glob(f"[12][09][0129][0-9]/{file_prefix}*.txt"))
            for path in paths:
                s = date_re.search(path.name)
                if s:
                    meeting_times.add(
                        add_time_of_day(
                            datetime.datetime.strptime(s.group(), "%Y-%m-%d")
                        )
                    )
        bof_coord_data = build_bof_coord_data()
        bof_times = set(bof_coord_data.keys())
        assert len(bof_times.intersection(meeting_times)) == 0
        meeting_times.update(bof_times)
        year_seen = None
        for dt in sorted(meeting_times):
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
                name=f"IETF {bof_coord_data[dt].meeting_number} BOF Coordination Call"
                if dt in bof_times
                else "Formal Telechat",
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

            if dt in bof_times:
                source = minutes_dir / bof_coord_data[dt].source_name
                if source.exists():
                    doc_name = (
                        f"minutes-interim-{dt.year}-iesg-{counter:02d}-{dt:%Y%m%d%H%M}"
                    )
                    doc_filename = f"{doc_name}-00.txt"
                    doc = Document.objects.create(
                        name=doc_name,
                        type_id="minutes",
                        title=f"Minutes IETF {bof_coord_data[dt].meeting_number} BOF coordination {meeting_name} {dt:%Y-%m-%d %H:%M}",
                        group_id=2,  # the IESG group
                        rev="00",
                        uploaded_filename=doc_filename,
                    )
                    e = DocEvent.objects.create(
                        type="comment",
                        doc=doc,
                        rev="00",
                        by_id=1,  # "(System)"
                        desc="Minutes moved into datatracker",
                    )
                    doc.save_with_history([e])
                    session.presentations.create(document=doc, rev=doc.rev)
                    dest = (
                        Path(settings.AGENDA_PATH)
                        / meeting_name
                        / "minutes"
                        / doc_filename
                    )
                    if dest.exists():
                        self.stdout.write(
                            f"WARNING: {dest} already exists - not overwriting it."
                        )
                    else:
                        os.makedirs(dest.parent, exist_ok=True)
                        shutil.copy(source, dest)
            else:
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
                        doc_name = f"{prefix}-interim-{dt.year}-iesg-{counter:02d}-{dt:%Y%m%d%H%M}"
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
                        e = DocEvent.objects.create(
                            type="comment",
                            doc=doc,
                            rev="00",
                            by_id=1,  # "(System)"
                            desc=f"{verbose_type} moved into datatracker",
                        )
                        doc.save_with_history([e])
                        session.presentations.create(document=doc, rev=doc.rev)
                        dest = (
                            Path(settings.AGENDA_PATH)
                            / meeting_name
                            / type_id
                            / doc_filename
                        )
                        if dest.exists():
                            self.stdout.write(
                                f"WARNING: {dest} already exists - not overwriting it."
                            )
                        else:
                            os.makedirs(dest.parent, exist_ok=True)
                            shutil.copy(source, dest)

            counter += 1
