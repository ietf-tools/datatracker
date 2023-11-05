# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import os
import shutil
import subprocess
import tempfile

from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from ietf.doc.models import Document, DocEvent
from ietf.meeting.models import Meeting, Session


def agendas_to_import():
    return [
        "2018-09-05.md",
        "2018-09-12.md",
        "2018-09-26.md",
        "2018-10-03.md",
        "2018-10-10.md",
        "2018-10-24.md",
        "2018-11-04.md",
        "2018-11-05.md",
        "2018-11-08.md",
        "2018-11-21.md",
        "2018-11-28.md",
        "2018-12-05.md",
        "2018-12-19.md",
        "2019-01-09.md",
        "2019-01-16.md",
        "2019-01-23.md",
        "2019-02-06.md",
        "2019-02-13.md",
        "2019-02-27.md",
        "2019-03-06.md",
        "2019-03-13.md",
        "2019-03-24.md",
        "2019-03-25.md",
        "2019-03-28.md",
        "2019-04-10.md",
        "2019-04-17.md",
        "2019-05-01.md",
        "2019-05-08.md",
        "2019-05-29.md",
        "2019-06-12.md",
        "2019-06-26.md",
        "2019-07-10.md",
        "2019-07-21.md",
        "2019-07-25.md",
        "2019-08-07.md",
        "2019-08-21.md",
        "2019-08-28.md",
        "2019-09-04.md",
        "2019-09-18.md",
        "2019-10-02.md",
        "2019-10-16.md",
        "2019-10-30.md",
        "2019-11-17.md",
        "2019-11-18.md",
        "2019-11-21.md",
        "2019-12-04.md",
        "2019-12-11.md",
        "2019-12-18.md",
        "2020-01-08.md",
        "2020-01-15.md",
        "2020-01-22.md",
        "2020-02-05.md",
        "2020-02-12.md",
        "2020-02-19.md",
        "2020-03-04.md",
        "2020-03-11.md",
        "2020-03-18.md",
        "2020-04-01.md",
        "2020-04-08.md",
        "2020-04-15.md",
        "2020-04-29.md",
        "2020-05-13.md",
        "2020-05-20.md",
        "2020-05-27.md",
        "2020-06-10.md",
        "2020-06-17.md",
        "2020-07-01.md",
        "2020-07-15.md",
        "2020-08-12.md",
        "2020-08-26.md",
        "2020-09-09.md",
        "2020-09-23.md",
        "2020-10-07.md",
        "2020-10-14.md",
        "2020-10-21.md",
        "2020-11-04.md",
        "2020-12-02.md",
        "2020-12-16.md",
        "2021-01-06.md",
        "2021-01-13.md",
        "2021-01-20.md",
        "2021-01-27.md",
        "2021-02-03.md",
        "2021-02-10.md",
        "2021-02-17.md",
        "2021-02-24.md",
        "2021-03-03.md",
        "2021-03-24.md",
        "2021-03-31.md",
        "2021-04-07.md",
        "2021-04-14.md",
        "2021-04-21.md",
        "2021-05-05.md",
        "2021-05-12.md",
        "2021-05-19.md",
        "2021-05-26.md",
        "2021-06-02.md",
        "2021-06-16.md",
        "2021-06-23.md",
        "2021-06-30.md",
        "2021-07-14.md",
        "2021-07-21.md",
        "2021-08-11.md",
        "2021-08-25.md",
        "2021-09-01.md",
        "2021-09-08.md",
        "2021-09-22.md",
        "2021-10-06.md",
        "2021-10-20.md",
        "2021-10-27.md",
        "2021-11-17.md",
        "2021-12-01.md",
        "2021-12-08.md",
        "2021-12-15.md",
        "2022-01-12.md",
        "2022-01-19.md",
        "2022-02-02.md",
        "2022-02-16.md",
        "2022-02-23.md",
        "2022-03-02.md",
        "2022-03-09.md",
        "2022-03-20.md",
        "2022-04-06.md",
        "2022-04-13.md",
        "2022-04-20.md",
        "2022-04-27.md",
        "2022-05-04.md",
        "2022-05-11.md",
        "2022-06-01.md",
        "2022-06-15.md",
        "2022-06-22.md",
        "2022-06-29.md",
        "2022-07-06.md",
        "2022-07-24.md",
        "2022-07-26.md",
        "2022-08-10.md",
        "2022-08-24.md",
        "2022-09-07.md",
        "2022-09-21.md",
        "2022-09-28.md",
        "2022-10-05.md",
        "2022-10-12.md",
        "2022-10-26.md",
        "2022-11-06.md",
        "2022-11-08.md",
        "2022-11-10.md",
        "2022-11-23.md",
        "2022-12-07.md",
        "2022-12-14.md",
    ]


class Command(BaseCommand):
    help = "Performs a one-time import of older IAB agendas"

    def handle(self, *args, **options):
        if Document.objects.filter(name="agenda-interim-2018-iab-26-20180905").exists():
            print("Command has already been run - exiting")
            exit(0)

        tmpdir = tempfile.mkdtemp()
        process = subprocess.Popen(
            ["git", "clone", "https://github.com/kesara/iab-scraper.git", tmpdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
        if not Path(tmpdir).joinpath("iab_agendas", "2018-09-05.md").exists():
            print("Git clone of the iab-scraper directory did not go as expected")
            print("stdout:", stdout)
            print("stderr:", stderr)
            print(f"Clean up {tmpdir} manually")
            exit(-1)

        agendas = agendas_to_import()
        for agenda in agendas:
            [year, month, day] = [int(part) for part in agenda[:10].split("-")]
            agenda_date = datetime.date(year, month, day)
            meeting = Meeting.objects.get(
                date=agenda_date, type_id="interim", session__group__acronym="iab"
            )
            counter = int(meeting.number.split("-")[3])
            agenda_docname = (
                f"agenda-interim-{year}-iab-{counter:02d}-{agenda_date:%Y%m%d}"
            )
            agenda_filename = f"{agenda_docname}-00.md"
            # Create Document
            doc = Document.objects.create(
                name=agenda_docname,
                type_id="agenda",
                title=f"Agenda {meeting.number} {agenda_date:%Y-%m-%d}",
                group_id=7,  # The IAB group
                rev="00",
                uploaded_filename=agenda_filename,
            )
            e = DocEvent.objects.create(
                type="comment",
                doc=doc,
                rev="00",
                by_id=1,  # The "(System)" person
                desc="Agenda moved into datatracker from iab wordpress website",
            )
            doc.save_with_history([e])

            session = Session.objects.get(meeting=meeting)
            # Add Document to Session
            session.sessionpresentation_set.create(document=doc, rev=doc.rev)

            # Put file in place
            source = Path(tmpdir).joinpath("iab_agendas", agenda)
            dest = Path(settings.AGENDA_PATH).joinpath(
                meeting.number, "agenda", agenda_filename
            )
            if dest.exists():
                print(f"WARNING: {dest} already exists - not overwriting it.")
            else:
                os.makedirs(dest.parent, exist_ok=True)
                shutil.copy(source, dest)

        shutil.rmtree(tmpdir)
