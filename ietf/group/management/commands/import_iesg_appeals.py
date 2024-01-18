# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import re
import shutil
import subprocess
import tempfile

from pathlib import Path
import dateutil

from django.conf import settings
from django.core.management import BaseCommand

from ietf.group.models import Appeal, AppealArtifact


class Command(BaseCommand):
    help = "Performs a one-time import of IESG appeals"

    def handle(self, *args, **options):
        old_appeals_root = (
            "/a/www/www6/iesg/appeal"
            if settings.SERVER_MODE == "production"
            else "/assets/www6/iesg/appeal"
        )
        tmpdir = tempfile.mkdtemp()
        process = subprocess.Popen(
            ["git", "clone", "https://github.com/rjsparks/iesg-scraper.git", tmpdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        sub_stdout, sub_stderr = process.communicate()
        if not (Path(tmpdir) / "iesg_appeals" / "anderson-2006-03-08.md").exists():
            self.stdout.write(
                "Git clone of the iesg-scraper directory did not go as expected"
            )
            self.stdout.write("stdout:", sub_stdout)
            self.stdout.write("stderr:", sub_stderr)
            self.stdout.write(f"Clean up {tmpdir} manually")
            exit(-1)
        titles = [
            "Appeal: IESG Statement on Guidance on In-Person and Online Interim Meetings (John Klensin, 2023-08-15)",
            "Appeal of current Guidance on in-Person and Online meetings (Ted Hardie, Alan Frindell, 2023-07-19)",
            "Appeal re: URI Scheme Application and draft-mcsweeney-drop-scheme (Tim McSweeney, 2020-07-08)",
            "Appeal to the IESG re WGLC of draft-ietf-spring-srv6-network-programming (Fernando Gont, Andrew Alston, and Sander Steffann, 2020-04-22)",
            "Appeal re Protocol Action: 'URI Design and Ownership' to Best \nCurrent Practice (draft-nottingham-rfc7320bis-03.txt) (John Klensin; 2020-02-04)",
            "Appeal of IESG Conflict Review process and decision on draft-mavrogiannopoulos-pkcs8-validated-parameters-02 (John Klensin; 2018-07-07)",
            "Appeal of IESG decision to defer action and request that ISE publish draft-klensin-dns-function-considerations (John Klensin; 2017-11-29)",
            'Appeal to the IESG concerning its approval of the "draft-ietf-ianaplan-icg-response" (PDF file) (JFC Morfin; 2015-03-11)',
            "Appeal re tzdist mailing list moderation (Tobias Conradi; 2014-08-28) / Withdrawn by Submitter",
            "Appeal re draft-masotta-tftpexts-windowsize-opt (Patrick Masotta; 2013-11-14)",
            "Appeal re draft-ietf-manet-nhdp-sec-threats (Abdussalam Baryun; 2013-06-19)",
            "Appeal of decision to advance RFC6376 (Douglas Otis; 2013-05-30)",
            "Appeal to the IESG in regards to RFC 6852 (PDF file) (JFC Morfin; 2013-04-05)",
            "Appeal to the IESG concerning the approbation of the IDNA2008 document set (PDF file) (JFC Morfin; 2010-03-10)",
            "Authentication-Results Header Field Appeal (Douglas Otis, David Rand; 2009-02-16) / Withdrawn by Submitter",
            "Appeal to the IAB of IESG rejection of Appeal to Last Call draft-ietf-grow-anycast (Dean Anderson; 2008-11-14)",
            "Appeal to the IESG Concerning the Way At Large Internet Lead Users Are Not Permitted To Adequately Contribute to the IETF Deliverables (JFC Morfin; 2008-09-10)",
            "Appeal over suspension of posting rights for Todd Glassey (Todd Glassey; 2008-07-28)",
            "Appeal against IESG blocking DISCUSS on draft-klensin-rfc2821bis (John C Klensin; 2008-06-13)",
            "Appeal: Continued Abuse of Process by IPR-WG Chair (Dean Anderson; 2007-12-26)",
            "Appeal to the IESG from Todd Glassey (Todd Glassey; 2007-11-26)",
            "Appeal Against the Removal of the Co-Chairs of the GEOPRIV Working Group (PDF file) (Randall Gellens, Allison Mankin, and Andrew Newton; 2007-06-22)",
            "Appeal concerning the WG-LTRU rechartering (JFC Morfin; 2006-10-24)",
            "Appeal against decision within July 10 IESG appeal dismissal (JFC Morfin; 2006-09-09)",
            "Appeal: Mandatory to implement HTTP authentication mechanism in the Atom Publishing Protocol (Robert Sayre; 2006-08-29)",
            "Appeal Against IESG Decisions Regarding the draft-ietf-ltru-matching (PDF file) (JFC Morfin; 2006-08-16)",
            "Amended Appeal Re: grow: Last Call: 'Operation of Anycast Services' to BCP (draft-ietf-grow-anycast) (Dean Anderson; 2006-06-14)",
            "Appeal Against an IESG Decision Denying Me IANA Language Registration Process by way of PR-Action (PDF file) (JFC Morfin; 2006-05-17)",
            "Appeal to the IESG of PR-Action against Dean Anderson (Dean Anderson; 2006-03-08)",
            "Appeal to IESG against AD decision: one must clear the confusion opposing the RFC 3066 Bis consensus (JFC Morfin; 2006-02-20)",
            "Appeal to the IESG of an IESG decision (JFC Morfin; 2006-02-17)",
            "Appeal to the IESG in reference to the ietf-languages@alvestrand.no mailing list (JFC Morfin; 2006-02-07)",
            "Appeal to the IESG against an IESG decision concerning RFC 3066 Bis Draft (JFC Morfin; 2006-01-14)",
            "Appeal over a key change in a poor RFC 3066 bis example (JFC Morfin; 2005-10-19)",
            "Additional appeal against publication of draft-lyon-senderid-* in regards to its recommended use of Resent- header fields in the way that is inconsistant with RFC2822(William Leibzon; 2005-08-29)",
            "Appeal: Publication of draft-lyon-senderid-core-01 in conflict with referenced draft-schlitt-spf-classic-02 (Julian Mehnle; 2005-08-25)",
            'Appeal of decision to standardize "Mapping Between the Multimedia Messaging Service (MMS) and Internet Mail" (John C Klensin; 2005-06-10)',
            "Appeal regarding IESG decision on the GROW WG (David Meyer; 2003-11-15)",
            "Appeal: Official notice of appeal on suspension rights (Todd Glassey; 2003-08-06)",
            "Appeal: AD response to Site-Local Appeal (Tony Hain; 2003-07-31)",
            "Appeal against IESG decision for draft-chiba-radius-dynamic-authorization-05.txt (Glen Zorn; 2003-01-15)",
            "Appeal Against moving draft-ietf-ipngwg-addr-arch-v3 to Draft Standard (Robert Elz; 2002-11-05)",
        ]
        date_re = re.compile(r"\d{4}-\d{2}-\d{2}")
        dates = [
            datetime.datetime.strptime(date_re.search(t).group(), "%Y-%m-%d").date()
            for t in titles
        ]

        parts = [
            ["klensin-2023-08-15.txt", "response-to-klensin-2023-08-15.txt"],
            [
                "hardie-frindell-2023-07-19.txt",
                "response-to-hardie-frindell-2023-07-19.txt",
            ],
            ["mcsweeney-2020-07-08.txt", "response-to-mcsweeney-2020-07-08.pdf"],
            ["gont-2020-04-22.txt", "response-to-gont-2020-06-02.txt"],
            ["klensin-2020-02-04.txt", "response-to-klensin-2020-02-04.txt"],
            ["klensin-2018-07-07.txt", "response-to-klensin-2018-07-07.txt"],
            ["klensin-2017-11-29.txt", "response-to-klensin-2017-11-29.md"],
            ["morfin-2015-03-11.pdf", "response-to-morfin-2015-03-11.md"],
            ["conradi-2014-08-28.txt"],
            ["masotta-2013-11-14.txt", "response-to-masotta-2013-11-14.md"],
            ["baryun-2013-06-19.txt", "response-to-baryun-2013-06-19.md"],
            ["otis-2013-05-30.txt", "response-to-otis-2013-05-30.md"],
            ["morfin-2013-04-05.pdf", "response-to-morfin-2013-04-05.md"],
            ["morfin-2010-03-10.pdf", "response-to-morfin-2010-03-10.txt"],
            ["otis-2009-02-16.txt"],
            ["anderson-2008-11-14.md", "response-to-anderson-2008-11-14.txt"],
            ["morfin-2008-09-10.txt", "response-to-morfin-2008-09-10.txt"],
            ["glassey-2008-07-28.txt", "response-to-glassey-2008-07-28.txt"],
            ["klensin-2008-06-13.txt", "response-to-klensin-2008-06-13.txt"],
            ["anderson-2007-12-26.txt", "response-to-anderson-2007-12-26.txt"],
            ["glassey-2007-11-26.txt", "response-to-glassey-2007-11-26.txt"],
            ["gellens-2007-06-22.pdf", "response-to-gellens-2007-06-22.txt"],
            ["morfin-2006-10-24.txt", "response-to-morfin-2006-10-24.txt"],
            ["morfin-2006-09-09.txt", "response-to-morfin-2006-09-09.txt"],
            ["sayre-2006-08-29.txt", "response-to-sayre-2006-08-29.txt"],
            [
                "morfin-2006-08-16.pdf",
                "response-to-morfin-2006-08-17.txt",
                "response-to-morfin-2006-08-17-part2.txt",
            ],
            ["anderson-2006-06-13.txt", "response-to-anderson-2006-06-14.txt"],
            ["morfin-2006-05-17.pdf", "response-to-morfin-2006-05-17.txt"],
            ["anderson-2006-03-08.md", "response-to-anderson-2006-03-08.txt"],
            ["morfin-2006-02-20.txt", "response-to-morfin-2006-02-20.txt"],
            ["morfin-2006-02-17.txt", "response-to-morfin-2006-02-17.txt"],
            ["morfin-2006-02-07.txt", "response-to-morfin-2006-02-07.txt"],
            ["morfin-2006-01-14.txt", "response-to-morfin-2006-01-14.txt"],
            ["morfin-2005-10-19.txt", "response-to-morfin-2005-10-19.txt"],
            ["leibzon-2005-08-29.txt", "response-to-leibzon-2005-08-29.txt"],
            ["mehnle-2005-08-25.txt", "response-to-mehnle-2005-08-25.txt"],
            ["klensin-2005-06-10.txt", "response-to-klensin-2005-06-10.txt"],
            ["meyer-2003-11-15.txt", "response-to-meyer-2003-11-15.txt"],
            ["glassey-2003-08-06.txt", "response-to-glassey-2003-08-06.txt"],
            ["hain-2003-07-31.txt", "response-to-hain-2003-07-31.txt"],
            ["zorn-2003-01-15.txt", "response-to-zorn-2003-01-15.txt"],
            ["elz-2002-11-05.txt", "response-to-elz-2002-11-05.txt"],
        ]

        assert len(titles) == len(dates)
        assert len(titles) == len(parts)

        part_times = dict()
        part_times["klensin-2023-08-15.txt"] = "2023-08-15 15:03:55 -0400"
        part_times["response-to-klensin-2023-08-15.txt"] = "2023-08-24 18:54:13 +0300"
        part_times["hardie-frindell-2023-07-19.txt"] = "2023-07-19 07:17:16PDT"
        part_times[
            "response-to-hardie-frindell-2023-07-19.txt"
        ] = "2023-08-15 11:58:26PDT"
        part_times["mcsweeney-2020-07-08.txt"] = "2020-07-08 14:45:00 -0400"
        part_times["response-to-mcsweeney-2020-07-08.pdf"] = "2020-07-28 12:54:04 -0000"
        part_times["gont-2020-04-22.txt"] = "2020-04-22 22:26:20 -0400"
        part_times["response-to-gont-2020-06-02.txt"] = "2020-06-02 20:44:29 -0400"
        part_times["klensin-2020-02-04.txt"] = "2020-02-04 13:54:46 -0500"
        # part_times["response-to-klensin-2020-02-04.txt"]="2020-03-24 11:49:31EDT"
        part_times["response-to-klensin-2020-02-04.txt"] = "2020-03-24 11:49:31 -0400"
        part_times["klensin-2018-07-07.txt"] = "2018-07-07 12:40:43PDT"
        # part_times["response-to-klensin-2018-07-07.txt"]="2018-08-16 10:46:45EDT"
        part_times["response-to-klensin-2018-07-07.txt"] = "2018-08-16 10:46:45 -0400"
        part_times["klensin-2017-11-29.txt"] = "2017-11-29 09:35:02 -0500"
        part_times["response-to-klensin-2017-11-29.md"] = "2017-11-30 11:33:04 -0500"
        part_times["morfin-2015-03-11.pdf"] = "2015-03-11 18:03:44 -0000"
        part_times["response-to-morfin-2015-03-11.md"] = "2015-04-16 15:18:09 -0000"
        part_times["conradi-2014-08-28.txt"] = "2014-08-28 22:28:06 +0300"
        part_times["masotta-2013-11-14.txt"] = "2013-11-14 15:35:19 +0200"
        part_times["response-to-masotta-2013-11-14.md"] = "2014-01-27 07:39:32 -0800"
        part_times["baryun-2013-06-19.txt"] = "2013-06-19 06:29:51PDT"
        part_times["response-to-baryun-2013-06-19.md"] = "2013-07-02 15:24:42 -0700"
        part_times["otis-2013-05-30.txt"] = "2013-05-30 19:35:18 +0000"
        part_times["response-to-otis-2013-05-30.md"] = "2013-06-27 11:56:48 -0700"
        part_times["morfin-2013-04-05.pdf"] = "2013-04-05 17:31:19 -0700"
        part_times["response-to-morfin-2013-04-05.md"] = "2013-04-17 08:17:29 -0700"
        part_times["morfin-2010-03-10.pdf"] = "2010-03-10 21:40:58 +0100"
        part_times["response-to-morfin-2010-03-10.txt"] = "2010-04-07 14:26:06 -0700"
        part_times["otis-2009-02-16.txt"] = "2009-02-16 15:47:15 -0800"
        part_times["anderson-2008-11-14.md"] = "2008-11-14 00:16:58 -0500"
        part_times["response-to-anderson-2008-11-14.txt"] = "2008-12-15 11:00:02 -0800"
        part_times["morfin-2008-09-10.txt"] = "2008-09-10 04:10:13 +0200"
        part_times["response-to-morfin-2008-09-10.txt"] = "2008-09-28 10:00:01PDT"
        part_times["glassey-2008-07-28.txt"] = "2008-07-28 08:34:52 -0700"
        part_times["response-to-glassey-2008-07-28.txt"] = "2008-09-02 11:00:01PDT"
        part_times["klensin-2008-06-13.txt"] = "2008-06-13 21:14:38 -0400"
        part_times["response-to-klensin-2008-06-13.txt"] = "2008-07-07 10:00:01 PDT"
        # part_times["anderson-2007-12-26.txt"]="2007-12-26 17:19:34EST"
        part_times["anderson-2007-12-26.txt"] = "2007-12-26 17:19:34 -0500"
        part_times["response-to-anderson-2007-12-26.txt"] = "2008-01-15 17:21:05 -0500"
        part_times["glassey-2007-11-26.txt"] = "2007-11-26 08:13:22 -0800"
        part_times["response-to-glassey-2007-11-26.txt"] = "2008-01-23 17:38:43 -0500"
        part_times["gellens-2007-06-22.pdf"] = "2007-06-22 21:45:41 -0400"
        part_times["response-to-gellens-2007-06-22.txt"] = "2007-09-20 14:01:27 -0400"
        part_times["morfin-2006-10-24.txt"] = "2006-10-24 05:03:17 +0200"
        part_times["response-to-morfin-2006-10-24.txt"] = "2006-11-07 12:56:02 -0500"
        part_times["morfin-2006-09-09.txt"] = "2006-09-09 02:54:55 +0200"
        part_times["response-to-morfin-2006-09-09.txt"] = "2006-09-15 12:56:31 -0400"
        part_times["sayre-2006-08-29.txt"] = "2006-08-29 17:05:03 -0400"
        part_times["response-to-sayre-2006-08-29.txt"] = "2006-10-16 13:07:18 -0400"
        part_times["morfin-2006-08-16.pdf"] = "2006-08-16 18:28:19 -0400"
        part_times["response-to-morfin-2006-08-17.txt"] = "2006-08-22 12:05:42 -0400"
        part_times[
            "response-to-morfin-2006-08-17-part2.txt"
        ] = "2006-11-07 13:00:58 -0500"
        # part_times["anderson-2006-06-13.txt"]="2006-06-13 21:51:18EDT"
        part_times["anderson-2006-06-13.txt"] = "2006-06-13 21:51:18 -0400"
        part_times["response-to-anderson-2006-06-14.txt"] = "2006-07-10 14:31:08 -0400"
        part_times["morfin-2006-05-17.pdf"] = "2006-05-17 06:46:18 +0200"
        part_times["response-to-morfin-2006-05-17.txt"] = "2006-07-10 14:18:10 -0400"
        part_times["anderson-2006-03-08.md"] = "2006-03-08 09:42:44 +0100"
        part_times["response-to-anderson-2006-03-08.txt"] = "2006-03-20 14:55:38 -0500"
        part_times["morfin-2006-02-20.txt"] = "2006-02-20 19:18:24 +0100"
        part_times["response-to-morfin-2006-02-20.txt"] = "2006-03-06 13:08:39 -0500"
        part_times["morfin-2006-02-17.txt"] = "2006-02-17 18:59:38 +0100"
        part_times["response-to-morfin-2006-02-17.txt"] = "2006-07-10 14:05:15 -0400"
        part_times["morfin-2006-02-07.txt"] = "2006-02-07 19:38:57 -0500"
        part_times["response-to-morfin-2006-02-07.txt"] = "2006-02-21 19:09:26 -0500"
        part_times["morfin-2006-01-14.txt"] = "2006-01-14 15:05:24 +0100"
        part_times["response-to-morfin-2006-01-14.txt"] = "2006-02-21 12:23:38 -0500"
        part_times["morfin-2005-10-19.txt"] = "2005-10-19 17:12:11 +0200"
        part_times["response-to-morfin-2005-10-19.txt"] = "2005-11-15 11:42:30 -0500"
        part_times["leibzon-2005-08-29.txt"] = "2005-08-29 08:28:52PDT"
        part_times["response-to-leibzon-2005-08-29.txt"] = "2005-12-08 14:04:47 -0500"
        part_times["mehnle-2005-08-25.txt"] = "2005-08-25 00:45:26 +0200"
        part_times["response-to-mehnle-2005-08-25.txt"] = "2005-12-08 13:37:38 -0500"
        part_times["klensin-2005-06-10.txt"] = "2005-06-10 14:49:17 -0400"
        part_times["response-to-klensin-2005-06-10.txt"] = "2005-07-22 18:14:06 -0400"
        part_times["meyer-2003-11-15.txt"] = "2003-11-15 09:47:11 -0800"
        part_times["response-to-meyer-2003-11-15.txt"] = "2003-11-25 10:56:06 -0500"
        part_times["glassey-2003-08-06.txt"] = "2003-08-06 02:14:24 +0000"
        part_times["response-to-glassey-2003-08-06.txt"] = "2003-09-24 09:54:51 -0400"
        part_times["hain-2003-07-31.txt"] = "2003-07-31 16:44:19 -0700"
        part_times["response-to-hain-2003-07-31.txt"] = "2003-09-30 14:44:30 -0400"
        part_times["zorn-2003-01-15.txt"] = "2003-01-15 01:22:28 -0800"
        part_times["elz-2002-11-05.txt"] = "2002-11-05 10:51:13 +0700"
        # No time could be found for this one:
        part_times["response-to-zorn-2003-01-15.txt"] = "2003-02-08"
        # This one was issued sometime between 2002-12-27 (when IESG minutes note that the
        # appeal response was approved) and 2003-01-04 (when the appeal was escalated to
        # the IAB) - we're using the earlier end of the window
        part_times["response-to-elz-2002-11-05.txt"] = "2002-12-27"
        for name in part_times:
            part_times[name] = dateutil.parser.parse(part_times[name]).astimezone(
                datetime.timezone.utc
            )

        redirects = []
        for index, title in enumerate(titles):
            # IESG is group 2
            appeal = Appeal.objects.create(
                name=titles[index], date=dates[index], group_id=2
            )
            for part in parts[index]:
                if part.endswith(".pdf"):
                    content_type = "application/pdf"
                else:
                    content_type = "text/markdown;charset=utf-8"
                if part.endswith(".md"):
                    source_path = Path(tmpdir) / "iesg_appeals" / part
                else:
                    source_path = Path(old_appeals_root) / part
                with source_path.open("rb") as source_file:
                    bits = source_file.read()
                    if part == "morfin-2008-09-10.txt":
                        bits=bits.decode("macintosh")
                        bits.replace("\r","\n")
                        bits.encode("utf8")
                    elif part in ["morfin-2006-02-07.txt", "morfin-2006-01-14.txt"]:
                        bits=bits.decode("windows-1252").encode("utf8")
                    artifact_type_id = (
                        "response" if part.startswith("response") else "appeal"
                    )
                    artifact = AppealArtifact.objects.create(
                        appeal=appeal,
                        artifact_type_id=artifact_type_id,
                        date=part_times[part].date(),
                        content_type=content_type,
                        bits=bits,
                    )
                    redirects.append(
                        (
                            part.replace(".md", ".html")
                            if part.endswith(".md")
                            else part,
                            artifact.pk,
                        )
                    )

        shutil.rmtree(tmpdir)
        with open("iesg_appeal_redirects.txt", "w") as f:
            f.write(str(redirects))
