# Copyright The IETF Trust 2026, All Rights Reserved
"""Search indexing utilities"""

import re
from math import floor

import httpx  # just for exceptions
import typesense
import typesense.exceptions
from django.conf import settings

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


def update_or_create_rfc_entry(rfc: Document):
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
    obsoleted_by = rfc.relations_that("obs")
    updated_by = rfc.relations_that("updates")

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

    ts_id = f"doc-{rfc.pk}"
    ts_document = {
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
    _settings = get_settings()
    client = typesense.Client(
        {
            "api_key": _settings["TYPESENSE_API_KEY"],
            "nodes": [_settings["TYPESENSE_API_URL"]],
        }
    )
    client.collections[_settings["TYPESENSE_COLLECTION_NAME"]].documents.upsert(
        {"id": ts_id} | ts_document
    )
