# Copyright The IETF Trust 2023, All Rights Reserved

import debug  # pyflakes: ignore

import datetime
import shutil
import subprocess
import tempfile

from pathlib import Path

from django.core.management.base import BaseCommand

from ietf.group.models import Appeal, AppealArtifact

from ietf.name.models import AppealArtifactTypeName


PDF_FILES = [
    "2006-01-04-appeal.pdf",
    "2006-08-24-appeal.pdf",
    "2006-09-11-appeal.pdf",
    "2008-11-29-appeal.pdf",
    "2010-06-07-appeal.pdf",
    "2010-06-07-response.pdf",
    "2013-07-08-appeal.pdf",
    "2015-06-22-appeal.pdf",
    "2019-01-31-appeal.pdf",
    "2019-01-31-response.pdf",
]

NAME_PART_MAP = {
    "appeal": "appeal",
    "response": "response",
    "appeal_with_response": "response",
    "reply_to_response": "reply",
}


def bits_name(date, part):
    part_type = part["type"]
    name_fragment = NAME_PART_MAP[part_type]
    prefix = f"{date:%Y-%m-%d}-{name_fragment}"
    if f"{prefix}.pdf" in PDF_FILES:
        ext = "pdf"
    else:
        ext = "md"
    return f"{prefix}.{ext}"


def date_from_string(datestring):
    year, month, day = [int(part) for part in datestring.split("-")]
    return datetime.date(year, month, day)


def work_to_do():
    # Taken from https://www.iab.org/appeals/ on 2023-08-24 - some lines carved out below as exceptions
    input = """
    2020-07-31 	IAB appeal for arpa assignment (Timothy McSweeney) 	IAB Response (2020-08-26)
    2019-01-31 	An appeal to make the procedure related to Independent Submission Stream more transparent (Shyam Bandyopadhyay) 	IAB Response (2019-03-06)
    2015-06-22 	Appeal to the IAB concerning the IESG response to his appeal concerning the IESG approval of the “draft-ietf-ianaplan-icg-response” (JFC Morfin) 	IAB Response (2015-07-08)
    2013-07-08 	Appeal to the IAB irt. RFC 6852 (JFC Morfin) 	IAB Response (2013-07-17)
    2010-06-07 	Appeal over the IESG Publication of the IDNA2008 Document Set Without Appropriate Explanation to the Internet Community (JFC Morfin) 	IAB Response (2010-08-20)
    2008-11-29 	Appeal to the IAB Concerning the Way Users Are Not Permitted To Adequately Contribute to the IETF (JFC Morfin) 	IAB Response (2009-01-28)
    2006-10-10 	Complaints about suspension from the ietf@ietf.org mailing list (Todd Glassey) 	IAB Response (2006-10-31)
    2006-09-11 	Appeal to the IAB over IESG dismissed appeals from J-F C. Morfin (JFC Morfin) 	IAB Response (2006-12-05)
    2006-09-10 	Appeal of IESG Decision of July 10, 2006 from Dean Anderson (Dean Anderson) 	IAB Response (2006-09-27)
    2006-08-24 	Appeal Against the decision to consider expediting an RFC Publication from J-F C. Morfin (JFC Morfin) 	IAB Response (2006-09-07)
    2006-04-18 	Appeal Against IESG PR-Action from Dean Anderson (Dean Anderson) 	IAB Response (2006-07-13)
    2006-02-08 	Appeal Against IESG Decision by Julian Mehnle (Julian Mehnle) 	IAB Response (2006-03-02)
    2006-01-04 	Appeal Against IESG Decision by Jefsey Morfin (JFC Morfin) 	IAB Response (2006-01-31)
    2003-01-04 	Appeal against IESG decision (Robert Elz) 	IAB Response (includes original appeal)(2003-02-15)
    2000-11-15 	Appeal Against IESG Action by Mr. D J Bernstein (D J Bernstein) 	IAB Response (2001-02-26)
    1999-10-23 	Appeal against IESG Inaction by W.A. Simpson (William Allen Simpson) 	IAB Response (2000-01-11)
    1999-05-01 	Appeal against IESG action (William Allen Simpson) 	IAB Response (1999-10-05)
    1996-03-06 	Appeal SNMPv2 SMI Appeal by Mr. David T. Perkins, IAB consideration (David Perkins) 	IAB Response (includes original appeal) (1996-03-06)
    """

    work = []

    for line in input.split("\n"):
        line = line.strip()
        if line == "":
            continue
        appeal_date = line[:10]
        response_date = line[-11:-1]
        title = line[11:-12].strip().split(")")[0] + ")"
        item = dict(title=title, date=appeal_date, parts=[])
        if appeal_date in [
            "2006-10-10",
            "2000-11-15",
            "1999-10-23",
            "1999-05-01",
            "1996-03-06",
        ]:
            item["parts"].append(dict(type="appeal_with_response", date=response_date))
        else:
            item["parts"].append(dict(type="appeal", date=appeal_date))
            item["parts"].append(dict(type="response", date=response_date))
        work.append(item)

    # Hand building the items for the following
    # exceptions="""
    # 2003-10-09      Appeal to the IAB on the site-local issue (Tony Hain)
    #     IAB Response (2003-11-12)
    #     Tony Hain reply to IAB Response (2003-11-18)
    # 1995-02-18 (etc.) 	Appeal Against IESG Inaction by Mr. Dave Cocker, Mr W. Simpson (Dave Crocker, William Allen Simpson) 	IAB Response (1995-04-04 and 1995-04-05)
    # """
    item = dict(
        title="Appeal to the IAB on the site-local issue (Tony Hain)",
        date="2003-10-09",
        parts=[],
    )
    item["parts"].append(
        dict(
            type="appeal",
            date="2003-10-09",
        )
    )
    item["parts"].append(
        dict(
            type="response",
            date="2003-11-12",
        )
    )
    item["parts"].append(
        dict(
            type="reply_to_response",
            date="2003-11-18",
        )
    )
    work.append(item)

    item = dict(
        title="Appeal Against IESG Inaction by Mr. Dave Cocker, Mr W. Simpson (Dave Crocker, William Allen Simpson)",
        date="1995-02-18",
        parts=[],
    )
    item["parts"].append(
        dict(
            type="appeal",
            date="1995-02-18",
        )
    )
    item["parts"].append(
        dict(
            type="response",
            date="2003-10-09",
            title="IAB Responses from 1995-04-04 and 1995-04-05",
        )
    )
    work.append(item)

    for item in work:
        item["date"] = date_from_string(item["date"])
        for part in item["parts"]:
            part["date"] = date_from_string(part["date"])

    work.sort(key=lambda o: o["date"])

    return work


class Command(BaseCommand):
    help = "Performs a one-time import of IAB appeals"

    def handle(self, *args, **options):
        tmpdir = tempfile.mkdtemp()
        process = subprocess.Popen(
            ["git", "clone", "https://github.com/kesara/iab-scraper.git", tmpdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
        if not Path(tmpdir).joinpath("iab_appeals", "1995-02-18-appeal.md").exists():
            print("Git clone of the iab-scraper directory did not go as expected")
            print("stdout:", stdout)
            print("stderr:", stderr)
            print(f"Clean up {tmpdir} manually")
            exit(-1)

        work = work_to_do()

        for item in work:
            # IAB is group 7
            appeal = Appeal.objects.create(name=item["title"], date=item["date"], group_id=7)
            for part in item["parts"]:
                bits_file_name = bits_name(item["date"], part)
                if bits_file_name.endswith(".pdf"):
                    content_type = "application/pdf"
                else:
                    content_type = "text/markdown"
                with Path(tmpdir).joinpath("iab_appeals", bits_file_name).open(
                    "rb"
                ) as source_file:
                    bits = source_file.read()
                    artifact_type = AppealArtifactTypeName.objects.get(slug=part["type"])
                    AppealArtifact.objects.create(
                        appeal = appeal,
                        artifact_type=artifact_type,
                        date=part["date"],
                        title=getattr(part, "title", artifact_type.name),
                        content_type=content_type,
                        bits=bits,
                    )

        shutil.rmtree(tmpdir)
