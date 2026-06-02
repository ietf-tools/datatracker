# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ietf.doc.models import Document, RelatedDocument
from ietf.name.models import StdLevelName
from ietf.doc.storage_utils import exists_in_storage, store_bytes
from ietf.sync.errata import errata_map_from_json, get_errata_data
from ietf.sync.rfcindex import get_april1_rfc_numbers, get_publication_std_levels
from ietf.utils.log import assertion, log


_FORMAT_CHECKS = [
    ("xml", "XML"),
    ("txt", "TEXT"),
    ("html", "HTML"),
    ("pdf", "PDF"),
]


def generate_rfc_json(rfc_number: int, *, pub_levels=None) -> None:
    """Generate and store the JSON metadata file for a published RFC.

    Reads RFC metadata from the DB and errata data from the red bucket, combines
    them, and writes json/rfc{N}.json to the "rfc" blob bucket (overwriting any
    existing file).

    pub_levels, if provided, should be the defaultdict returned by
    get_publication_std_levels(). Pass it when generating JSON for multiple RFCs
    to avoid a redundant blob read per call.
    """
    try:
        rfc = (
            Document.objects.select_related("std_level", "stream", "group__parent")
            .prefetch_related("rfcauthor_set")
            .get(type_id="rfc", rfc_number=rfc_number)
        )
    except Document.DoesNotExist:
        log(f"generate_rfc_json: no RFC found for rfc_number={rfc_number}")
        return

    if pub_levels is None:
        try:
            pub_levels = get_publication_std_levels()
        except Exception as e:
            log(f"generate_rfc_json: failed to get publication std levels: {e}")
            return

    doc_id = f"RFC{rfc_number}"

    # draft name
    draft_doc = rfc.came_from_draft()
    draft = draft_doc.name if draft_doc else None

    # authors: ordered list of display strings
    authors = []
    for author in rfc.rfcauthor_set.order_by("order"):
        name = author.titlepage_name
        if author.is_editor:
            name = f"{name}, Ed."
        authors.append(name)

    # format: check which file blobs are present
    formats = [
        label
        for ext, label in _FORMAT_CHECKS
        if exists_in_storage(kind="rfc", name=f"{ext}/rfc{rfc_number}.{ext}")
    ]

    # page_count
    page_count = str(rfc.pages) if rfc.pages is not None else ""

    # status: current std_level
    status = rfc.std_level.name.upper() if rfc.std_level else ""

    # pub_status from publication-std-levels.json in the red bucket
    # but guard against recent publication not having updated the bucket yet
    pub_event = rfc.latest_event(type="published_rfc")
    if rfc_number in pub_levels:
        pub_status = pub_levels[rfc_number].name.upper()
    else:
        if (
            pub_event is not None
            and timezone.now() - pub_event.time < datetime.timedelta(days=2)
        ):
            pub_status = status
        else:
            log(f"Assuming an unknown publication status for rfc{rfc_number}")
            pub_status = StdLevelName.objects.get(slug="unkn").name.upper()

    # source: adapted from errata system's display_source() logic
    if rfc.stream is None or rfc.group is None:
        # Basic expectations (should be constraints) on RFC Document objects
        # have been violated.
        assertion("rfc.stream is not None and rfc.group is not None")
        log(
            f"Malformed document object encountered for rfc{rfc_number}. Aborting update of rfc{rfc_number}.json"
        )
        return
    stream_slug = rfc.stream.slug
    group_acronym = rfc.group.acronym

    area_acronym = None
    if stream_slug == "ietf":
        if rfc.group.parent is None:
            assertion("rfc.group.parent is not None")
            log(
                f"Malformed document object encountered for rfc{rfc_number}. Aborting update of rfc{rfc_number}.json"
            )
            return
        else:
            area_acronym = rfc.group.parent.acronym

    if stream_slug == "ise":
        source = "INDEPENDENT"
    elif stream_slug == "iab":
        source = "IAB"
    elif stream_slug == "ietf" and (
        group_acronym in ("none", "gen") or not area_acronym
    ):
        source = "IETF - NON WORKING GROUP"
    elif group_acronym not in ("none", ""):
        source = group_acronym
        if stream_slug == "ietf" and area_acronym:
            source += f" ({area_acronym})"
        elif stream_slug:
            source += f" ({stream_slug})"
    elif stream_slug:
        source = "Legacy" if stream_slug == "legacy" else stream_slug.upper()
    else:
        source = ""

    # pub_date: month/year of publication, with April 1st special-casing
    pub_date = None
    if pub_event:
        dt = pub_event.time
        try:
            april_first_numbers = get_april1_rfc_numbers()
        except Exception:
            april_first_numbers = []
        if dt.month == 4 and rfc_number in april_first_numbers:
            pub_date = dt.strftime("1 %B %Y")
        else:
            pub_date = dt.strftime("%B %Y")

    # relationship lists — sorted by RFC number
    def _rfc_list(qs, attr):
        numbers = [
            getattr(rd, attr).rfc_number
            for rd in qs
            if getattr(rd, attr).rfc_number is not None
        ]
        return [f"RFC{n}" for n in sorted(numbers)]

    obsoletes = _rfc_list(
        RelatedDocument.objects.filter(
            source=rfc, relationship_id="obs"
        ).select_related("target"),
        "target",
    )
    obsoleted_by = _rfc_list(
        RelatedDocument.objects.filter(
            target=rfc, relationship_id="obs"
        ).select_related("source"),
        "source",
    )
    updates = _rfc_list(
        RelatedDocument.objects.filter(
            source=rfc, relationship_id="updates"
        ).select_related("target"),
        "target",
    )
    updated_by = _rfc_list(
        RelatedDocument.objects.filter(
            target=rfc, relationship_id="updates"
        ).select_related("source"),
        "source",
    )

    # errata_url: non-None if any errata entry exists for this RFC (any status)
    try:
        errata_data = get_errata_data()
        errata_map = errata_map_from_json(errata_data)
        errata_url = (
            settings.RFC_EDITOR_ERRATA_BASE_URL + f"rfc{rfc_number}"
            if rfc_number in errata_map
            else None
        )
    except Exception:
        log(f"generate_rfc_json: could not load errata data for RFC {rfc_number}")
        errata_url = None

    data = {
        "draft": draft,
        "doc_id": doc_id,
        "title": rfc.title,
        "authors": authors,
        "format": formats,
        "page_count": page_count,
        "pub_status": pub_status,
        "status": status,
        "source": source,
        "abstract": rfc.abstract,
        "pub_date": pub_date,
        "keywords": rfc.keywords,
        "obsoletes": obsoletes,
        "obsoleted_by": obsoleted_by,
        "updates": updates,
        "updated_by": updated_by,
        "see_also": [],
        "doi": f"10.17487/{doc_id}",
        "errata_url": errata_url,
    }

    content = json.dumps(data, indent=2).encode("utf-8")
    store_bytes(
        kind="rfc",
        name=f"json/rfc{rfc_number}.json",
        content=content,
        allow_overwrite=True,
        doc_name=f"rfc{rfc_number}",
        doc_rev=None,
        mtime=timezone.now(),
    )
    fs_path = Path(settings.RFC_PATH) / f"rfc{rfc_number}.json"
    if settings.SERVER_MODE != "production" and not fs_path.parent.exists():
        fs_path.parent.mkdir()
    fs_path.write_bytes(content)
