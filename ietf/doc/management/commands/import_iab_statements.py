# Copyright The IETF Trust 2023, All Rights Reserved

import debug  # pyflakes:ignore

import csv
import datetime
import io
import os
import shutil
import subprocess
import tempfile

from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ietf.doc.models import Document, DocAlias, DocEvent, State
from ietf.utils.text import xslugify


class Command(BaseCommand):
    help = "Performs a one-time import of IAB statements"

    def handle(self, *args, **options):
        if Document.objects.filter(type="statement", group__acronym="iab").exists():
            print("IAB statement documents already exist - exiting")
            exit(-1)
        tmpdir = tempfile.mkdtemp()
        process = subprocess.Popen(
            ["git", "clone", "https://github.com/kesara/iab-scraper.git", tmpdir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
        if not Path(tmpdir).joinpath("iab_minutes", "2022-12-14.md").exists():
            print("Git clone of the iab-scraper directory did not go as expected")
            print("stdout:", stdout)
            print("stderr:", stderr)
            print(f"Clean up {tmpdir} manually")
            exit(-1)

        spreadsheet_rows = load_spreadsheet()
        with open("iab_statement_redirects.csv", "w") as redirect_file:
            redirect_writer = csv.writer(redirect_file)
            for index, (file_fix, date_string, title, url, _) in enumerate(
                spreadsheet_rows
            ):
                name = url.split("/")[6].lower()
                if name.startswith("iabs"):
                    name = name[5:]
                elif name.startswith("iab"):
                    name = name[4:]
                if index == 1:
                    name += "-archive"  # https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-statement-on-identifiers-and-unicode-7-0-0/archive/
                if index == 100:
                    name = (
                        "2010-" + name
                    )  # https://www.iab.org/documents/correspondence-reports-documents/docs2010/iab-statement-on-the-rpki/
                if index == 152:
                    name = (
                        "2018-" + name
                    )  # https://www.iab.org/documents/correspondence-reports-documents/2018-2/iab-statement-on-the-rpki/
                docname = f"statement-iab-{xslugify(name)}"
                ext = None
                base_sourcename = (
                    f"{date_string}-{file_fix}" if file_fix != "" else date_string
                )
                if (
                    Path(tmpdir)
                    .joinpath("iab_statements", f"{base_sourcename}.md")
                    .exists()
                ):
                    ext = "md"
                elif (
                    Path(tmpdir)
                    .joinpath("iab_statements", f"{base_sourcename}.pdf")
                    .exists()
                ):
                    ext = "pdf"
                if ext is None:
                    debug.show(
                        'f"Could not find {Path(tmpdir).joinpath("iab_statements", f"{base_path}.md")}"'
                    )
                    continue
                filename = f"{docname}-00.{ext}"
                # Create Document
                doc = Document.objects.create(
                    name=docname,
                    type_id="statement",
                    title=title,
                    group_id=7,  # The IAB group
                    rev="00",
                    uploaded_filename=filename,
                )
                doc.set_state(State.objects.get(type_id="statement", slug="active"))
                DocAlias.objects.create(name=doc.name).docs.add(doc)
                year, month, day = [int(part) for part in date_string.split("-")]
                e1 = DocEvent.objects.create(
                    time=datetime.datetime(
                        year, month, day, 12, 00, tzinfo=datetime.timezone.utc
                    ),
                    type="published_statement",
                    doc=doc,
                    rev="00",
                    by_id=1,
                    desc="Statement published (note: The 1200Z time of day is inaccurate - the actual time of day is not known)",
                )
                e2 = DocEvent.objects.create(
                    type="added_comment",
                    doc=doc,
                    rev="00",
                    by_id=1,  # The "(System)" person
                    desc="Statement moved into datatracker from iab wordpress website",
                )
                doc.save_with_history([e1, e2])

                # Put file in place
                source = Path(tmpdir).joinpath(
                    "iab_statements", f"{base_sourcename}.{ext}"
                )
                dest = Path(settings.DOCUMENT_PATH_PATTERN.format(doc=doc)).joinpath(
                    filename
                )
                if dest.exists():
                    print(f"WARNING: {dest} already exists - not overwriting it.")
                else:
                    os.makedirs(dest.parent, exist_ok=True)
                    shutil.copy(source, dest)

                redirect_writer.writerow(
                    [
                        url,
                        f"https://datatracker.ietf.org/doc/{docname}",
                    ]
                )

        shutil.rmtree(tmpdir)


def load_spreadsheet():
    csv_dump = '''2002-03-01,IAB RFC Publication Process Description(txt) March 2003,https://www.iab.org/documents/correspondence-reports-documents/docs2003/iab-rfc-publication-process/,deprecated
2015-01-27,IAB Statement on Identifiers and Unicode 7.0.0 (archive),https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-statement-on-identifiers-and-unicode-7-0-0/archive/,deprecated
2010-02-05,Response to the EC’s RFI on Forums and Consortiums,https://www.iab.org/documents/correspondence-reports-documents/docs2010/response-to-the-ecs-rfi-on-forums-and-consortiums/,https://www.iab.org/wp-content/IAB-uploads/2011/03/2010-02-05-IAB-Response-Euro-ICT-Questionnaire.pdf
2011-03-30,IAB responds to NTIA Request for Comments on the IANA Functions,https://www.iab.org/documents/correspondence-reports-documents/2011-2/iab-responds-to-ntia-request-for-comments-on-the-iana-functions/,https://www.iab.org/wp-content/IAB-uploads/2011/04/2011-03-30-iab-iana-noi-response.pdf
2011-07-28,IAB's response to the NTIA FNOI on IANA,https://www.iab.org/documents/correspondence-reports-documents/2011-2/iabs-response-to-the-ntia-fnoi-on-iana/,https://www.iab.org/wp-content/IAB-uploads/2011/07/IANA-IAB-FNOI-2011.pdf
2011-12-16,"Questionnaire in support of the ICANN bid for the IANA function [Dec 16, 2011]",https://www.iab.org/documents/correspondence-reports-documents/2011-2/questionnaire-in-support-of-the-icann-bid-for-the-iana-function/,https://www.iab.org/wp-content/IAB-uploads/2011/12/IAB-Past-Performance-Questionnaire.pdf
2012-04-03,IETF Oversight of the IANA Protocol Parameter Function,https://www.iab.org/documents/correspondence-reports-documents/2012-2/ietf-oversight-of-the-iana-protocol-parameter-function/,https://www.iab.org/wp-content/IAB-uploads/2012/04/IETF-IANA-Oversight.pdf
2012-04-29,IETF and IAB comment on OMB Circular A-119,https://www.iab.org/documents/correspondence-reports-documents/2012-2/ietf-and-iab-comment-on-omb-circular-a-119/,https://www.iab.org/wp-content/IAB-uploads/2012/04/OMB-119.pdf
2012-05-24,IAB submits updated ICANN performance evaluation,https://www.iab.org/documents/correspondence-reports-documents/2012-2/iab-submits-updated-icann-performance-evaluation/,https://www.iab.org/wp-content/IAB-uploads/2012/05/IAB-Past-Performance-Questionnaire-FINAL.pdf
2013-07-02,Open letter to the European Commission and the European Parliament in the matter of the Transatlantic Trade and Investment Partnership (TTIP),https://www.iab.org/documents/correspondence-reports-documents/2013-2/open-letter-to-the-ec/,https://www.iab.org/wp-content/IAB-uploads/2013/07/TTIP_market_driven_standards_EU_letter.pdf
2013-05-10,Comments In the matter of Transatlantic Trade and Investment Partnership (TTIP) (USTR-2013-0019),https://www.iab.org/documents/correspondence-reports-documents/2013-2/comments-in-the-matter-of-transatlantic-trade-and-investment-partnership-ttip-ustr-2013-0019/,https://www.iab.org/wp-content/IAB-uploads/2013/07/TTIP_market_driven_standards_FINAL.pdf
2013-10-23,IAB Comments on Recommendation for Random Number Generation Using Deterministic Random Bit Generators,https://www.iab.org/documents/correspondence-reports-documents/2013-2/nist-sp-800-90a/,https://www.iab.org/wp-content/IAB-uploads/2013/10/IAB-NIST-FINAL.pdf
2014-04-07,IAB Comments on NISTIR 7977,https://www.iab.org/documents/correspondence-reports-documents/2014-2/iab-comments-on-nistir-7977/,https://www.iab.org/wp-content/IAB-uploads/2014/04/IAB-NIST7977-20140407.pdf
2014-04-29,Comments to ICANN on the Transition of NTIA’s Stewardship of the IANA Functions,https://www.iab.org/documents/correspondence-reports-documents/2014-2/iab-response-to-icann-iana-transition-proposal/,https://www.iab.org/wp-content/IAB-uploads/2014/04/iab-response-to-20140408-20140428a.pdf
2016-05-27,"IAB Comments to US NTIA Request for Comments, ""The Benefits, Challenges, and Potential Roles for the Government in Fostering the Advancement of the Internet of Things""",https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-comments-to-ntia-request-for-comments-the-benefits-challenges-and-potential-roles-for-the-government/,https://www.iab.org/wp-content/IAB-uploads/2016/05/ntia-iot-20160525.pdf
2016-05-24,"IAB Chair Testifies before the United States Senate Committee on Commerce, Science, and Transportation on ""Examining the Multistakeholder Plan for Transitioning the Internet Assigned Number Authority""",https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-chair-statement-before-us-senate-committee-on-iana-transition/,https://www.iab.org/wp-content/IAB-uploads/2016/05/sullivan-to-senate-commerce-20160524.pdf
2018-07-16,IAB Response to NTIA Notice of Inquiry on International Internet Policy Priorities,https://www.iab.org/documents/correspondence-reports-documents/2018-2/iab-response-to-ntia-notice-of-inquiry-on-international-internet-policy-priorities-response/,https://www.iab.org/wp-content/IAB-uploads/2018/07/IAB-response-to-the-2018-NTIA-Notice-of-Inquiry.pdf
2018-09-09,Internet Architecture Board Comments on the Australian Assistance and Access Bill 2018,https://www.iab.org/documents/correspondence-reports-documents/2018-2/internet-architecture-board-comments-on-the-australian-assistance-and-access-bill-2018/,https://www.iab.org/wp-content/IAB-uploads/2018/09/IAB-Comments-on-Australian-Assistance-and-Access-Bill-2018.pdf
2023-03-03,IAB Response to the Office of the High Commissioner for Human Rights Call for Input  on “The relationship between human rights and technical standard-setting processes for new and emerging digital technologies”,https://www.iab.org/documents/correspondence-reports-documents/2023-2/iab-response-to-the-ohchr-call-for-input-on-the-relationship-between-human-rights-and-technical-standard/,https://www.iab.org/wp-content/IAB-uploads/2023/03/IAB-Response-to-OHCHR-consultation.pdf
1998-12-09,"IAB Request to IANA for Delegating IPv6 Address Space, Mail Message, December 1998",https://www.iab.org/documents/correspondence-reports-documents/docs98/iab-request-to-iana-for-delegating-ipv6-address-space-mail-message-december-1998/,
1998-12-18,"1998 Statements on Cryptography, Mail Message, December 1998.",https://www.iab.org/documents/correspondence-reports-documents/docs98/1998-statements-on-cryptography/,
1999-02-22,Correspondence between Bradner and Dyson on Protocol Parameter Parameters,https://www.iab.org/documents/correspondence-reports-documents/docs99/correspondence-between-bradner-and-dyson-on-protocol-parameter-parameters/,
1999-08-13,Comment on ICANN ASO membership,https://www.iab.org/documents/correspondence-reports-documents/docs99/comment-on-icann-aso-membership/,
1999-10-19,Ad Hoc Group on Numbering,https://www.iab.org/documents/correspondence-reports-documents/docs99/ad-hoc-group-on-numbering/,
2000-05-01,"IAB Statement on Infrastructure Domain and Subdomains, May 2000.",https://www.iab.org/documents/correspondence-reports-documents/docs2000/iab-statement-on-infrastructure-domain-and-subdomains-may-2000/,
2002-05-01,"IETF and ITU-T Cooperation Arrangements, May 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/ietf-and-itu-t-cooperation-arrangements-may-2002/,
2002-05-03,"IAB replyto ENUM liaison statement, May 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/enum-response/,
2002-05-24,"Interim Approval for Internet Telephone Numbering System (ENUM) Provisioning, 24 May 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/enum-pr/,
2002-06-01,"IAB response to ICANN Evolution and Reform, June 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/icann-response/,
2002-09-01,"IAB response to ICANN Evolution and Reform Committee's Second Interim Report, September 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/icann-response-2/,
2002-10-01,"IAB response to ICANN Evolution and Reform Committee's Final Implementation Report, October 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/icann-response-3/,
2002-12-10,"IAB Response to RIRs request regarding 6bone address entries in ip6.arpa, December 2002",https://www.iab.org/documents/correspondence-reports-documents/docs2002/3ffe/,
2003-01-03,"IETF Notice of Withdrawal from the Protocol Support Organization, January 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/icann-pso-notice/,
2003-01-25,"IAB Response to Verisign GRS IDN Announcement, January 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/icann-vgrs-response/,
2003-07-10,"Note: Unified Notification Protocol Considerations, July 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-07-10-iab-notification/,
2003-08-01,Open Architectural Issues in the Development of the Internet,https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-08-architectural-issues/,
2003-08-28,RFC Document editing/ queueing suggestion,https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-08-28-klensin-rfc-editor/,
2003-09-02,"IAB Chair's announcement of an Advisory Committee, September 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-02-adv-committee/,
2003-09-19,"IAB Commentary: Architectural Concerns on the Use of DNS Wildcards, September 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-20-dns-wildcards/,
2003-09-24,"IAB to ICANN: IAB input related to the .cs code in ISO 3166, 24 September 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-25-icann-cs-code/,
2003-09-24,"IAB to ISO: IAB comment on stability of ISO 3166 and other infrastructure standards, 24 September 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-25-iso-cs-code/,
2003-09-25,"Correspondance to ISO concerning .cs code, and advice to ICANN, 25 September 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-25-icann-cs-code-2/,
2003-09-25,"Correspondance to ISO concerning .cs code, and advice to ICANN, 25 September 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-25-iso-cs-code-2/,
2003-09-26,ISO Codes,https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-09-23-isocodes/,
2003-10-02,"IESG to IAB: Checking data for validity before usage in a protocol, 2 October 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-10-02-iesg-dns-validity-check-query/,
2003-10-14,"Survey of Current Security Work in the IETF, October 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-10-14-security-survey/,
2003-10-17,"IAB to ICANN SESAC:Wildcard entries in DNS domains, 17 October 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-10-17-crocker-wildcards-2/,
2003-10-17,"IAB note to Steve Crocker, Chair, ICANN Security and Stability Advisory Committee, October 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-10-17-crocker-wildcards/,
2003-10-18,"IAB concerns against permanent deployment of edge-based port filtering, October 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-10-18-edge-filters/,
2003-11-08,"IAB Response to IESG architectural query: Checking data for validity before usage in protocol, November 2003",https://www.iab.org/documents/correspondence-reports-documents/docs2003/2003-11-08-iesg-dns-validity-check-query-response/,
2004-01-19,"Number Resource Organisation (NRO) formation, 19 January 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-01-19-nro/,
2004-01-22,"IAB to RIPE NCC:ENUM Administration, 22 January 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-01-22-enum-subcodes/,
2004-02-09,"IAB to IANA: Instructions to IANA -Delegation of 2.0.0.2.ip6.arpa, 9 February, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-02-09-6to4-rev-delegation/,
2004-02-26,The IETF -- what is it?,https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-02-26-ietf-defn/,
2004-04-15,"IAB to ICANN: Validity checks for names, 15 April, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-04-15-icann-dns-validity-check/,
2004-05-07,"IAB to IANA: IPv6 Allocation Policy , 7 May, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-05-07-iana-v6alloc/,
2004-05-24,"IAB to IANA: Instructions to IANA -Delegation of 3.f.f.e.ip6.arpa, 24 May, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-05-24-3ffe-rev-delegation/,
2004-05-27,"IAB to ICANN:Concerns regarding IANA Report, 27 May, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-05-27-iana-report/,
2004-07-16,"Upcoming clarifications to RIPE NCC instructions for e164.arpa operation, 16 July 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-07-15-enum-instructions/,
2004-07-16,"IANA Delegation Requests, 16 July 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-07-16-iana-delegation/,
2004-08-06,OMA-IETF Standardization Collaboration,https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-08-draft-iab-oma-liaison-00/,
2004-08-12,"IAB to RIPE NCC:Notice of revision of instructions concerning the ENUM Registry, 12 August, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-08-12-enum-instructions/,
2004-08-12,"Response to your letter of August 4, 12 August 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-08-12-icann-wildcard/,
2004-09-27,"IAB to ICANN:Report of Concerns over IANA Performance , 27 September, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-09-27-iana-concerns/,
2004-09-27,"IAB Report of IETF IANA Functions , 27 September 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-09-27-iana-report/,
2004-11-03,"IAB to IESG:Comments on Teredo , 3 November, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-11-03-teredo-comments/,
2004-11-12,"IAB to ICANN:Response to ICANN Request for assistance with new TLD Policy , 12 November, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-11-12-icann-new-tld-policy/,
2004-11-29,"The IETF and IPv6 Address Allocation , 29 November 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-11-29-ipv6-allocs/,
2004-12-15,"IAB Comment to Internet AD:Comments on IANA Considerations in IPv6 ULA draft, 15 December, 2004",https://www.iab.org/documents/correspondence-reports-documents/docs2004/2004-12-15-ipv6-ula-iana-considerations/,
2005-02-16,"IAB review of Structure of the IETF Administrative Support Activity, 16 February 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-02-16-iasa/,
2005-08-26,"SiteFinder returns, 26 August 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-08-26-ssac-note/,
2005-09-01,"Re: SiteFinder returns, 1 September 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-09-01-ssac-response/,
2005-10-14,"IAB to ICANN: IAB comments on ICANN IDN Guidelines, 14 October 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-10-14-idn-guidelines/,
2005-11-07,"IAB to ICANN – Nameserver change for e164.arpa, 7 November 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-11-07-nameserver-change/,
2005-11-22,"IETF to ICANN – IANA structural status, 22 November 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-11-22-iana-structure/,
2005-11-29,"IAB to IANA – Teredo prefix assignment, 29 November 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-11-29-teredo-prefix/,
2005-12-22,"IAB to ICANN – dot arpa TLD management, 22 December 2005",https://www.iab.org/documents/correspondence-reports-documents/docs2005/2005-12-22-dot-arpa/,
2006-03-06,"IAB Position on the IETF IANA Technical Parameter Function, 6 March 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/iab-iana-position/,
2006-03-28,"IAB to ICANN – Name server changes for ip6.arpa, 28 March 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-03-28-nameserver-change/,
2006-04-20,"IAB to IANA – Administrative contact information change for arpa, 20 April 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-04-20-update-to-administrative-contact-information-for-arpa-iana/,
2006-04-20,"IAB to ITU TSB – FYI re contact info changes for e164.arpa, 20 April 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-04-20-update-to-contact-information-for-e164-arpa-hill/,
2006-04-20,"IAB to IANA – Contact information changes for e164.arpa, 20 April 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-04-20-update-to-contact-information-for-e164-arpa-iana/,
2006-05-15,"IAB to IANA – Request to IANA for status update on deployment of DNSSEC on IANA managed zones, 15 May 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-05-15-iab-request-to-iana-to-sign-dnssec-zones/,
2006-06-07,"The IAB announces the mailing list for the discussion of the independent submissions process, 7 June 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-06-07-independent-submissions/,
2006-06-19,"Procedural issues with liaison on nextsteps, 19 June 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-06-16-response-to-idn-liaison-issues/,
2006-10-12,"The IAB sends a note to the Registry Services Technical Evaluation Panel on the use of wildcards in the .travel TLD, 12 October 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-10-12-rstep-note/,
2006-10-19,"The IAB sends a note to the OIF Technical Committee Chair on IETF Protocol Extensions, 19 October 2006",https://www.iab.org/documents/correspondence-reports-documents/docs2006/2006-10-19-oifnote/,
2007-05-21,"The IAB responds to ITU Consultation on Resolution 102, 21 May 2007",https://www.iab.org/documents/correspondence-reports-documents/docs2007/2007-05-21-itu-resolution-102/,
2007-07-05,"Correspondence from the RIPE NCC regarding deployment of DNSSEC in the E164.ARPA zone, 5 July 2007",https://www.iab.org/documents/correspondence-reports-documents/docs2007/2007-07-05-ripe-ncc-dnssec-e164/,
2007-07-24,"Correspondence from the IAB to the ITU-TSB Director regarding deployment of DNSSEC in the E164.ARPA zone, 24 July 2007",https://www.iab.org/documents/correspondence-reports-documents/docs2007/2007-07-24-iab-itu-dnssec-e164/,
2007-10-10,"Follow-up work on NAT-PT, 10 October 2007",https://www.iab.org/documents/correspondence-reports-documents/docs2007/follow-up-work-on-nat-pt/,
2008-02-15,"Correspondence from the IAB to the National Telecommunications and Information Administration, US Department of Commerce regarding the ICANN/DoC Joint Project Agreement, 15 February 2008",https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-02-15-midterm-view-icann-doc-jpa/,
2008-03-07,"The IAB’s response to ICANN’s solicitation on DNS stability, 7 March 2008",https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-03-07-icann-new-gtlds/,
2008-06-04,Proposed RFC Editor Structure,https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-06-04-rfc-editor-model/,
2008-08-16,"The IAB’s response to Geoff Huston’s request concerning 32-bit AS numbers, 16 August 2008",https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-08-16-32bit-as-huston/,
2008-09-05,Proposed RFC Editor Structure,https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-09-05-rfc-editor-model/,
2008-11-18,"The IAB’s correspondence with NTIA on DNSSEC deployment at the root, 18 November 2008",https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-11-18-dnssec-deployment-at-the-root/,
2008-12-04,"IAB correspondence with Geoff Huston on TAs, IANA, RIRs et al.., 4 December 2008",https://www.iab.org/documents/correspondence-reports-documents/docs2008/2008-12-04-huston-tas-iana-rirs/,
2009-06-02,"IAB correspondence with IANA on the Signing of .ARPA, 2 June 2009",https://www.iab.org/documents/correspondence-reports-documents/docs2009/2009-06-02-roseman-signing-by-iana-of-arpa/,
2009-10-14,"IAB correspondence with ICANN on their “Scaling the Root” study., 14 October 2009",https://www.iab.org/documents/correspondence-reports-documents/docs2009/2009-10-14-icann-scaling-the-root/,
2010-01-27,IAB statement on the RPKI,https://www.iab.org/documents/correspondence-reports-documents/docs2010/iab-statement-on-the-rpki/,
2010-07-30,Transition of IN-ADDR.ARPA generation,https://www.iab.org/documents/correspondence-reports-documents/docs2010/transition-of-in-addr-arpa-generation/,
2011-06-22,Response to ARIN's request for guidance regarding Draft Policy ARIN-2011-5,https://www.iab.org/documents/correspondence-reports-documents/2011-2/response-to-arins-request-for-guidance-regarding-draft-policy-arin-2011-5/,
2011-07-25,"IAB Response to ""Some IESG Thoughts on Liaisons""",https://www.iab.org/documents/correspondence-reports-documents/2011-2/iab-response-to-some-iesg-thoughts-on-liaisons/,
2011-09-16,Letter to the European Commission on Global Interoperability in Emergency Services,https://www.iab.org/documents/correspondence-reports-documents/2011-2/letter-to-the-european-commission-on-global-interoperability-in-emergency-services/,
2012-02-08,"IAB Statement: ""The interpretation of rules in the ICANN gTLD Applicant Guidebook""",https://www.iab.org/documents/correspondence-reports-documents/2012-2/iab-statement-the-interpretation-of-rules-in-the-icann-gtld-applicant-guidebook/,
2012-03-26,"Response to ICANN questions concerning ""The interpretation of rules in the ICANN gTLD Applicant Guidebook""",https://www.iab.org/documents/correspondence-reports-documents/2012-2/response-to-icann-questions-concerning-the-interpretation-of-rules-in-the-icann-gtld-applicant-guidebook/,
2012-03-30,IAB Member Roles in Evaluating New Work Proposals,https://www.iab.org/documents/correspondence-reports-documents/2012-2/iab-member-roles-in-evaluating-new-work-proposals/,
2012-08-29,Leading Global Standards Organizations Endorse ‘OpenStand’ Principles that Drive Innovation and Borderless Commerce,https://www.iab.org/documents/correspondence-reports-documents/2012-2/leading-global-standards-organizations-endorse-%e2%80%98openstand/,
2013-03-28,IAB Response to RSSAC restructure document (28 March 2013),https://www.iab.org/documents/correspondence-reports-documents/2013-2/iab-response-to-rssac-restructure-document-28-march-2013/,
2013-05-28,Consultation on Root Zone KSK Rollover from the IAB,https://www.iab.org/documents/correspondence-reports-documents/2013-2/consultation-on-root-zone-ksk-rollover-from-the-iab/,
2013-07-10,IAB Statement: Dotless Domains Considered Harmful,https://www.iab.org/documents/correspondence-reports-documents/2013-2/iab-statement-dotless-domains-considered-harmful/,
2013-07-16,IAB Response to ICANN Consultation on the Source of Policies & User Instructions for Internet Number Resource Requests,https://www.iab.org/documents/correspondence-reports-documents/2013-2/iab-response-to-iana-policies-user-instructions-25jun13/,
2013-10-03,Statement from the IAB on the Strengths of the OpenStand Principles,https://www.iab.org/documents/correspondence-reports-documents/2013-2/statement-from-openstand-on-the-strengths-of-the-openstand-principles/,
2013-10-07,Montevideo Statement on the Future of Internet Cooperation,https://www.iab.org/documents/correspondence-reports-documents/2013-2/montevideo-statement-on-the-future-of-internet-cooperation/,
2013-11-27,IAB Statement on draft-farrell-perpass-attack-00,https://www.iab.org/documents/correspondence-reports-documents/2013-2/iab-statement-on-draft-farrell-perpass-attack-00/,
2014-01-23,IAB Comments Regarding the IRTF CFRG chair,https://www.iab.org/documents/correspondence-reports-documents/2014-2/0123-iab-comments-regarding-the-irtf-cfrg-chair/,
2014-02-14,"Statement from the I* Leaders Coordination Meeting, Santa Monica, 14 February 2014",https://www.iab.org/documents/correspondence-reports-documents/2014-2/statement-from-the-i-leaders-coordination-meeting-santa-monica-14-february-2014/,
2014-03-11,Re: Guiding the Evolution of the IANA Protocol Parameter Registries,https://www.iab.org/documents/correspondence-reports-documents/2014-2/re-guiding-the-evolution-of-the-iana-protocol-parameter-registries/,
2014-03-14,Internet Technical Leaders Welcome IANA Globalization Progress,https://www.iab.org/documents/correspondence-reports-documents/2014-2/internet-technical-leaders-welcome-iana-globalization-progress/,
2014-05-13,I* Post-NETmundial Meeting Statement,https://www.iab.org/documents/correspondence-reports-documents/2014-2/i-post-netmundial-meeting-statement/,
2014-06-05,Comments on ICANN Board Member Compensation from the IAB,https://www.iab.org/documents/correspondence-reports-documents/2014-2/comments-on-icann-board-member-compensation/,
2014-11-13,IAB Statement on Internet Confidentiality,https://www.iab.org/documents/correspondence-reports-documents/2014-2/iab-statement-on-internet-confidentiality/,
2014-12-04,IAB statement on the NETmundial Initiative,https://www.iab.org/documents/correspondence-reports-documents/2014-2/iab-statement-on-the-netmundial-initiative/,
2014-12-17,IAB Comments on CSTD Report Mapping International Internet Public Policy Issues,https://www.iab.org/documents/correspondence-reports-documents/2014-2/iab-comments-on-cstd-report-mapping-international-public-policy-issues/,
2015-02-11,IAB liaison to ICANN Root Server System Advisory Committee (RSSAC),https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-liaison-to-icann-root-server-system-advisory-council-rssac/,
2015-02-11,IAB Statement on Identifiers and Unicode 7.0.0,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-statement-on-identifiers-and-unicode-7-0-0/,
2015-03-02,IAB Statement on Liaison Compensation,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-statement-on-liaison-compensation/,
2015-04-09,IAB Comments on The HTTPS-Only Standard,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-the-https-only-standard/,
2015-06-03,IAB comments on CCWG-Accountability Draft Report,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-ccwg-accountability-draft-report/,
2015-06-12,IAB Statement on the Trade in Security Technologies,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-statement-on-the-trade-in-security-technologies/,
2015-06-24,"IAB Correspondence to U.S. Bureau of Industry and Security, re RIN 0694-AG49",https://www.iab.org/documents/correspondence-reports-documents/2015-2/rin-0694-ag49/,
2015-09-07,Internet Architecture Board comments on the ICG Proposal,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-icg-proposal/,
2015-09-09,IAB comments on the CCWG accountability 2d draft report,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-ccwg-accountability/,
2015-10-07,IAB Comments to FCC on Rules regarding Authorization of Radiofrequency Equipment,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-fcc-15-92/,
2015-12-16,IAB comments on the CCWG accountability 3d draft report,https://www.iab.org/documents/correspondence-reports-documents/2015-2/iab-comments-on-the-ccwg-accountability-3d-draft-report/,
2016-01-13,"Comments from the Internet Architecture Board (IAB) on ""Registration Data Access Protocol (RDAP) Operational Profile for gTLD Registries and Registrars""",https://www.iab.org/documents/correspondence-reports-documents/2016-2/comments-from-the-internet-architecture-board-iab-on-registration-data-access-protocol-rdap-operational-profile-for-gtld-registries-and-registrars/,
2016-05-04,IAB comments on Draft New ICANN Bylaws,https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-comments-on-draft-new-icann-bylaws/,
2016-05-11,IAB Comments on Proposed Changes to Internet Society Bylaws,https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-comments-on-proposed-changes-to-internet-society-bylaws/,
2016-07-17,Comments from the IAB on LGRs for second level,https://www.iab.org/documents/correspondence-reports-documents/2016-2/comments-from-the-iab-on-lgrs-for-second-level/,
2016-09-01,IAB statement on IANA Intellectual Property Rights,https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-statement-on-iana-intellectual-property-rights/,
2016-09-14,IAB Statement on the IANA Stewardship Transition,https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-statement-on-the-iana-stewardship-transition/,
2016-11-07,IAB Statement on IPv6,https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-statement-on-ipv6/,
2016-12-07,"IAB comment on ""Revised Proposed Implementation of GNSO Thick Whois Consensus Policy Requiring Consistent Labeling and Display of RDDS (Whois) Output for All gTLDs""",https://www.iab.org/documents/correspondence-reports-documents/2016-2/iab-comment-on-revised-proposed-implementation-of-gnso-thick-whois-consensus-policy-requiring-consistent-labeling-and-display-of-rdds-whois-output-for-all-gtlds/,
2017-01-04,IAB comments on Identifier Technology Health Indicators: Definition,https://www.iab.org/documents/correspondence-reports-documents/2017-2/iab-comments-on-identifier-technology-health-indicators-definition/,
2017-02-01,IAB Statement on OCSP Stapling,https://www.iab.org/documents/correspondence-reports-documents/2017-2/iab-statement-on-ocsp-stapling/,
2017-02-16,Follow up on barriers to entry blog post,https://www.iab.org/documents/correspondence-reports-documents/2017-2/follow-up-on-barriers-to-entry-blog-post/,
2017-03-02,IAB Comments to United States NTIA on the Green Paper: Fostering the Advancement of the Internet of Things,https://www.iab.org/documents/correspondence-reports-documents/2017-2/iab-comments-to-ntia-on-fostering-the-advancement-of-iot/,
2017-03-30,Internet Architecture Board statement on the registration of special use names in the ARPA domain,https://www.iab.org/documents/correspondence-reports-documents/2017-2/iab-statement-on-the-registration-of-special-use-names-in-the-arpa-domain/,
2017-05-01,Comments from the IAB on IDN Implementation Guidelines,https://www.iab.org/documents/correspondence-reports-documents/2017-2/comments-from-the-iab-on-idn-implementation-guidelines/,
2017-07-31,IAB Response to FCC-17-89,https://www.iab.org/documents/correspondence-reports-documents/2017-2/iab-response-to-fcc-17-89/,
2018-03-15,IAB Statement on Identifiers and Unicode,https://www.iab.org/documents/correspondence-reports-documents/2018-2/iab-statement-on-identifiers-and-unicode/,
2018-04-03,IAB Statement on the RPKI,https://www.iab.org/documents/correspondence-reports-documents/2018-2/iab-statement-on-the-rpki/,
2019-05-02,Revised Operating Instructions for e164.arpa (ENUM),https://www.iab.org/documents/correspondence-reports-documents/2019-2/revised-operating-instructions-for-e164-arpa-enum/,
2019-06-26,Comments on Evolving the Governance of the Root Server System,https://www.iab.org/documents/correspondence-reports-documents/2019-2/comments-on-evolving-the-governance-of-the-root-server-system/,
2019-09-04,Avoiding Unintended Harm to Internet Infrastructure,https://www.iab.org/documents/correspondence-reports-documents/2019-2/avoiding-unintended-harm-to-internet-infrastructure/,
2020-07-01,"IAB correspondence with the National Telecommunications and Information Administration (NTIA) on DNSSEC deployment for the Root Zone [Docket No. 100603240-0240-01], 1 July 2010",https://www.iab.org/documents/correspondence-reports-documents/docs2010/2010-07-01-alexander-dnssec-deployment-for-the-root-zone/,
2020-09-29,IAB Comments on the Draft Final Report on the new gTLD Subsequent Procedures Policy Development Process,https://www.iab.org/documents/correspondence-reports-documents/2020-2/iab-comments-on-new-gtld-subsequent-procedures/,
2021-07-14,IAB Statement on Inclusive Language in IAB Stream Documents,https://www.iab.org/documents/correspondence-reports-documents/2021-2/iab-statement-on-inclusive-language-in-iab-stream-documents/,
2022-04-08,IAB comment on Mandated Browser Root Certificates in the European Union’s eIDAS Regulation on the Internet,https://www.iab.org/documents/correspondence-reports-documents/2022-2/iab-comment-on-mandated-browser-root-certificates-in-the-european-unions-eidas-regulation-on-the-internet/,
2022-04-08,"IAB Comments on A Notice by the Federal Communications Commission on Secure Internet Routing, issued 03/11/2022",https://www.iab.org/documents/correspondence-reports-documents/2022-2/iab-comments-on-a-notice-by-the-federal-communications-commission-on-secure-internet-routing-issued-03-11-2022/,
2022-07-08,IAB Statement to OSTP on Privacy-Enhancing Technologies,https://www.iab.org/documents/correspondence-reports-documents/2022-2/iab-statement-to-ostp-on-privacy-enhancing-technologies/,
2022-11-21,IAB Comments on a notice by the Federal Trade Commission on “Trade Regulation Rule on Commercial Surveillance and Data Security” (16 CFR Part 464),https://www.iab.org/documents/correspondence-reports-documents/2022-2/iab-comments-on-a-notice-by-the-federal-trade-commission-on-trade-regulation-rule-on-commercial-surveillance-and-data-security-16-cfr-part-464/,
'''

    rows = []
    date_count = defaultdict(lambda: 0)
    with io.StringIO(csv_dump) as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            date = row[0]
            if date_count[date] == 0:
                row.insert(0, "")
            else:
                row.insert(0, date_count[date])
                date_count[date] += 1
            rows.append(row)
    return rows
