# Copyright The IETF Trust 2026, All Rights Reserved
from pathlib import Path
from urllib.parse import urljoin
from xml.sax.saxutils import quoteattr as qa

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import models
from django.db.models.functions import Substr, Cast
from lxml import etree

from ietf.doc.models import Document
from ietf.utils.log import log


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


def get_rfc_bibxml(rfc_number):
    """Return BibXML entry for the given rfc"""

    rfc = Document.objects.get(rfc_number=rfc_number)
    link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"rfc{rfc_number}")
    date = rfc.pub_date().strftime('<date month="%B" year="%Y"/>')
    authors = ""

    for author in rfc.rfcauthor_set.all():
        if author.is_editor:
            author_entry = f"""<author fullname={qa(author.titlepage_name)} surname={qa(author.titlepage_name.split(".")[-1].strip())} role="editor"/>"""
        else:
            author_entry = f"""<author fullname={qa(author.titlepage_name)} surname={qa(author.titlepage_name.split(".")[-1].strip())}/>"""
        authors += author_entry

    return f"""<reference anchor="RFC{rfc_number}" target="{link}"><front><title>{rfc.title}</title>{date}{authors}<abstract><t>{rfc.abstract}</t></abstract></front><seriesInfo name="RFC" value="{rfc_number}"/><seriesInfo name="DOI" value="{rfc.doi}"/></reference>"""


def get_bcp_bibxml(bcp_number):
    """Return BibXML entry for the given bcp"""
    bcp = Document.objects.get(name=f"bcp{bcp_number}")
    bcp_link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"bcp{bcp_number}")
    rfc_bibxml = ""
    rfcs = sorted(bcp.contains(), key=lambda x: x.rfc_number)
    for rfc in rfcs:
        rfc_bibxml += get_rfc_bibxml(rfc.rfc_number)

    return f"""<referencegroup anchor="BCP{bcp_number}" target="{bcp_link}">{rfc_bibxml}</referencegroup>"""


def get_std_bibxml(std_number):
    """Return BibXML entry for the given std"""
    std = Document.objects.get(name=f"std{std_number}")
    std_link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"std{std_number}")
    rfc_bibxml = ""
    rfcs = sorted(std.contains(), key=lambda x: x.rfc_number)
    for rfc in rfcs:
        rfc_bibxml += get_rfc_bibxml(rfc.rfc_number)

    return f"""<referencegroup anchor="STD{std_number}" target="{std_link}">{rfc_bibxml}</referencegroup>"""


def get_fyi_bibxml(fyi_number):
    """Return BibXML entry for the given fyi"""
    fyi = Document.objects.get(name=f"fyi{fyi_number}")
    fyi_link = urljoin(settings.RFC_EDITOR_INFO_BASE_URL + "/", f"fyi{fyi_number}")
    rfc_bibxml = ""
    rfcs = sorted(fyi.contains(), key=lambda x: x.rfc_number)
    for rfc in rfcs:
        rfc_bibxml += get_rfc_bibxml(rfc.rfc_number)

    return f"""<referencegroup anchor="FYI{fyi_number}" target="{fyi_link}">{rfc_bibxml}</referencegroup>"""


def get_id_bibxml(draft_name, doc):
    """Return BibXML entry for the given I-D doc"""
    name = "-".join(draft_name.split("-", 2)[1:])
    date = ""
    if doc.is_dochistory():
        latest_event = doc.latest_event(type="new_revision", rev=doc.rev)
        if latest_event:
            doc.pub_date = latest_event.time
            date = doc.pub_date.strftime('<date day="%-d" month="%B" year="%Y"/>')
    else:
        date = doc.pub_date().strftime('<date day="%-d" month="%B" year="%Y"/>')
    link = f"https://datatracker.ietf.org/doc/html/{draft_name}-{doc.rev}"
    authors = ""
    for author in doc.author_persons_or_names():
        authors += f"""<author fullname={qa(author.person.name)} />"""

    return f"""<reference anchor="I-D.{name}" target="{link}"><front><title>{doc.title}</title>{date}{authors}<abstract><t>{doc.abstract}</t></abstract></front><seriesInfo name="Internet-Draft" value="{draft_name}-{doc.rev}"/></reference>"""


def save_bibxml(bibxml, filename):
    """Prettify and save given BibXML"""

    # make it pretty
    pretty_bibxml = etree.tostring(
        etree.fromstring(bibxml),
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=4,
    )
    save_to_bucket(filename, pretty_bibxml)


def recreate_rfc_bibxml():
    """Creates BibXML for all RFCs."""
    for rfc_number in Document.objects.filter(type_id="rfc").values_list(
        "rfc_number", flat=True
    ):
        filename = f"bibxml/rfc{rfc_number}.xml"
        bibxml = get_rfc_bibxml(rfc_number)
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
        filename = f"bibxml-rfcsubseries/bcp{bcp_number}.xml"
        bibxml = get_bcp_bibxml(bcp_number)
        save_bibxml(bibxml, filename)

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
        bibxml = get_std_bibxml(std_number)
        save_bibxml(bibxml, filename)

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
        bibxml = get_fyi_bibxml(fyi_number)
        save_bibxml(bibxml, filename)


def recreate_id_bibxml_by_draft_name(draft_name):
    """Creates BibXML for given draft_name."""
    doc = Document.objects.get(name=draft_name)
    name = "-".join(draft_name.split("-", 2)[1:])

    # revision less BibXML
    bibxml = get_id_bibxml(draft_name, doc)
    filename = f"bibxml-ids/reference.I-D.{name}.xml"
    save_bibxml(bibxml, filename)

    # draft BibXML for each revision
    for revision in reversed(doc.revisions_by_newrevisionevent()):
        doc_rev = doc.history_set.order_by("-time").filter(rev=revision).first()
        bibxml = get_id_bibxml(draft_name, doc_rev)
        filename = f"bibxml-ids/reference.I-D.{draft_name}.xml"
        save_bibxml(bibxml, filename)


def recreate_id_bibxml():
    """Creates BibXML for all Internet Drafts."""
    for draft_name in (
        Document.objects.filter(type_id="draft")
        .values_list("name", flat=True)
        .order_by("-time")
    ):
        recreate_id_bibxml_by_draft_name(draft_name)
