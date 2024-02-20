# Copyright The IETF Trust 2024, All Rights Reserved

import debug  # pyflakes:ignore

import datetime
import os
import shutil
import subprocess
import tempfile

from collections import namedtuple, Counter
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ietf.doc.models import Document, DocEvent, State
from ietf.utils.text import xslugify


class Command(BaseCommand):
    help = "Performs a one-time import of IESG statements"

    def handle(self, *args, **options):
        if Document.objects.filter(type="statement", group__acronym="iesg").exists():
            self.stdout.write("IESG statement documents already exist - exiting")
            exit(-1)
        tmpdir = tempfile.mkdtemp()
        process = subprocess.Popen(
            ["git", "clone", "https://github.com/kesara/iesg-scraper.git", tmpdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        sub_stdout, sub_stderr = process.communicate()
        if not Path(tmpdir).joinpath("iesg_statements", "2000-08-29-0.md").exists():
            self.stdout.write(
                "Git clone of the iesg-scraper directory did not go as expected"
            )
            self.stdout.write("stdout:", sub_stdout)
            self.stdout.write("stderr:", sub_stderr)
            self.stdout.write(f"Clean up {tmpdir} manually")
            exit(-1)

        for item in self.get_work_items():
            replaced = item.title.endswith(" SUPERSEDED") or item.doc_time.date() == datetime.date(2007,7,30)
            title = item.title
            if title.endswith(" - SUPERSEDED"):
                title = title[: -len(" - SUPERSEDED")]
            name = f"statement-iesg-{xslugify(title)}-{item.doc_time:%Y%m%d}"
            dest_filename = f"{name}-00.md"
            # Create Document
            doc = Document.objects.create(
                name=name,
                type_id="statement",
                title=title,
                group_id=2,  # The IESG group
                rev="00",
                uploaded_filename=dest_filename,
            )
            doc.set_state(
                State.objects.get(
                    type_id="statement",
                    slug="replaced" if replaced else "active",
                )
            )
            e1 = DocEvent.objects.create(
                time=item.doc_time,
                type="published_statement",
                doc=doc,
                rev="00",
                by_id=1,  # (System)
                desc="Statement published (note: The exact time of day is inaccurate - the actual time of day is not known)",
            )
            e2 = DocEvent.objects.create(
                type="added_comment",
                doc=doc,
                rev="00",
                by_id=1,  # (System)
                desc="Statement moved into datatracker from www.ietf.org",
            )
            doc.save_with_history([e1, e2])

            # Put file in place
            source = Path(tmpdir).joinpath("iesg_statements", item.source_filename)
            dest = Path(settings.DOCUMENT_PATH_PATTERN.format(doc=doc)).joinpath(
                dest_filename
            )
            if dest.exists():
                self.stdout.write(
                    f"WARNING: {dest} already exists - not overwriting it."
                )
            else:
                os.makedirs(dest.parent, exist_ok=True)
                shutil.copy(source, dest)

        shutil.rmtree(tmpdir)

    def get_work_items(self):
        Item = namedtuple("Item", "doc_time source_filename title")
        items = []
        dressed_rows = " ".join(
            self.cut_paste_from_www().expandtabs(1).split(" ")
        ).split("\n")
        # Rube-Goldberg-esque dance to deal with conflicting directions of the scrape and
        # what order we want the result to sort to
        dressed_rows.reverse()
        total_times_date_seen = Counter([row.split(" ")[0] for row in dressed_rows])
        count_date_seen_so_far = Counter()
        for row in dressed_rows:
            date_part = row.split(" ")[0]
            title_part = row[len(date_part) + 1 :]
            datetime_args = list(map(int, date_part.replace("-0", "-").split("-")))
            # Use the minutes in timestamps to preserve order of statements
            # on the same day as they currently appear at www.ietf.org
            datetime_args.extend([12, count_date_seen_so_far[date_part]])
            count_date_seen_so_far[date_part] += 1
            doc_time = datetime.datetime(*datetime_args, tzinfo=datetime.timezone.utc)
            items.append(
                Item(
                    doc_time,
                    f"{date_part}-{total_times_date_seen[date_part] - count_date_seen_so_far[date_part]}.md",
                    title_part,
                )
            )
        return items

    def cut_paste_from_www(self):
        return """2023-08-24	Support Documents in IETF Working Groups
2023-08-14	Guidance on In-Person and Online Interim Meetings
2023-05-01	IESG Statement on EtherTypes
2023-03-15	Second Report on the RFC 8989 Experiment
2023-01-27	Guidance on In-Person and Online Interim Meetings - SUPERSEDED
2022-10-31	Statement on Restricting Access to IETF IT Systems
2022-01-21	Handling Ballot Positions
2021-09-01	Report on the RFC 8989 experiment
2021-07-21	IESG Statement on Allocation of Email Addresses in the ietf.org Domain
2021-05-11	IESG Statement on Inclusive Language
2021-05-10	IESG Statement on Internet-Draft Authorship
2021-05-07	IESG Processing of RFC Errata for the IETF Stream
2021-04-16	Last Call Guidance to the Community
2020-07-23	IESG Statement On Oppressive or Exclusionary Language
2020-05-01	Guidance on Face-to-Face and Virtual Interim Meetings - SUPERSEDED
2018-03-16	IETF Meeting Photography Policy
2018-01-11	Guidance on Face-to-Face and Virtual Interim Meetings - SUPERSEDED
2017-02-09	License File for Open Source Repositories
2016-11-13	Support Documents in IETF Working Groups - SUPERSEDED
2016-02-05	Guidance on Face-to-Face and Virtual Interim Meetings - SUPERSEDED
2016-01-11	Guidance on Face-to-Face and Virtual Interim Meetings - SUPERSEDED
2015-08-20	IESG Statement on Maximizing Encrypted Access To IETF Information
2015-06-11	IESG Statement on Internet-Draft Authorship - SUPERSEDED
2014-07-20	IESG Statement on Designating RFCs as Historic
2014-05-07	DISCUSS Criteria in IESG Review
2014-03-02	Writable MIB Module IESG Statement
2013-11-03	IETF Anti-Harassment Policy
2012-10-25	IESG Statement on Ethertypes - SUPERSEDED
2012-10-25	IESG Statement on Removal of an Internet-Draft from the IETF Web Site
2011-10-20	IESG Statement on Designating RFCs as Historic - SUPERSEDED
2011-06-27	IESG Statement on Designating RFCs as Historic - SUPERSEDED
2011-06-13	IESG Statement on IESG Processing of RFC Errata concerning RFC Metadata
2010-10-11	IESG Statement on Document Shepherds
2010-05-24	IESG Statement on the Usage of Assignable Codepoints, Addresses and Names in Specification Examples
2010-05-24	IESG Statement on NomCom Eligibility and Day Passes
2009-09-08	IESG Statement on Copyright
2009-01-20	IESG Statement on Proposed Status for IETF Documents Reserving Resources for Example Purposes
2008-09-02	Guidance on Interim Meetings, Conference Calls and Jabber Sessions - SUPERSEDED
2008-07-30	IESG Processing of RFC Errata for the IETF Stream
2008-04-14	IESG Statement on Spam Control on IETF Mailing Lists
2008-03-03	IESG Statement on Registration Requests for URIs Containing Telephone Numbers
2008-02-27	IESG Statement on RFC3406 and URN Namespaces Registry Review
2008-01-23	Advice for WG Chairs Dealing with Off-Topic Postings
2007-10-04	On Appeals of IESG and Area Director Actions and Decisions
2007-07-05	Experimental Specification of New Congestion Control Algorithms
2007-03-20	Guidance on Area Director Sponsoring of Documents
2007-01-15	Last Call Guidance to the Community - SUPERSEDED
2006-04-19	IESG Statement: Normative and Informative References
2006-02-17	IESG Statement on Disruptive Posting
2006-01-09	Guidance for Spam Control on IETF Mailing Lists - SUPERSEDED
2006-01-05	IESG Statement on AUTH48 State
2005-05-12	Syntax for Format Definitions
2003-02-11	IESG Statement on IDN
2002-11-27	Copyright Statement in MIB and PIB Modules
2002-03-13	Guidance for Spam Control on IETF Mailing Lists - SUPERSEDED
2001-12-21	On Design Teams
2001-10-01	Guidelines for the Use of Formal Languages in IETF Specifications
2001-03-21	Establishment of Temporary Sub-IP Area
2000-12-06	Plans to Organize "Sub-IP" Technologies in the IETF
2000-11-20	A New IETF Work Area
2000-08-29	Guidance on Interim IETF Working Group Meetings and Conference Calls - SUPERSEDED
2000-08-29	IESG Guidance on the Moderation of IETF Working Group Mailing Lists"""
