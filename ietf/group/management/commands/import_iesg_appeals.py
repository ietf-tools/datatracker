# Copyright The IETF Trust 2023, All Rights Reserved

import datetime
import re
import shutil
import subprocess
import tempfile

from pathlib import Path

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
        stdout, stderr = process.communicate()
        if not (Path(tmpdir) / "iesg_appeals" / "anderson-2006-03-08.md").exists():
            print("Git clone of the iesg-scraper directory did not go as expected")
            print("stdout:", stdout)
            print("stderr:", stderr)
            print(f"Clean up {tmpdir} manually")
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
                    artifact_type_id = (
                        "response" if part.startswith("response") else "appeal"
                    )
                    AppealArtifact.objects.create(
                        appeal=appeal,
                        artifact_type_id=artifact_type_id,
                        date=part["date"], # AMHERE - need to get timestamps for all the artifacts.
                        content_type=content_type,
                        bits=bits,
                    )
        
        shutil.rmtree(tmpdir)
        # Build the bulk redirect rules for cloudflare
