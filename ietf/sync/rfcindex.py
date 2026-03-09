# Copyright The IETF Trust 2026, All Rights Reserved
import json
from collections.abc import Container
from dataclasses import dataclass
from io import StringIO, BytesIO
from itertools import chain
from operator import attrgetter
from textwrap import fill
from xml.dom.minidom import parseString
from xml.etree import ElementTree

from django.core.files.storage import storages
from django.db import models
from django.db.models.functions import Substr, Cast
from django.template.loader import render_to_string
from django.utils import timezone

from ietf.doc.models import Document
from ietf.name.models import StdLevelName
from ietf.utils.log import log

FORMATS_FOR_INDEX = ["txt", "html", "pdf", "xml", "ps"]


def rfc_doi(rfc: Document):
    assert rfc.rfc_number is not None
    return f"10.17487/RFC{rfc.rfc_number:04d}"


def errata_url(rfc: Document):
    return f"https://www.rfc-editor.org/errata/rfc{rfc.rfc_number}"


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


def get_publication_std_levels() -> Container[int]:
    FILENAME = "publication-std-levels.json"
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
    return {
        record["number"]: StdLevelName.objects.get(slug=record["publication_std_level"])
        for record in records
    }


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
            published_at = rfc.pub_date()
            date = (
                published_at.strftime("1 %B %Y")
                if rfc.rfc_number in april1_rfc_numbers
                else published_at.strftime("%B %Y")
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
                    f"(DOI: {rfc_doi(rfc)})"
                ),
                width=73,
                subsequent_indent=" " * 5,
            )
            entries.append(entry)

    return entries


def add_subseries_xml_index_entries(rfc_index, ss_type, include_all=False):
    """Add subseries entries for rfc-index.xml"""
    # subseries docs annotated with numeric number
    ss_docs = list(
        Document.objects.filter(type_id=ss_type)
        .annotate(
            number=Cast(
                Substr("name", 4, None),
                output_field=models.IntegerField(),
            )
        )
        .order_by("-number")
    )
    if len(ss_docs) == 0:
        return  # very much not expected
    highest_number = ss_docs[0].number
    for ss_number in range(1, highest_number + 1):
        if ss_docs[-1].number == ss_number:
            this_ss_doc = ss_docs.pop()
            contained_rfcs = this_ss_doc.contains()
        else:
            contained_rfcs = []
        if len(contained_rfcs) == 0 and not include_all:
            continue
        entry = ElementTree.SubElement(rfc_index, f"{ss_type}-entry")
        ElementTree.SubElement(
            entry, "doc-id"
        ).text = f"{ss_type.upper()}{ss_number:04d}"
        if len(contained_rfcs) > 0:
            is_also = ElementTree.SubElement(entry, "is-also")
            for rfc in sorted(contained_rfcs, key=attrgetter("rfc_number")):
                ElementTree.SubElement(
                    is_also, "doc-id"
                ).text = f"RFC{rfc.rfc_number:04d}"


def add_rfc_not_be_xml_index_entries(rfc_index):
    """Add unusable RFC entries for rfc-index.xml"""
    entries = []

    for record in sorted(get_unusable_rfc_numbers(), key=attrgetter("rfc_number")):
        entry = ElementTree.SubElement(rfc_index, "rfc-not-issued-entry")
        ElementTree.SubElement(entry, "doc-id").text = f"RFC{record.rfc_number:04d}"
        entries.append(entry)


def add_rfc_xml_index_entries(rfc_index):
    """Add RFC entries for rfc-index.xml"""
    entries = []
    april1_rfc_numbers = get_april1_rfc_numbers()
    publication_statuses = get_publication_std_levels()

    published_rfcs = Document.objects.filter(type_id="rfc").order_by("rfc_number")

    for rfc in published_rfcs:
        entry = ElementTree.SubElement(rfc_index, "rfc-entry")

        ElementTree.SubElement(entry, "doc-id").text = f"RFC{rfc.rfc_number:04d}"
        ElementTree.SubElement(entry, "title").text = rfc.title

        for author in rfc.rfcauthor_set.all():
            author_element = ElementTree.SubElement(entry, "author")
            ElementTree.SubElement(author_element, "name").text = author.titlepage_name
            if author.is_editor:
                ElementTree.SubElement(author_element, "title").text = "Editor"

        date = ElementTree.SubElement(entry, "date")
        published_at = rfc.pub_date()
        ElementTree.SubElement(date, "month").text = published_at.strftime("%B")
        if rfc.rfc_number in april1_rfc_numbers:
            ElementTree.SubElement(date, "day").text = str(published_at.day)
        ElementTree.SubElement(date, "year").text = str(published_at.year)

        format_ = ElementTree.SubElement(entry, "format")
        fmts = [ff["fmt"] for ff in rfc.formats() if ff["fmt"] in FORMATS_FOR_INDEX]
        for fmt in sorted(fmts, key=format_ordering(rfc.rfc_number)):
            ElementTree.SubElement(format_, "file-format").text = (
                "ASCII" if fmt == "txt" else fmt.upper()
            )

        ElementTree.SubElement(entry, "page-count").text = str(rfc.pages)

        part_of_documents = rfc.part_of()
        if len(part_of_documents) > 0:
            is_also = ElementTree.SubElement(entry, "is-also")
            for doc in part_of_documents:
                ElementTree.SubElement(is_also, "doc-id").text = doc.name.upper()

        obsoletes_documents = sorted(
            rfc.related_that_doc("obs"),
            key=attrgetter("rfc_number"),
        )
        if len(obsoletes_documents) > 0:
            obsoletes = ElementTree.SubElement(entry, "obsoletes")
            for doc in obsoletes_documents:
                ElementTree.SubElement(
                    obsoletes, "doc-id"
                ).text = f"RFC{doc.rfc_number:04d}"

        updates_documents = sorted(
            rfc.related_that_doc("updates"),
            key=attrgetter("rfc_number"),
        )
        if len(updates_documents) > 0:
            updates = ElementTree.SubElement(entry, "updates")
            for doc in updates_documents:
                ElementTree.SubElement(
                    updates, "doc-id"
                ).text = f"RFC{doc.rfc_number:04d}"

        obsoleted_by_documents = sorted(
            rfc.related_that("obs"),
            key=attrgetter("rfc_number"),
        )
        if len(obsoleted_by_documents) > 0:
            obsoleted_by = ElementTree.SubElement(entry, "obsoleted-by")
            for doc in obsoleted_by_documents:
                ElementTree.SubElement(
                    obsoleted_by, "doc-id"
                ).text = f"RFC{doc.rfc_number:04d}"

        updated_by_documents = sorted(
            rfc.related_that("updates"),
            key=attrgetter("rfc_number"),
        )
        if len(updated_by_documents) > 0:
            updated_by = ElementTree.SubElement(entry, "updated-by")
            for doc in updated_by_documents:
                ElementTree.SubElement(
                    updated_by, "doc-id"
                ).text = f"RFC{doc.rfc_number:04d}"

        if len(rfc.keywords) > 0:
            keywords = ElementTree.SubElement(entry, "keywords")
            for keyword in rfc.keywords:
                ElementTree.SubElement(keywords, "kw").text = keyword.strip()

        if rfc.abstract:
            abstract_ = ElementTree.SubElement(entry, "abstract")
            ElementTree.SubElement(abstract_, "p").text = rfc.abstract

        draft = rfc.came_from_draft()
        if draft is not None:
            ElementTree.SubElement(entry, "draft").text = draft.name

        ElementTree.SubElement(
            entry, "current-status"
        ).text = rfc.std_level.name.upper()
        ElementTree.SubElement(entry, "publication-status").text = publication_statuses[
            rfc.rfc_number
        ].name.upper()
        ElementTree.SubElement(entry, "stream").text = (
            "INDEPENDENT" if rfc.stream_id == "ise" else rfc.stream.name
        )

        # Add area / wg_acronym
        if rfc.stream_id == "ietf":
            if rfc.group.acronym in ["none", "gen"]:
                ElementTree.SubElement(entry, "wg_acronym").text = "NON WORKING GROUP"
            else:
                if rfc.area is not None:
                    ElementTree.SubElement(entry, "area").text = rfc.area.acronym
                if rfc.group:
                    ElementTree.SubElement(entry, "wg_acronym").text = rfc.group.acronym

        if rfc.tags.filter(slug="errata").exists():
            ElementTree.SubElement(entry, "errata-url").text = errata_url(rfc)
        ElementTree.SubElement(entry, "doi").text = rfc_doi(rfc)
        entries.append(entry)


def create_rfc_txt_index():
    """Create text index of published documents"""
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
    red_bucket.save(filename, StringIO(index))
    log(f"Created {filename} in red_bucket storage")


def create_rfc_xml_index():
    """Create XML index of published documents"""
    log("Creating rfc-index.xml")
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
    add_subseries_xml_index_entries(rfc_index, "bcp", include_all=True)
    add_subseries_xml_index_entries(rfc_index, "fyi")
    add_rfc_not_be_xml_index_entries(rfc_index)
    add_rfc_xml_index_entries(rfc_index)
    add_subseries_xml_index_entries(rfc_index, "std")

    # make it pretty
    rough_index = parseString(ElementTree.tostring(rfc_index, encoding="UTF-8"))
    pretty_index = rough_index.toprettyxml(indent=" " * 4, encoding="UTF-8")
    red_bucket = storages["red_bucket"]
    filename = "rfc-index.xml"
    # Django 4.2's FileSystemStorage does not support allow_overwrite. We can drop
    # the delete() when we move to a Storage class that supports it.
    red_bucket.delete(filename)
    red_bucket.save(filename, BytesIO(pretty_index))
    log(f"Created {filename} in red_bucket storage")
