# Copyright The IETF Trust 2026, All Rights Reserved
"""Search indexing utilities"""

import re
from itertools import batched
from math import floor
from typing import Iterable

import httpx  # just for exceptions
import typesense
import typesense.exceptions
from django.conf import settings
from typesense.types.document import DocumentSchema

from ietf.doc.models import Document, StoredObject
from ietf.doc.storage_utils import retrieve_str
from ietf.utils.log import log

# Error classes that might succeed just by retrying a failed attempt.
# Must be a tuple for use with isinstance()
RETRYABLE_ERROR_CLASSES = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    typesense.exceptions.Timeout,
    typesense.exceptions.ServerError,
    typesense.exceptions.ServiceUnavailable,
)


DEFAULT_SETTINGS = {
    "TYPESENSE_API_URL": "",
    "TYPESENSE_API_KEY": "",
    "TYPESENSE_COLLECTION_NAME": "docs",
    "TASK_RETRY_DELAY": 10,
    "TASK_MAX_RETRIES": 12,
}


def get_settings():
    return DEFAULT_SETTINGS | getattr(settings, "SEARCHINDEX_CONFIG", {})


def enabled():
    _settings = get_settings()
    return _settings["TYPESENSE_API_URL"] != ""


def get_typesense_client() -> typesense.Client:
    _settings = get_settings()
    client = typesense.Client(
        {
            "api_key": _settings["TYPESENSE_API_KEY"],
            "nodes": [_settings["TYPESENSE_API_URL"]],
        }
    )
    return client


def get_collection_name() -> str:
    _settings = get_settings()
    collection_name = _settings["TYPESENSE_COLLECTION_NAME"]
    assert isinstance(collection_name, str)
    return collection_name


def _sanitize_text(content):
    """Sanitize content or abstract text for search"""
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


def typesense_doc_from_rfc(rfc: Document) -> DocumentSchema:
    assert rfc.type_id == "rfc"
    assert rfc.rfc_number is not None

    keywords: list[str] = rfc.keywords  # help type checking

    subseries = rfc.part_of()
    if len(subseries) > 1:
        log(
            f"RFC {rfc.rfc_number} is in multiple subseries. "
            f"Indexing as {subseries[0].name}"
        )
    subseries = subseries[0] if len(subseries) > 0 else None
    obsoleted_by = rfc.related_that("obs")
    updated_by = rfc.related_that("updates")

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
        "abstract": _sanitize_text(rfc.abstract),
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
            "hiddenDefault": False,
            "obsoleted": len(obsoleted_by) > 0,
            "updated": len(updated_by) > 0,
        },
        "obsoletedBy": [str(doc.rfc_number) for doc in obsoleted_by],
        "updatedBy": [str(doc.rfc_number) for doc in updated_by],
        "ranking": rfc.rfc_number,
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
    ts_document = typesense_doc_from_rfc(rfc)
    client = get_typesense_client()
    client.collections[get_collection_name()].documents.upsert(ts_document)


def update_or_create_rfc_entries(
    rfcs: Iterable[Document], batchsize: int | None = None
):
    """Update/create index entries for RFCs in bulk

    If batchsize is set, computes index data in batches of batchsize and adds to the
    index. Will make a total of (len(rfcs) // batchsize) + 1 API calls.

    N.b. that typesense has a server-side batch size that defaults to 40, which should
    "almost never be changed from the default." This does not change that. Further,
    the python client library's import_ method has a batch_size parameter that does
    client-side batching. We don't use that, either.
    """
    success_count = 0
    fail_count = 0
    client = get_typesense_client()
    batches = [rfcs] if batchsize is None else batched(rfcs, batchsize)
    for batch in batches:
        tdoc_batch = [typesense_doc_from_rfc(rfc) for rfc in batch]
        results = client.collections[get_collection_name()].documents.import_(
            tdoc_batch, {"action": "upsert"}
        )
        for tdoc, result in zip(tdoc_batch, results):
            if result["success"]:
                success_count += 1
            else:
                fail_count += 1
                log(f"Failed to index RFC {tdoc['rfcNumber']}: {result['error']}")
    log(f"Added {success_count} RFCs to the index, failed to add {fail_count}")


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
    ],
}


def create_collection():
    collection_name = get_collection_name()
    log(f"Creating '{collection_name}' collection")
    client = get_typesense_client()
    client.collections.create({"name": get_collection_name()} | DOCS_SCHEMA)


def delete_collection():
    collection_name = get_collection_name()
    log(f"Deleting '{collection_name}' collection")
    client = get_typesense_client()
    try:
        client.collections[collection_name].delete()
    except typesense.exceptions.ObjectNotFound:
        pass
