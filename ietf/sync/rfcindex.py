# Copyright The IETF Trust 2026, All Rights Reserved
import json
from collections.abc import Container
from dataclasses import dataclass
from io import StringIO
from itertools import chain
from operator import attrgetter
from textwrap import fill
from xml.dom.minidom import parseString
from xml.etree import ElementTree

from django.conf import settings
from django.core.files.storage import storages
from django.template.loader import render_to_string
from django.utils import timezone

from ietf.doc.models import Document
from ietf.utils.log import log

FORMATS_FOR_INDEX = ["txt", "html", "pdf", "xml", "ps"]


def render_doi(rfc: Document):
    assert rfc.rfc_number is not None
    return f"10.17487/RFC{rfc.rfc_number:04d}"


@dataclass
class UnusableRfcNumber:
    rfc_number: int
    comment: str


def get_unusable_rfc_numbers() -> list[UnusableRfcNumber]:
    FILENAME = "unusable-rfc-numbers.json"
    try:
        with storages["red_bucket"].open(FILENAME) as urn_file:
            records = json.load(urn_file)
    except FileNotFoundError:
        log(f"Error: unable to open {FILENAME} in red_bucket storage")
        return []
    except json.JSONDecodeError:
        log(f"Error: unable to parse {FILENAME} in red_bucket storage")
        return []
    assert all(isinstance(record["number"], int) for record in records)
    assert all(isinstance(record["comment"], str) for record in records)
    return [
        UnusableRfcNumber(rfc_number=record["number"], comment=record["comment"])
        for record in records
    ]


def get_april1_rfc_numbers() -> Container[int]:
    FILENAME = "april-first-rfc-numbers.json"
    try:
        with storages["red_bucket"].open(FILENAME) as urn_file:
            records = json.load(urn_file)
    except FileNotFoundError:
        log(f"Error: unable to open {FILENAME} in red_bucket storage")
        return []
    except json.JSONDecodeError:
        log(f"Error: unable to parse {FILENAME} in red_bucket storage")
        return []
    assert all(isinstance(record, int) for record in records)
    return records


def format_ordering(rfc_number):
    if rfc_number < 8650:
        ordering = ["txt", "ps", "pdf", "html", "xml"]
    else:
        ordering = ["html", "txt", "ps", "pdf", "xml"]
    return ordering.index  # return the method


def get_rfc_text_index_entries():
    """Returns RFC entries for rfc-index.txt"""
    entries = []
    april1_rfc_numbers = get_april1_rfc_numbers()
    published_rfcs = Document.objects.filter(type_id="rfc").order_by("rfc_number")
    rfcs = sorted(
        chain(published_rfcs, get_unusable_rfc_numbers()), key=attrgetter("rfc_number")
    )
    for rfc in rfcs:
        if isinstance(rfc, UnusableRfcNumber):
            entries.append(f"{rfc.rfc_number:04d} Not Issued.")
        else:
            assert isinstance(rfc, Document)
            authors = ", ".join(
                author.format_for_titlepage() for author in rfc.rfcauthor_set.all()
            )
            date = (
                rfc.pub_date().strftime("1 %B %Y")
                if rfc.rfc_number in april1_rfc_numbers
                else rfc.pub_date().strftime("%B %Y")
            )

            # formats
            formats = ", ".join(
                sorted(
                    [
                        format["fmt"]
                        for format in rfc.formats()
                        if format["fmt"] in FORMATS_FOR_INDEX
                    ],
                    key=format_ordering(rfc.rfc_number),
                )
            ).upper()

            # obsoletes
            obsoletes = ""
            obsoletes_documents = sorted(
                rfc.related_that_doc("obs"),
                key=attrgetter("rfc_number"),
            )
            if len(obsoletes_documents) > 0:
                obsoletes_names = ", ".join(
                    f"RFC{doc.rfc_number:04d}" for doc in obsoletes_documents
                )
                obsoletes = f" (Obsoletes {obsoletes_names})"

            # obsoleted by
            obsoleted_by = ""
            obsoleted_by_documents = sorted(
                rfc.related_that("obs"),
                key=attrgetter("rfc_number"),
            )
            if len(obsoleted_by_documents) > 0:
                obsoleted_by_names = ", ".join(
                    f"RFC{doc.rfc_number:04d}" for doc in obsoleted_by_documents
                )
                obsoleted_by = f" (Obsoleted by {obsoleted_by_names})"

            # updates
            updates = ""
            updates_documents = sorted(
                rfc.related_that_doc("updates"),
                key=attrgetter("rfc_number"),
            )
            if len(updates_documents) > 0:
                updates_names = ", ".join(
                    f"RFC{doc.rfc_number:04d}" for doc in updates_documents
                )
                updates = f" (Updates {updates_names})"

            # updated by
            updated_by = ""
            updated_by_documents = sorted(
                rfc.related_that("updates"),
                key=attrgetter("rfc_number"),
            )
            if len(updated_by_documents) > 0:
                updated_by_names = ", ".join(
                    f"RFC{doc.rfc_number:04d}" for doc in updated_by_documents
                )
                updated_by = f" (Updated by {updated_by_names})"

            doc_relations = f"{obsoletes}{obsoleted_by}{updates}{updated_by} "

            # subseries
            subseries = ",".join(
                f"{container.type.slug}{int(container.name[3:]):04d}"
                for container in rfc.part_of()
            ).upper()
            if subseries:
                subseries = f"(Also {subseries}) "

            entry = fill(
                (
                    f"{rfc.rfc_number:04d} {rfc.title}. {authors}. {date}. "
                    f"(Format: {formats}){doc_relations}{subseries}"
                    f"(Status: {str(rfc.std_level).upper()}) "
                    f"(DOI: {render_doi(rfc)})"
                ),
                width=73,
                subsequent_indent=" " * 5,
            )
            entries.append(entry)

    return entries


def add_bcp_xml_index_entries(rfc_index):
    """Add BCP entries for rfc-index.xml"""
    entries = []

    highest_bcp_number = (
        SubseriesMember.objects.filter(type_id="bcp").order_by("-number").first().number
    )

    for bcp_number in range(1, highest_bcp_number):
        entry = ElementTree.SubElement(rfc_index, "bcp-entry")
        ElementTree.SubElement(entry, "doc-id").text = f"BCP{bcp_number}"

        subseries_members = SubseriesMember.objects.filter(
            type_id="bcp", number=bcp_number
        )
        if subseries_members:
            is_also = ElementTree.SubElement(entry, "is-also")

            for bcp_entry in subseries_members:
                ElementTree.SubElement(
                    is_also, "doc-id"
                ).text = f"RFC{bcp_entry.rfc_to_be.rfc_number}"

        entries.append(entry)


def add_fyi_xml_index_entries(rfc_index):
    """Add FYI entries for rfc-index.xml"""
    entries = []

    published_fyis = (
        SubseriesMember.objects.filter(type_id="fyi").order_by("number").distinct()
    )

    for fyi in published_fyis:
        entry = ElementTree.SubElement(rfc_index, "fyi-entry")
        ElementTree.SubElement(entry, "doc-id").text = f"FYI{fyi.number}"
        is_also = ElementTree.SubElement(entry, "is-also")

        for fyi_entry in SubseriesMember.objects.filter(
            type_id="fyi", number=fyi.number
        ):
            ElementTree.SubElement(
                is_also, "doc-id"
            ).text = f"RFC{fyi_entry.rfc_to_be.rfc_number}"

        entries.append(entry)


def add_std_xml_index_entries(rfc_index):
    """Add std entries for rfc-index.xml"""
    entries = []

    published_stds = (
        SubseriesMember.objects.filter(type_id="std").order_by("number").distinct()
    )

    for std in published_stds:
        entry = ElementTree.SubElement(rfc_index, "std-entry")
        ElementTree.SubElement(entry, "doc-id").text = f"STD{std.number}"
        is_also = ElementTree.SubElement(entry, "is-also")

        for std_entry in SubseriesMember.objects.filter(
            type_id="std", number=std.number
        ):
            ElementTree.SubElement(
                is_also, "doc-id"
            ).text = f"RFC{std_entry.rfc_to_be.rfc_number}"

        entries.append(entry)


def add_rfc_not_be_xml_index_entries(rfc_index):
    """Add unusable RFC entries for rfc-index.xml"""
    entries = []

    for record in UnusableRfcNumber.objects.order_by("number"):
        entry = ElementTree.SubElement(rfc_index, "rfc-not-issued-entry")
        ElementTree.SubElement(entry, "doc-id").text = f"RFC{record.number}"
        entries.append(entry)


def add_rfc_xml_index_entries(rfc_index):
    """Add RFC entries for rfc-index.xml"""
    entries = []

    published_rfcs = RfcToBe.objects.filter(published_at__isnull=False).order_by(
        "rfc_number"
    )
    for rfc in published_rfcs:
        entry = ElementTree.SubElement(rfc_index, "rfc-entry")

        ElementTree.SubElement(entry, "doc-id").text = f"RFC{rfc.rfc_number}"
        ElementTree.SubElement(entry, "title").text = rfc.title

        for author in rfc.authors.all():
            author_element = ElementTree.SubElement(entry, "author")
            ElementTree.SubElement(author_element, "name").text = author.titlepage_name
            if author.is_editor:
                ElementTree.SubElement(author_element, "title").text = "Editor"

        date = ElementTree.SubElement(entry, "date")
        ElementTree.SubElement(date, "month").text = rfc.published_at.strftime("%B")
        if rfc.is_april_first_rfc:
            ElementTree.SubElement(date, "day").text = str(rfc.published_at.day)
        ElementTree.SubElement(date, "year").text = str(rfc.published_at.year)

        format = ElementTree.SubElement(entry, "format")
        for file_format in rfc.published_formats.filter(
            slug__in=FORMATS_FOR_INDEX
        ).values_list("slug", flat=True):
            ElementTree.SubElement(format, "file-format").text = file_format.upper()

        ElementTree.SubElement(entry, "page-count").text = str(rfc.pages)

        if rfc.obsoletes:
            obsoletes = ElementTree.SubElement(entry, "obsoletes")
            for rfc_number in rfc.obsoletes.values_list(
                "rfc_number", flat=True
            ).order_by("rfc_number"):
                ElementTree.SubElement(obsoletes, "doc-id").text = f"RFC{rfc_number}"

        if rfc.updates:
            updates = ElementTree.SubElement(entry, "updates")
            for rfc_number in rfc.updates.values_list("rfc_number", flat=True).order_by(
                "rfc_number"
            ):
                ElementTree.SubElement(updates, "doc-id").text = f"RFC{rfc_number}"

        if rfc.obsoleted_by:
            obsoleted_by = ElementTree.SubElement(entry, "obsoleted-by")
            for rfc_number in rfc.obsoleted_by.values_list(
                "rfc_number", flat=True
            ).order_by("rfc_number"):
                ElementTree.SubElement(obsoleted_by, "doc-id").text = f"RFC{rfc_number}"

        if rfc.updated_by:
            updated_by = ElementTree.SubElement(entry, "updated-by")
            for rfc_number in rfc.updated_by.values_list(
                "rfc_number", flat=True
            ).order_by("rfc_number"):
                ElementTree.SubElement(updated_by, "doc-id").text = f"RFC{rfc_number}"

        if rfc.keywords.strip():
            keywords = ElementTree.SubElement(entry, "keywords")
            for keyword in rfc.keywords.strip().split(","):
                ElementTree.SubElement(keywords, "kw").text = keyword.strip()

        if rfc.abstract:
            abstract = ElementTree.SubElement(entry, "abstract")
            ElementTree.SubElement(abstract, "p").text = rfc.abstract

        if rfc.draft:
            ElementTree.SubElement(entry, "draft").text = str(rfc.draft)

        ElementTree.SubElement(entry, "current-status").text = str(
            rfc.std_level
        ).upper()
        ElementTree.SubElement(entry, "publication-status").text = str(
            rfc.publication_std_level
        ).upper()
        ElementTree.SubElement(entry, "stream").text = str(rfc.stream)

        if rfc.area:
            ElementTree.SubElement(entry, "area").text = str(rfc.area)

        if rfc.group:
            ElementTree.SubElement(entry, "wg_acronym").text = str(rfc.group)

        ElementTree.SubElement(
            entry, "errata-url"
        ).text = f"{settings.ERRATA_URL}/rfc{rfc.rfc_number}"
        ElementTree.SubElement(
            entry, "doi"
        ).text = f"{settings.DOI_PREFIX}/RFC{rfc.rfc_number:04d}"
        entries.append(entry)


def create_rfc_txt_index():
    """
    Create text index of published documents
    """
    DATE_FMT = "%m/%d/%Y"
    created_on = timezone.now().strftime(DATE_FMT)
    log("Creating rfc-index.txt")
    index = render_to_string(
        "sync/rfc-index.txt",
        {
            "created_on": created_on,
            "rfcs": get_rfc_text_index_entries(),
        },
    )
    red_bucket = storages["red_bucket"]
    filename = "rfc-index.txt"
    # Django 4.2's FileSystemStorage does not support allow_overwrite. We can drop
    # the delete() when we move to a Storage class that supports it.
    red_bucket.delete(filename)
    red_bucket.save("rfc-index.txt", StringIO(index))
    log("Created rfc-index.txt in red_bucket storage")


def createRfcXmlIndex():
    """
    Create XML index of published documents
    """
    logger.info("Creating rfc-index.xml")
    rfc_index = ElementTree.Element(
        "rfc-index",
        attrib={
            "xmlns": "https://www.rfc-editor.org/rfc-index",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "https://www.rfc-editor.org/rfc-index "
                "https://www.rfc-editor.org/rfc-index.xsd"
            ),
        },
    )

    # add data
    add_bcp_xml_index_entries(rfc_index)
    add_fyi_xml_index_entries(rfc_index)
    add_rfc_not_be_xml_index_entries(rfc_index)
    add_rfc_xml_index_entries(rfc_index)
    add_std_xml_index_entries(rfc_index)

    # make it pretty
    rough_index = parseString(ElementTree.tostring(rfc_index, encoding="UTF-8"))
    pretty_index = rough_index.toprettyxml(indent=" " * 4, encoding="UTF-8")
    print(pretty_index.decode())  # TODO: Write to a blob store
    logger.info("Created rfc-index.xml")
