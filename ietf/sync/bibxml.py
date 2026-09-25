# Copyright The IETF Trust 2026, All Rights Reserved
import re
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import escape as esc
from xml.sax.saxutils import quoteattr as qa

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import models
from django.db.models.functions import Cast, Substr
from lxml import etree

from ietf.doc.models import Document
from ietf.utils.log import log

ORG_LOOKUP = {
    # Format: {"lookup string" : ("abbrev", "display name")}
    "ISO": ("ISO", "International Organization for Standardization"),
    "IAB": ("IAB", "Internet Architecture Board"),
    "IESG": ("IESG", "Internet Engineering Steering Group"),
    "IANA": (None, "IANA"),
    "International Organization for Standardization": (
        "ISO",
        "International Organization for Standardization",
    ),
    "Federal Networking Council": ("FNC", "Federal Networking Council"),
    "Internet Architecture Board": ("IAB", "Internet Architecture Board"),
    "Internet Activities Board": ("IAB", "Internet Activities Board"),
    "Defense Advanced Research Projects Agency": (
        "DARPA",
        "Defense Advanced Research Projects Agency",
    ),
    "National Science Foundation": ("NSF", "National Science Foundation"),
    "National Research Council": ("NRC", "National Research Council"),
    "National Bureau of Standards": ("NBS", "National Bureau of Standards"),
    "Internet Engineering Steering Group": (
        "IESG",
        "Internet Engineering Steering Group",
    ),
    "IETF Secretariat": ("IETF", "IETF Secretariat"),
    "Internet Assigned Numbers Authority (IANA)": (
        None,
        "IANA",
    ),
    "ESnet Site Coordinating Comittee (ESCC)": (
        "ESCC",
        "ESnet Site Coordinating Comittee (ESCC)",
    ),
    "Energy Sciences Network (ESnet)": ("ESnet", "Energy Sciences Network (ESnet)"),
    "International Telegraph and Telephone Consultative Committee of the International Telecommunication Union": (
        "CCITT",
        "International Telegraph and Telephone Consultative Committee of the International Telecommunication Union",
    ),
    "Audio-Video Transport Working Group": (
        None,
        "Audio-Video Transport Working Group",
    ),
    "EARN Staff": (None, "EARN Staff"),
    "Vietnamese Standardization Working Group": (
        None,
        "Vietnamese Standardization Working Group",
    ),
    "ACM SIGUCCS": (None, "ACM SIGUCCS"),
    "ESCC X.500/X.400 Task Force": (None, "ESCC X.500/X.400 Task Force"),
    "Sun Microsystems": (None, "Sun Microsystems"),
    "NetBIOS Working Group in the Defense Advanced Research Projects Agency": (
        None,
        "NetBIOS Working Group in the Defense Advanced Research Projects Agency",
    ),
    "End-to-End Services Task Force": (None, "End-to-End Services Task Force"),
    "Network Technical Advisory Group": (None, "Network Technical Advisory Group"),
    "Bolt Beranek": (None, "Bolt Beranek"),
    "Bolt Beranek and Newman Laboratories": (
        None,
        "Bolt Beranek and Newman Laboratories",
    ),
    "Newman Laboratories": (None, "Newman Laboratories"),
    "Gateway Algorithms and Data Structures Task Force": (
        None,
        "Gateway Algorithms and Data Structures Task Force",
    ),
    "Network Information Center. Stanford Research Institute": (
        None,
        "Network Information Center. Stanford Research Institute",
    ),
    "RFC Editor": (None, "RFC Editor"),
    "Information Sciences Institute University of Southern California": (
        None,
        "Information Sciences Institute University of Southern California",
    ),
    "IAB and IESG": (None, "IAB and IESG"),
    "RARE WG-MSG Task Force 88": (None, "RARE WG-MSG Task Force 88"),
    "KOI8-U Working Group": (None, "KOI8-U Working Group"),
    "The Internet Society": (None, "The Internet Society"),
    "IAB Advisory Committee": (None, "IAB Advisory Committee"),
    "ISOC Board of Trustees": (None, "ISOC Board of Trustees"),
    "RFC Editor, et al.": (None, "RFC Editor, et al."),
    "North American Directory Forum": (None, "North American Directory Forum"),
    "The North American Directory Forum": (None, "The North American Directory Forum"),
}


CHUNK = r"(?:[A-Z]|\([A-Z]+\))+"
PARENY = r"[A-Z]*(?:\([A-Z]+\)[A-Z]*)+"
DOTTED = rf"(?:{CHUNK}-)*{CHUNK}\."
BARE = rf"(?:{PARENY}|[A-Z]+)(?=[-\s])"
INITIAL = rf"(?:{DOTTED}|{BARE})"

NAME_RE = re.compile(rf"^\s*(?P<initials>(?:{INITIAL}[-\s]*)*)(?P<surname>.*?)\s*$")


class BibXMLException(Exception):
    pass


def save_to_bucket(filename: str, content: str | bytes):
    bibxml_bucket = storages["bibxml_bucket"]
    bucket_path = str(Path(getattr(settings, "BIBXML_OUTPUT_PATH", "")) / filename)
    if getattr(settings, "BIBXML_DELETE_THEN_WRITE", True):
        # Django 4.2's FileSystemStorage does not support allow_overwrite.
        bibxml_bucket.delete(bucket_path)
    bibxml_bucket.save(
        bucket_path,
        ContentFile(content if isinstance(content, bytes) else content.encode("utf-8")),
    )
    log(f"Saved {bucket_path} in bibxml_bucket storage")


def get_abstract_bibxml(abstract):
    """Return BibXML abstract for the given abstract text

    Abstracts as stored separate paragraphs with a blank line and sentences with
    two spaces. BibXML has no use for either: each paragraph becomes its own
    <t>, and the whitespace within a paragraph collapses to single spaces.

    An RFC with no abstract gets no <abstract> element at all -- an empty one
    would not be valid BibXML, which requires at least one <t>.
    """
    paragraphs = [
        " ".join(paragraph.split()) for paragraph in re.split(r"\n\s*\n", abstract)
    ]
    ts = "".join(f"<t>{esc(paragraph)}</t>" for paragraph in paragraphs if paragraph)
    return f"""<abstract>{ts}</abstract>""" if ts else ""


def get_rfc_bibxml(rfc):
    """Return BibXML entry for the given rfc Document object"""

    rfc_number = rfc.rfc_number
    link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"rfc{rfc_number}")
    date = rfc.pub_date().strftime('<date month="%B" year="%Y"/>')
    authors = ""
    subseries_info = ""

    for author in rfc.rfcauthor_set.all():
        if author.titlepage_name in ORG_LOOKUP:
            # Author is an organization
            abbrev, name = ORG_LOOKUP[author.titlepage_name]
            if abbrev:
                author_entry = f"""<author><organization abbrev={qa(abbrev)}>{esc(name)}</organization></author>"""
            else:
                author_entry = (
                    f"""<author><organization>{esc(name)}</organization></author>"""
                )
        else:
            try:
                name_parts = NAME_RE.match(author.titlepage_name)
                initials = name_parts["initials"].strip()
                surname = name_parts["surname"]
                initials_attr = ""
                if initials:
                    initials_attr = f"initials={qa(initials)}"
                if author.is_editor:
                    author_entry = f"""<author fullname={qa(author.titlepage_name)} {initials_attr} surname={qa(surname)} role="editor"/>"""
                else:
                    author_entry = f"""<author fullname={qa(author.titlepage_name)} {initials_attr} surname={qa(surname)}/>"""
            except ValueError:
                # Case where author has single name.
                author_entry = f"""<author fullname={qa(author.titlepage_name)} />"""
        authors += author_entry

    for subseries in rfc.part_of():
        subseries_info += f"""<seriesInfo name="{subseries.type_id.upper()}" value="{subseries.name[3:]}"/>"""

    return f"""<reference anchor="RFC{rfc_number}" target="{link}"><front><title>{esc(rfc.title)}</title>{authors}{date}{get_abstract_bibxml(rfc.abstract)}</front>{subseries_info}<seriesInfo name="RFC" value="{rfc_number}"/><seriesInfo name="DOI" value="{rfc.doi}"/></reference>"""


def get_bcp_bibxml(bcp_number):
    """Return BibXML entry for the given bcp"""
    bcp = Document.objects.get(type_id="bcp", name=f"bcp{bcp_number}")
    bcp_link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"bcp{bcp_number}")
    rfc_bibxml = ""
    rfcs = sorted(bcp.contains(), key=lambda x: x.rfc_number)
    if not rfcs:
        raise BibXMLException(f"No RFCs found for BCP {bcp_number}.")
    for rfc in rfcs:
        rfc_bibxml += get_rfc_bibxml(rfc)

    return f"""<referencegroup anchor="BCP{bcp_number}" target="{bcp_link}">{rfc_bibxml}</referencegroup>"""


def get_std_bibxml(std_number):
    """Return BibXML entry for the given std"""
    std = Document.objects.get(type_id="std", name=f"std{std_number}")
    std_link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"std{std_number}")
    rfc_bibxml = ""
    rfcs = sorted(std.contains(), key=lambda x: x.rfc_number)
    if not rfcs:
        raise BibXMLException(f"No RFCs found for STD {std_number}.")
    for rfc in rfcs:
        rfc_bibxml += get_rfc_bibxml(rfc)

    return f"""<referencegroup anchor="STD{std_number}" target="{std_link}">{rfc_bibxml}</referencegroup>"""


def get_fyi_bibxml(fyi_number):
    """Return BibXML entry for the given fyi"""
    fyi = Document.objects.get(type_id="fyi", name=f"fyi{fyi_number}")
    fyi_link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"fyi{fyi_number}")
    rfc_bibxml = ""
    rfcs = sorted(fyi.contains(), key=lambda x: x.rfc_number)
    if not rfcs:
        raise BibXMLException(f"No RFCs found for FYI {fyi_number}.")
    for rfc in rfcs:
        rfc_bibxml += get_rfc_bibxml(rfc)

    return f"""<referencegroup anchor="FYI{fyi_number}" target="{fyi_link}">{rfc_bibxml}</referencegroup>"""


def save_bibxml(bibxml, filename):
    """Prettify and save given BibXML"""

    # make it pretty
    pretty_bibxml = etree.tostring(
        etree.fromstring(bibxml),
        encoding="utf-8",
        xml_declaration=False,
        pretty_print=4,
    )
    save_to_bucket(filename, pretty_bibxml)


def recreate_rfc_bibxml():
    """Creates BibXML for all RFCs."""
    for rfc in Document.objects.filter(type_id="rfc"):
        rfc_number = rfc.rfc_number
        filename = f"bibxml/rfc{rfc_number}.xml"
        bibxml = get_rfc_bibxml(rfc)
        save_bibxml(bibxml, filename)


def recreate_rfcsubseries_bibxml():
    """Creates BibXML for all RFC subseries."""
    # BCPs
    bcps = (
        Document.objects.filter(type_id="bcp")
        .annotate(
            number=Cast(
                Substr("name", 4, None),
                output_field=models.IntegerField(),
            )
        )
        .order_by("-number")
        .values_list("number", flat=True)
    )
    for bcp_number in bcps:
        try:
            filename = f"bibxml-rfcsubseries/bcp{bcp_number}.xml"
            bibxml = get_bcp_bibxml(bcp_number)
            save_bibxml(bibxml, filename)
        except BibXMLException as e:
            log(f"{e}")
    # STDs
    stds = (
        Document.objects.filter(type_id="std")
        .annotate(
            number=Cast(
                Substr("name", 4, None),
                output_field=models.IntegerField(),
            )
        )
        .order_by("-number")
        .values_list("number", flat=True)
    )
    for std_number in stds:
        filename = f"bibxml-rfcsubseries/std{std_number}.xml"
        try:
            bibxml = get_std_bibxml(std_number)
            save_bibxml(bibxml, filename)
        except BibXMLException as e:
            log(f"{e}")

    # FYIs
    fyis = (
        Document.objects.filter(type_id="fyi")
        .annotate(
            number=Cast(
                Substr("name", 4, None),
                output_field=models.IntegerField(),
            )
        )
        .order_by("-number")
        .values_list("number", flat=True)
    )
    for fyi_number in fyis:
        filename = f"bibxml-rfcsubseries/fyi{fyi_number}.xml"
        try:
            bibxml = get_fyi_bibxml(fyi_number)
            save_bibxml(bibxml, filename)
        except BibXMLException as e:
            log(f"{e}")
