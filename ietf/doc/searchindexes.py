# Copyright The IETF Trust 2026, All Rights Reserved
"""Search indexing for documents"""

import re
from collections.abc import Callable
from math import floor
from typing import Any, Iterable

from typesense.types.document import DocumentSchema

from ietf.utils import search_provider
from ietf.utils.log import log

from .models import Document, StoredObject
from .storage_utils import retrieve_str
from .utils_reef import cached_popularity_scores, refresh_popularity_scores


def _sanitize_text(content: str):
    """Sanitize content text for search

    Aggressively simplifies whitespace, removes most punctuation
    """
    # REs (with approximate names)
    RE_DOT_OR_BANG_SPACE = r"\. |! "  # -> " " (space)
    RE_COMMENT_OR_TOC_CRUD = r"<--|-->|--+|\+|\.\.+"  # -> ""
    RE_BRACKETED_REF = r"\[[a-zA-Z0-9 -]+\]"  # -> ""
    RE_DOTTED_NUMBERS = r"[0-9]+\.[0-9]+(\.[0-9]+)?"  # -> ""
    RE_MULTIPLE_WHITESPACE = r"\s+"  # -> " " (space)
    # Replacement values (for clarity of intent)
    SPACE = " "
    EMPTY = ""
    # Sanitizing begins here, order is significant!
    content = re.sub(RE_DOT_OR_BANG_SPACE, SPACE, content.strip())
    content = re.sub(RE_COMMENT_OR_TOC_CRUD, EMPTY, content)
    content = re.sub(RE_BRACKETED_REF, EMPTY, content)
    content = re.sub(RE_DOTTED_NUMBERS, EMPTY, content)
    content = re.sub(RE_MULTIPLE_WHITESPACE, SPACE, content)
    return content.strip()


def _sanitize_abstract(abstract: str):
    """Sanitize abstract text for search

    Simplifies whitespace but mostly leaves text intact. Abstract text will be
    displayed in search results, so a light touch is needed.
    """
    abstract = abstract.strip()
    abstract = re.sub("\r\n|\n\r|\r", "\n", abstract)  # normalize on \n
    abstract = "\n".join(line.strip() for line in abstract.split("\n"))  # strip by line
    return abstract


def _get_popularity_scores() -> dict[int, float] | None:
    """Get cached popularity scores, or None if they are unavailable"""
    try:
        return cached_popularity_scores()
    except Exception as err:
        log(f"Unable to load popularity scores: {err}")
        return None


def typesense_doc_from_rfc(
    rfc: Document, popularity_scores: dict[int, float] | None
) -> DocumentSchema:
    """Build the typesense document for an RFC

    popularity_scores maps rfc_number to popularity score, or is None if scores are
    unavailable.
    """
    assert rfc.type_id == "rfc"
    assert rfc.rfc_number is not None
    assert rfc.pages is not None

    keywords: list[str] = rfc.keywords  # help type checking

    subseries = rfc.part_of()
    if len(subseries) > 1:
        log(
            f"RFC {rfc.rfc_number} is in multiple subseries. "
            f"Indexing as {subseries[0].name}"
        )
    subseries = subseries[0] if len(subseries) > 0 else None
    obsoleted_by = rfc.related_that("obs")
    is_obsoleted = len(obsoleted_by) > 0
    updated_by = rfc.related_that("updates")
    is_updated = len(updated_by) > 0
    is_historic = rfc.std_level.slug == "hist"

    stored_txt = (
        StoredObject.objects.exclude_deleted()
        .filter(store="rfc", doc_name=rfc.name, name__startswith="txt/")
        .first()
    )
    content = ""
    if stored_txt is not None:
        # Should be available in the blobdb, but be cautious...
        try:
            content = retrieve_str(kind=stored_txt.store, name=stored_txt.name)
        except Exception as err:
            log(f"Unable to retrieve {stored_txt} from storage: {err}")

    ts_document = {
        "id": f"doc-{rfc.pk}",
        "rfcNumber": rfc.rfc_number,
        "rfc": str(rfc.rfc_number),
        "filename": rfc.name,
        "title": rfc.title,
        "abstract": _sanitize_abstract(rfc.abstract),
        "pages": rfc.pages,
        "keywords": keywords,
        "type": "rfc",
        "state": [state.name for state in rfc.states.all()],
        "status": {"slug": rfc.std_level.slug, "name": rfc.std_level.name},
        "date": floor(rfc.time.timestamp()),
        "publicationDate": floor(rfc.pub_datetime().timestamp()),
        "stream": {"slug": rfc.stream.slug, "name": rfc.stream.name},
        "authors": [
            {"name": rfc_author.titlepage_name, "affiliation": rfc_author.affiliation}
            for rfc_author in rfc.rfcauthor_set.all()
        ],
        "flags": {
            "hiddenDefault": is_obsoleted or is_historic,
            "obsoleted": is_obsoleted,
            "updated": is_updated,
        },
        "obsoletedBy": [str(doc.rfc_number) for doc in obsoleted_by],
        "updatedBy": [str(doc.rfc_number) for doc in updated_by],
        "ranking": rfc.rfc_number,
        "popularity": (
            None if popularity_scores is None else popularity_scores.get(rfc.rfc_number)
        ),
    }
    if subseries is not None:
        ts_document["subseries"] = {
            "acronym": subseries.type.slug,
            "number": int(subseries.name[len(subseries.type.slug) :]),
            "total": len(subseries.contains()),
        }
    if rfc.group is not None:
        ts_document["group"] = {
            "acronym": rfc.group.acronym,
            "name": rfc.group.name,
            "full": f"{rfc.group.acronym} - {rfc.group.name}",
            "type": rfc.group.type.slug,
        }
    if (
        rfc.group.parent is not None
        and rfc.stream_id not in ["ise", "irtf", "iab"]  # exclude editorial?
    ):
        ts_document["area"] = {
            "acronym": rfc.group.parent.acronym,
            "name": rfc.group.parent.name,
            "full": f"{rfc.group.parent.acronym} - {rfc.group.parent.name}",
        }
    if rfc.ad is not None:
        ts_document["adName"] = rfc.ad.name
    if content != "":
        ts_document["content"] = _sanitize_text(content)
    return ts_document


def update_or_create_rfc_entry(rfc: Document):
    """Update/create index entries for one RFC"""
    ts_document = typesense_doc_from_rfc(rfc, _get_popularity_scores())
    DOCS_INDEX.upsert_document(ts_document)


def update_or_create_rfc_entries(
    rfcs: Iterable[Document], batchsize: int | None = None
):
    """Update/create index entries for RFCs in bulk

    If batchsize is set, computes index data in batches of batchsize and adds to the
    index. Will make a total of (len(rfcs) // batchsize) + 1 API calls.
    """
    popularity_scores = _get_popularity_scores()
    result = DOCS_INDEX.upsert_documents(
        (typesense_doc_from_rfc(rfc, popularity_scores) for rfc in rfcs),
        batchsize=batchsize,
    )
    for failure in result.failures:
        log(f"Failed to index RFC {failure.document['rfcNumber']}: {failure.error}")
    log(
        f"Added {result.written} RFCs to the index, "
        f"failed to add {len(result.failures)}"
    )


def partial_update_rfc_entries(
    rfcs: Iterable[Document],
    fields: dict[str, Callable[[Document], Any]],
    batchsize: int | None = None,
):
    result = DOCS_INDEX.update_documents(
        (
            {"id": f"doc-{rfc.pk}"}  # required
            | {
                field_name: field_extractor(rfc)
                for field_name, field_extractor in fields.items()
            }
            for rfc in rfcs
        ),
        batchsize=batchsize,
    )
    for failure in result.failures:
        log(f"Failed to update {failure.document['id']}: {failure.error}")
    log(
        f"Updated {result.written} RFCs in the index, "
        f"failed to update {len(result.failures)}"
    )


def update_rfc_popularities(rfcs: Iterable[Document], batchsize: int | None = None):
    # Load fresh scores once rather than per RFC. This also refreshes the cache.
    scores = refresh_popularity_scores()
    partial_update_rfc_entries(
        rfcs,
        {
            "popularity": lambda rfc: (
                None if rfc.rfc_number is None else scores.get(rfc.rfc_number)
            )
        },
        batchsize,
    )


DOCS_SCHEMA = {
    "enable_nested_fields": True,
    "default_sorting_field": "ranking",
    "fields": [
        # RFC number in integer form, for sorting asc/desc in search results
        # Omit field for drafts
        {
            "name": "rfcNumber",
            "type": "int32",
            "facet": False,
            "optional": True,
            "sort": True,
        },
        # RFC number in string form, for direct matching with ranking
        # Omit field for drafts
        {"name": "rfc", "type": "string", "facet": False, "optional": True},
        # For drafts that correspond to an RFC, insert the RFC number
        # Omit field for rfcs or if not relevant
        {"name": "ref", "type": "string", "facet": False, "optional": True},
        # Filename of the document (without the extension, e.g. "rfc1234"
        # or "draft-ietf-abc-def-02")
        {"name": "filename", "type": "string", "facet": False, "infix": True},
        # Title of the draft / rfc
        {"name": "title", "type": "string", "facet": False},
        # Abstract of the draft / rfc
        {"name": "abstract", "type": "string", "facet": False},
        # Number of pages
        {"name": "pages", "type": "int32", "facet": False},
        # A list of search keywords if relevant, set to empty array otherwise
        {"name": "keywords", "type": "string[]", "facet": True},
        # Type of the document
        # Accepted values: "draft" or "rfc"
        {"name": "type", "type": "string", "facet": True},
        # State(s) of the document (e.g. "Published", "Adopted by a WG", etc.)
        # Use the full name, not the slug
        {"name": "state", "type": "string[]", "facet": True, "optional": True},
        # Status (Standard Level Name)
        # Object with properties "slug" and "name"
        # e.g.: { slug: "std", "name": "Internet Standard" }
        {"name": "status", "type": "object", "facet": True, "optional": True},
        # The subseries it is part of. (e.g. "BCP")
        # Omit otherwise.
        {
            "name": "subseries.acronym",
            "type": "string",
            "facet": True,
            "optional": True,
        },
        # The subseries number it is part of. (e.g. 123)
        # Omit otherwise.
        {
            "name": "subseries.number",
            "type": "int32",
            "facet": True,
            "sort": True,
            "optional": True,
        },
        # The total of RFCs in the subseries
        # Omit if not part of a subseries
        {
            "name": "subseries.total",
            "type": "int32",
            "facet": False,
            "sort": False,
            "optional": True,
        },
        # Date of the document, in unix epoch seconds (can be negative for < 1970)
        {"name": "date", "type": "int64", "facet": False},
        # Expiration date of the document, in unix epoch seconds (can be negative
        # for < 1970). Omit field for RFCs
        {"name": "expires", "type": "int64", "facet": False, "optional": True},
        # Publication date of the RFC, in unix epoch seconds (can be negative
        # for < 1970). Omit field for drafts
        {
            "name": "publicationDate",
            "type": "int64",
            "facet": True,
            "optional": True,
        },
        # Working Group
        # Object with properties "acronym", "name" and "full"
        # e.g.:
        # {
        #     "acronym": "ntp",
        #     "name": "Network Time Protocols",
        #     "full": "ntp - Network Time Protocols",
        # }
        {"name": "group", "type": "object", "facet": True, "optional": True},
        # Area
        # Object with properties "acronym", "name" and "full"
        # e.g.:
        # {
        #     "acronym": "mpls",
        #     "name": "Multiprotocol Label Switching",
        #     "full": "mpls - Multiprotocol Label Switching",
        # }
        {"name": "area", "type": "object", "facet": True, "optional": True},
        # Stream
        # Object with properties "slug" and "name"
        # e.g.: { slug: "ietf", "name": "IETF" }
        {"name": "stream", "type": "object", "facet": True, "optional": True},
        # List of authors
        # Array of objects with properties "name" and "affiliation"
        # e.g.:
        # [
        #     {"name": "John Doe", "affiliation": "ACME Inc."},
        #     {"name": "Ada Lovelace", "affiliation": "Babbage Corps."},
        # ]
        {"name": "authors", "type": "object[]", "facet": True, "optional": True},
        # Area Director Name (e.g. "Leonardo DaVinci")
        {"name": "adName", "type": "string", "facet": True, "optional": True},
        # Whether the document should be hidden by default in search results or not.
        {"name": "flags.hiddenDefault", "type": "bool", "facet": True},
        # Whether the document is obsoleted by another document or not.
        {"name": "flags.obsoleted", "type": "bool", "facet": True},
        # Whether the document is updated by another document or not.
        {"name": "flags.updated", "type": "bool", "facet": True},
        # List of documents that obsolete this document.
        # Array of strings. Use RFC number for RFCs. (e.g. ["123", "456"])
        # Omit if none. Must be provided if "flags.obsoleted" is set to True.
        {
            "name": "obsoletedBy",
            "type": "string[]",
            "facet": False,
            "optional": True,
        },
        # List of documents that update this document.
        # Array of strings. Use RFC number for RFCs. (e.g. ["123", "456"])
        # Omit if none. Must be provided if "flags.updated" is set to True.
        {"name": "updatedBy", "type": "string[]", "facet": False, "optional": True},
        # Sanitized content of the document.
        # Make sure to remove newlines, double whitespaces, symbols and tags.
        {
            "name": "content",
            "type": "string",
            "facet": False,
            "optional": True,
            "store": False,
        },
        # Ranking value to use when no explicit sorting is used during search
        # Set to the RFC number for RFCs and the revision number for drafts
        # This ensures newer RFCs get listed first in the default search results
        # (without a query)
        {"name": "ranking", "type": "int32", "facet": False},
        # Popularity score. Unscored will sort after those with any score, regardless of
        # sort direction, unless the sort_by field explicity specifies different
        # missing_values behavior.
        {
            "name": "popularity",
            "type": "float",
            "facet": False,
            "optional": True,
        },
    ],
}

SEARCH_PRESETS = {
    "red": {
        "collection": "docs",
        "infix": "off,always,off,off,off,off,off,off",
        "query_by": "rfc,filename,title,abstract,keywords,authors,group,area",
        "query_by_weights": "127,50,50,20,20,5,2,1",
    },
    "red-content": {
        "collection": "docs",
        "infix": "off,always,off,off,off,off,off,off,off",
        "query_by": "rfc,filename,title,abstract,keywords,authors,group,area,content",
        "query_by_weights": "127,50,50,20,20,5,2,1,1",
    },
}

DOCS_INDEX = search_provider.SearchIndex(
    name="docs", schema=DOCS_SCHEMA, presets=SEARCH_PRESETS
)
