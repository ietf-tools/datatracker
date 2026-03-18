# Copyright The IETF Trust 2026, All Rights Reserved
"""Search indexing utilities"""
import re
import typing
from collections.abc import Collection
from math import floor

import typesense
from django.conf import settings

from ietf.doc.models import Document
from ietf.utils.log import log

COLLECTION = "docs"

type DocsSchemaTypeT = typing.Literal["draft", "rfc"]

SlugNameDict = typing.TypedDict("SlugNameDict", {"slug": str, "name": str})


class GroupDict(typing.TypedDict):
    acronym: str
    name: str
    full: str


class SubseriesDict(typing.TypedDict):
    acronym: str  # type of subseries
    number: int  # number of the subseries doc
    total: int  # total number of docs in the subseries


class AuthorDict(typing.TypedDict):
    name: str
    affiliation: str


class FlagsDict(typing.TypedDict):
    hiddenDefault: bool  # should doc be hidden in search by default?
    obsoleted: bool  # obsoleted by another doc?
    updated: bool  # updated by another doc?


class DocsSchemaDict(typing.TypedDict):
    """TypedDict equivalent to the Typesense "docs" schema"""

    rfcNumber: int | None  # integer RFC number, omit for drafts
    rfc: str | None  # string RFC number, omit for drafts
    ref: str | None  # RFC number for drafts corresponding to draft, else omitted
    filename: str  # filename of the document, without extension
    title: str  # title of the draft / rfc
    abstract: str  # abstract of the draft / rfc
    keywords: Collection[str]  # search keywords, possibly empty
    type: DocsSchemaTypeT  # type of the document (draft/rfc)
    state: Collection[str] | None  # state(s) of the document (full name)
    status: SlugNameDict | None  # standard level name (slug and name)
    subseries: SubseriesDict | None
    date: int  # date as a unix timestamp
    expires: int | None  # expiration date as a unix timestamp
    publicationDate: int | None  # publication date as a unix timestamp
    group: GroupDict | None  # working group
    area: GroupDict | None
    stream: SlugNameDict | None
    authors: list[AuthorDict] | None
    adName: str | None  # area director name
    flags: FlagsDict
    obsoletedBy: list[str]  # RFC numbers (as strs) obsoleting this doc
    updatedBy: list[str]  # RFC numbers (as strs) updating this doc
    content: str | None  # sanitized content
    ranking: int  # ranking when no explicit sorting (RFC number or rev)



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

    ts_id = f"doc-{rfc.pk}"
    ts_document: DocsSchemaDict = {
        "rfcNumber": rfc.rfc_number,
        "rfc": str(rfc.rfc_number),
        "ref": None,
        "filename": rfc.name,
        "title": rfc.title,
        "abstract": _sanitize_text(rfc.abstract),
        "keywords": keywords,
        "type": "rfc",
        "state": [state.name for state in rfc.states.all()],
        "status": {"slug": rfc.std_level.slug, "name": rfc.std_level.name},
        "subseries": (
            None
            if subseries is None
            else SubseriesDict(
                acronym=subseries.type.slug,
                number=int(subseries.name[len(subseries.type.slug) :]),
                total=len(subseries.contains()),
            )
        ),
        "date": floor(rfc.time.timestamp()),
        "expires": None,
        "publicationDate": floor(rfc.pub_datetime().timestamp()),
        "group": (
            None
            if rfc.group is None  # exclude "none" (individual group)?
            else GroupDict(
                acronym=rfc.group.acronym,
                name=rfc.group.name,
                full=f"{rfc.group.acronym} - {rfc.group.name}",
            )
        ),
        "area": (
            GroupDict(
                acronym=rfc.group.parent.acronym,
                name=rfc.group.parent.name,
                full=f"{rfc.group.parent.acronym} - {rfc.group.parent.name}",
            )
            if (
                rfc.group.parent is not None
                and rfc.stream_id not in ["ise", "irtf", "iab"]  # exclude editorial?
            )
            else None
        ),
        "stream": {"slug": rfc.stream.slug, "name": rfc.stream.name},
        "authors": [
            AuthorDict(
                name=rfc_author.titlepage_name, affiliation=rfc_author.affiliation
            )
            for rfc_author in rfc.rfcauthor_set.all()
        ],
        "adName": None if rfc.ad is None else rfc.ad.name,
        "flags": {
            "hiddenDefault": False,
            "obsoleted": len(obsoleted_by) > 0,
            "updated": len(updated_by) > 0,
        },
        "obsoletedBy": [str(doc.rfc_number) for doc in obsoleted_by],
        "updatedBy": [str(doc.rfc_number) for doc in updated_by],
        "content": None,  # tbd
        "ranking": rfc.rfc_number,
    }

    client = typesense.Client(
        {"api_key": settings.TYPESENSE_API_KEY, "nodes": [settings.TYPESENSE_API_URL]}
    )
    client.collections[COLLECTION].documents.upsert({"id": ts_id} | ts_document)
