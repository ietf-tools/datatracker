# Copyright The IETF Trust 2026, All Rights Reserved
import json
from collections import defaultdict
from collections.abc import Container
from dataclasses import dataclass
from itertools import chain
from operator import attrgetter, itemgetter
from pathlib import Path
from textwrap import fill
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from lxml import etree

from django.core.files.storage import storages
from django.db import models
from django.db.models.functions import Substr, Cast
from django.template.loader import render_to_string
from django.utils import timezone

from ietf.doc.models import Document
from ietf.name.models import StdLevelName
from ietf.utils.log import log

FORMATS_FOR_INDEX = ["txt", "html", "pdf", "xml", "ps"]
SS_TXT_MARGIN = 3
SS_TXT_CUE_COL_WIDTH = 14


def format_rfc_number(n):
    """Format an RFC number (or subseries doc number)

    Set settings.RFCINDEX_MATCH_LEGACY_XML=True for the legacy (leading-zero) format.
    That is for debugging only - tests will fail.
    """
    if getattr(settings, "RFCINDEX_MATCH_LEGACY_XML", False):
        return format(n, "04")
    else:
        return format(n)


def errata_url(rfc: Document):
    return urljoin(settings.RFC_EDITOR_ERRATA_BASE_URL + "/", f"rfc{rfc.rfc_number}")


def save_to_red_bucket(filename: str, content: str | bytes):
    red_bucket = storages["red_bucket"]
    bucket_path = str(Path(getattr(settings, "RFCINDEX_OUTPUT_PATH", "")) / filename)
    if getattr(settings, "RFCINDEX_DELETE_THEN_WRITE", True):
        # Django 4.2's FileSystemStorage does not support allow_overwrite.
        red_bucket.delete(bucket_path)
    red_bucket.save(
        bucket_path,
        ContentFile(content if isinstance(content, bytes) else content.encode("utf-8")),
    )
    log(f"Saved {bucket_path} in red_bucket storage")


@dataclass
class UnusableRfcNumber:
    rfc_number: int
    comment: str


def get_unusable_rfc_numbers() -> list[UnusableRfcNumber]:
    FILENAME = "unusable-rfc-numbers.json"
    bucket_path = str(Path(getattr(settings, "RFCINDEX_INPUT_PATH", "")) / FILENAME)
    try:
        with storages["red_bucket"].open(bucket_path) as urn_file:
            records = json.load(urn_file)
    except FileNotFoundError:
        if settings.SERVER_MODE == "development":
            log(
                f"Unable to open {bucket_path} in red_bucket storage. This is okay in dev "
                "but generated rfc-index will not agree with RFC Editor values."
            )  # pragma: no cover
            return []  # pragma: no cover
        log(f"Error: unable to open {bucket_path} in red_bucket storage")
        raise
    except json.JSONDecodeError:
        log(f"Error: unable to parse {bucket_path} in red_bucket storage")
        if settings.SERVER_MODE == "development":
            return []  # pragma: no cover
        raise
    assert all(isinstance(record["number"], int) for record in records)
    assert all(isinstance(record["comment"], str) for record in records)
    return [
        UnusableRfcNumber(rfc_number=record["number"], comment=record["comment"])
        for record in sorted(records, key=itemgetter("number"))
    ]


def get_april1_rfc_numbers() -> Container[int]:
    FILENAME = "april-first-rfc-numbers.json"
    bucket_path = str(Path(getattr(settings, "RFCINDEX_INPUT_PATH", "")) / FILENAME)
    try:
        with storages["red_bucket"].open(bucket_path) as urn_file:
            records = json.load(urn_file)
    except FileNotFoundError:
        if settings.SERVER_MODE == "development":
            log(
                f"Unable to open {bucket_path} in red_bucket storage. This is okay in dev "
                "but generated rfc-index will not agree with RFC Editor values."
            )  # pragma: no cover
            return []  # pragma: no cover
        log(f"Error: unable to open {bucket_path} in red_bucket storage")
        raise
    except json.JSONDecodeError:
        log(f"Error: unable to parse {bucket_path} in red_bucket storage")
        if settings.SERVER_MODE == "development":
            return []  # pragma: no cover
        raise
    assert all(isinstance(record, int) for record in records)
    return records


def get_publication_std_levels() -> dict[int, StdLevelName]:
    FILENAME = "publication-std-levels.json"
    bucket_path = str(Path(getattr(settings, "RFCINDEX_INPUT_PATH", "")) / FILENAME)
    values: dict[int, StdLevelName] = {}
    try:
        with storages["red_bucket"].open(bucket_path) as urn_file:
            records = json.load(urn_file)
    except FileNotFoundError:
        if settings.SERVER_MODE == "development":
            log(
                f"Unable to open {bucket_path} in red_bucket storage. This is okay in dev "
                "but generated rfc-index will not agree with RFC Editor values."
            )  # pragma: no cover
            # intentionally fall through instead of return here
        else:
            log(f"Error: unable to open {bucket_path} in red_bucket storage")
            raise
    except json.JSONDecodeError:
        log(f"Error: unable to parse {bucket_path} in red_bucket storage")
        if settings.SERVER_MODE != "development":
            raise
    else:
        assert all(isinstance(record["number"], int) for record in records)
        values = {
            record["number"]: StdLevelName.objects.get(
                slug=record["publication_std_level"]
            )
            for record in records
        }
    # defaultdict to return "unknown" for any missing values
    unknown_std_level = StdLevelName.objects.get(slug="unkn")
    return defaultdict(lambda: unknown_std_level, values)


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
            entries.append(f"{format_rfc_number(rfc.rfc_number)} Not Issued.")
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
                    f"RFC{format_rfc_number(doc.rfc_number)}"
                    for doc in obsoletes_documents
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
                    f"RFC{format_rfc_number(doc.rfc_number)}"
                    for doc in obsoleted_by_documents
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
                    f"RFC{format_rfc_number(doc.rfc_number)}"
                    for doc in updates_documents
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
                    f"RFC{format_rfc_number(doc.rfc_number)}"
                    for doc in updated_by_documents
                )
                updated_by = f" (Updated by {updated_by_names})"

            doc_relations = f"{obsoletes}{obsoleted_by}{updates}{updated_by} "

            # subseries
            subseries = ",".join(
                f"{container.type.slug}{format_rfc_number(int(container.name[3:]))}"
                for container in rfc.part_of()
            ).upper()
            if subseries:
                subseries = f"(Also {subseries}) "

            entry = fill(
                (
                    f"{format_rfc_number(rfc.rfc_number)} {rfc.title}. {authors}. {date}. "
                    f"(Format: {formats}){doc_relations}{subseries}"
                    f"(Status: {str(rfc.std_level).upper()}) "
                    f"(DOI: {rfc.doi})"
                ),
                width=73,
                subsequent_indent=" " * 5,
            )
            entries.append(entry)

    return entries


def subseries_text_line(line, first=False):
    """Return subseries text entry line"""
    indent = " " * SS_TXT_CUE_COL_WIDTH
    if first:
        initial_indent = " " * SS_TXT_MARGIN
    else:
        initial_indent = indent
    return fill(
        line,
        initial_indent=initial_indent,
        subsequent_indent=indent,
        width=80,
        break_on_hyphens=False,
    )


def get_bcp_text_index_entries():
    """Returns BCP entries for bcp-index.txt"""
    entries = []

    highest_bcp_number = (
        Document.objects.filter(type_id="bcp")
        .annotate(
            number=Cast(
                Substr("name", 4, None),
                output_field=models.IntegerField(),
            )
        )
        .order_by("-number")
        .first()
        .number
    )

    for bcp_number in range(1, highest_bcp_number + 1):
        bcp_name = f"BCP{bcp_number}"
        bcp = Document.objects.filter(type_id="bcp", name=f"{bcp_name.lower()}").first()

        if bcp:
            entry = subseries_text_line(
                (
                    f"[{bcp_name}]"
                    f"{' ' * (SS_TXT_CUE_COL_WIDTH - len(bcp_name) - 2 - SS_TXT_MARGIN)}"
                    f"Best Current Practice {bcp_number},"
                ),
                first=True,
            )
            entry += "\n"
            entry += subseries_text_line(
                f"<{settings.RFC_EDITOR_INFO_BASE_URL}{bcp_name.lower()}>."
            )
            entry += "\n"
            entry += subseries_text_line(
                "At the time of writing, this BCP comprises the following:"
            )
            entry += "\n\n"
            rfcs = sorted(bcp.contains(), key=lambda x: x.rfc_number)
            for rfc in rfcs:
                authors = ", ".join(
                    author.format_for_titlepage() for author in rfc.rfcauthor_set.all()
                )
                entry += subseries_text_line(
                    (
                        f'{authors}, "{rfc.title}", BCP¶{bcp_number}, RFC¶{rfc.rfc_number}, '
                        f"DOI¶{rfc.doi}, {rfc.pub_date().strftime('%B %Y')}, "
                        f"<{settings.RFC_EDITOR_INFO_BASE_URL}rfc{rfc.rfc_number}>."
                    )
                ).replace("¶", " ")
                entry += "\n\n"
        else:
            entry = subseries_text_line(
                (
                    f"[{bcp_name}]"
                    f"{' ' * (SS_TXT_CUE_COL_WIDTH - len(bcp_name) - 2 - SS_TXT_MARGIN)}"
                    f"Best Current Practice {bcp_number} currently contains no RFCs"
                ),
                first=True,
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
        entry = etree.SubElement(rfc_index, f"{ss_type}-entry")
        etree.SubElement(
            entry, "doc-id"
        ).text = f"{ss_type.upper()}{format_rfc_number(ss_number)}"
        if len(contained_rfcs) > 0:
            is_also = etree.SubElement(entry, "is-also")
            for rfc in sorted(contained_rfcs, key=attrgetter("rfc_number")):
                etree.SubElement(
                    is_also, "doc-id"
                ).text = f"RFC{format_rfc_number(rfc.rfc_number)}"


def add_related_xml_index_entries(root: etree.Element, rfc: Document, tag: str):
    relation_getter = {
        "obsoletes": lambda doc: doc.related_that_doc("obs"),
        "obsoleted-by": lambda doc: doc.related_that("obs"),
        "updates": lambda doc: doc.related_that_doc("updates"),
        "updated-by": lambda doc: doc.related_that("updates"),
    }
    related_docs = sorted(
        relation_getter[tag](rfc),
        key=attrgetter("rfc_number"),
    )
    if len(related_docs) > 0:
        element = etree.SubElement(root, tag)
        for doc in related_docs:
            etree.SubElement(
                element, "doc-id"
            ).text = f"RFC{format_rfc_number(doc.rfc_number)}"


def add_rfc_xml_index_entries(rfc_index):
    """Add RFC entries for rfc-index.xml"""
    entries = []
    april1_rfc_numbers = get_april1_rfc_numbers()
    publication_statuses = get_publication_std_levels()

    published_rfcs = Document.objects.filter(type_id="rfc").order_by("rfc_number")

    # Iterators for unpublished and published, both sorted by number
    unpublished_iter = iter(get_unusable_rfc_numbers())
    published_iter = iter(published_rfcs)

    # Prime the next_* values
    next_unpublished = next(unpublished_iter, None)
    next_published = next(published_iter, None)

    while next_published is not None or next_unpublished is not None:
        if next_unpublished is not None and (
            next_published is None
            or next_unpublished.rfc_number < next_published.rfc_number
        ):
            entry = etree.SubElement(rfc_index, "rfc-not-issued-entry")
            etree.SubElement(
                entry, "doc-id"
            ).text = f"RFC{format_rfc_number(next_unpublished.rfc_number)}"
            entries.append(entry)
            next_unpublished = next(unpublished_iter, None)
            continue

        rfc = next_published  # hang on to this
        next_published = next(published_iter, None)  # prep for next iteration
        entry = etree.SubElement(rfc_index, "rfc-entry")

        etree.SubElement(
            entry, "doc-id"
        ).text = f"RFC{format_rfc_number(rfc.rfc_number)}"
        etree.SubElement(entry, "title").text = rfc.title

        for author in rfc.rfcauthor_set.all():
            author_element = etree.SubElement(entry, "author")
            etree.SubElement(author_element, "name").text = author.titlepage_name
            if author.is_editor:
                etree.SubElement(author_element, "title").text = "Editor"

        date = etree.SubElement(entry, "date")
        published_at = rfc.pub_date()
        etree.SubElement(date, "month").text = published_at.strftime("%B")
        if rfc.rfc_number in april1_rfc_numbers:
            etree.SubElement(date, "day").text = str(published_at.day)
        etree.SubElement(date, "year").text = str(published_at.year)

        format_ = etree.SubElement(entry, "format")
        fmts = [ff["fmt"] for ff in rfc.formats() if ff["fmt"] in FORMATS_FOR_INDEX]
        for fmt in sorted(fmts, key=format_ordering(rfc.rfc_number)):
            match_legacy = getattr(settings, "RFCINDEX_MATCH_LEGACY_XML", False)
            etree.SubElement(format_, "file-format").text = (
                "ASCII" if match_legacy and fmt == "txt" else fmt.upper()
            )

        etree.SubElement(entry, "page-count").text = str(rfc.pages)

        if len(rfc.keywords) > 0:
            keywords = etree.SubElement(entry, "keywords")
            for keyword in rfc.keywords:
                etree.SubElement(keywords, "kw").text = keyword.strip()

        if rfc.abstract:
            abstract = etree.SubElement(entry, "abstract")
            for paragraph in rfc.abstract.split("\n\n"):
                etree.SubElement(abstract, "p").text = paragraph.strip()

        draft = rfc.came_from_draft()
        if draft is not None:
            etree.SubElement(entry, "draft").text = f"{draft.name}-{draft.rev}"

        part_of_documents = rfc.part_of()
        if len(part_of_documents) > 0:
            is_also = etree.SubElement(entry, "is-also")
            for doc in part_of_documents:
                etree.SubElement(is_also, "doc-id").text = doc.name.upper()

        add_related_xml_index_entries(entry, rfc, "obsoletes")
        add_related_xml_index_entries(entry, rfc, "obsoleted-by")
        add_related_xml_index_entries(entry, rfc, "updates")
        add_related_xml_index_entries(entry, rfc, "updated-by")

        etree.SubElement(entry, "current-status").text = rfc.std_level.name.upper()
        etree.SubElement(entry, "publication-status").text = publication_statuses[
            rfc.rfc_number
        ].name.upper()
        etree.SubElement(entry, "stream").text = (
            "INDEPENDENT" if rfc.stream_id == "ise" else rfc.stream.name
        )

        # Add area / wg_acronym
        if rfc.stream_id == "ietf":
            if rfc.group.type_id in ["individ", "area"]:
                etree.SubElement(entry, "wg_acronym").text = "NON WORKING GROUP"
            else:
                if rfc.area is not None:
                    etree.SubElement(entry, "area").text = rfc.area.acronym
                if rfc.group:
                    etree.SubElement(entry, "wg_acronym").text = rfc.group.acronym

        if rfc.tags.filter(slug="errata").exists():
            etree.SubElement(entry, "errata-url").text = errata_url(rfc)
        etree.SubElement(entry, "doi").text = rfc.doi
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
    save_to_red_bucket("rfc-index.txt", index)


def create_rfc_xml_index():
    """Create XML index of published documents"""
    XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
    XSI = "{" + XSI_NAMESPACE + "}"

    log("Creating rfc-index.xml")
    rfc_index = etree.Element(
        "rfc-index",
        nsmap={
            None: "https://www.rfc-editor.org/rfc-index",
            "xsi": XSI_NAMESPACE,
        },
        attrib={
            XSI + "schemaLocation": (
                "https://www.rfc-editor.org/rfc-index "
                "https://www.rfc-editor.org/rfc-index.xsd"
            ),
        },
    )

    # add data
    add_subseries_xml_index_entries(rfc_index, "bcp", include_all=True)
    add_subseries_xml_index_entries(rfc_index, "fyi")
    add_rfc_xml_index_entries(rfc_index)
    add_subseries_xml_index_entries(rfc_index, "std")

    # make it pretty
    pretty_index = etree.tostring(
        rfc_index,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=4,
    )
    save_to_red_bucket("rfc-index.xml", pretty_index)


def create_bcp_txt_index():
    """Create text index of BCPs"""
    DATE_FMT = "%m/%d/%Y"
    created_on = timezone.now().strftime(DATE_FMT)
    log("Creating bcp-index.txt")
    index = render_to_string(
        "sync/bcp-index.txt",
        {
            "created_on": created_on,
            "bcps": get_bcp_text_index_entries(),
        },
    )
    save_to_red_bucket("bcp-index.txt", index)
