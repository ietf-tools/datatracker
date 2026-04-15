# Copyright The IETF Trust 2026, All Rights Reserved
import datetime
import json
from collections import defaultdict
from typing import DefaultDict

from django.conf import settings
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Q

from ietf.doc.models import Document, DocEvent
from ietf.name.models import DocTagName
from ietf.person.models import Person
from ietf.utils.log import log
from ietf.utils.models import DirtyBits


DEFAULT_ERRATA_JSON_BLOB_NAME = "other/errata.json"

type ErrataJsonEntry = dict[str, str]

def get_errata_last_updated() -> datetime.datetime:
    """Get timestamp of the last errata.json update

    May raise FileNotFoundError or other storage/S3 exceptions. Be prepared.
    """
    red_bucket = storages["red_bucket"]
    return red_bucket.get_modified_time(
        getattr(settings, "ERRATA_JSON_BLOB_NAME", DEFAULT_ERRATA_JSON_BLOB_NAME)
    )


def get_errata_data() -> list[ErrataJsonEntry]:
    red_bucket = storages["red_bucket"]
    with red_bucket.open(
        getattr(settings, "ERRATA_JSON_BLOB_NAME", DEFAULT_ERRATA_JSON_BLOB_NAME), "r"
    ) as f:
        errata_data = json.load(f)
    return errata_data


def errata_map_from_json(errata_data: list[ErrataJsonEntry]):
    """Create a dict mapping RFC number to a list of applicable errata records"""
    errata = defaultdict(list)
    for item in errata_data:
        doc_id = item["doc-id"]
        if doc_id.upper().startswith("RFC"):
            rfc_number = int(doc_id[3:])
            errata[rfc_number].append(item)
    return dict(errata)


def update_errata_tags(errata_data: list[ErrataJsonEntry]):
    tag_has_errata = DocTagName.objects.get(slug="errata")
    tag_has_verified_errata = DocTagName.objects.get(slug="verified-errata")
    system = Person.objects.get(name="(System)")

    errata_map = errata_map_from_json(errata_data)
    nums_with_errata = [
        num
        for num, errata in errata_map.items()
        if any(er["errata_status_code"] != "Rejected" for er in errata)
    ]
    nums_with_verified_errata = [
        num
        for num, errata in errata_map.items()
        if any(er["errata_status_code"] == "Verified" for er in errata)
    ]

    rfcs_gaining_errata_tag = Document.objects.filter(
        type_id="rfc", rfc_number__in=nums_with_errata
    ).exclude(tags=tag_has_errata)

    rfcs_gaining_verified_errata_tag = Document.objects.filter(
        type_id="rfc", rfc_number__in=nums_with_verified_errata
    ).exclude(tags=tag_has_verified_errata)

    rfcs_losing_errata_tag = Document.objects.filter(
        type_id="rfc", tags=tag_has_errata
    ).exclude(rfc_number__in=nums_with_errata)

    rfcs_losing_verified_errata_tag = Document.objects.filter(
        type_id="rfc", tags=tag_has_verified_errata
    ).exclude(rfc_number__in=nums_with_verified_errata)

    # map rfc_number to add/remove lists
    changes: DefaultDict[Document, dict[str, list[DocTagName]]] = defaultdict(
        lambda: {"add": [], "remove": []}
    )
    for rfc in rfcs_gaining_errata_tag:
        changes[rfc]["add"].append(tag_has_errata)
    for rfc in rfcs_gaining_verified_errata_tag:
        changes[rfc]["add"].append(tag_has_verified_errata)
    for rfc in rfcs_losing_errata_tag:
        changes[rfc]["remove"].append(tag_has_errata)
    for rfc in rfcs_losing_verified_errata_tag:
        changes[rfc]["remove"].append(tag_has_verified_errata)

    for rfc, changeset in changes.items():
        # Update in a transaction per RFC to keep tags and DocEvents consistent.
        # With this in place, an interrupted task will be cleanly completed on the
        # next run.
        with transaction.atomic():
            change_descs = []
            for tag in changeset["add"]:
                rfc.tags.add(tag)
                change_descs.append(f"added {tag.slug} tag")
            for tag in changeset["remove"]:
                rfc.tags.remove(tag)
                change_descs.append(f"removed {tag.slug} tag")
            summary = "Update from RFC Editor: " + ", ".join(change_descs)
            if rfc.rfc_number in errata_map and all(
                er["errata_status_code"] == "Rejected"
                for er in errata_map[rfc.rfc_number]
            ):
                summary += " (all errata rejected)"
            DocEvent.objects.create(
                doc=rfc,
                rev=rfc.rev,  # expect no rev
                by=system,
                type="sync_from_rfc_editor",
                desc=summary,
            )


def update_errata_from_rfceditor():
    errata_data = get_errata_data()
    update_errata_tags(errata_data)


## DirtyBits management for the errata tags

ERRATA_SLUG = DirtyBits.Slugs.ERRATA


def update_errata_dirty_time() -> DirtyBits | None:
    try:
        last_update = get_errata_last_updated()
    except Exception as err:
        log(f"Error in get_errata_last_updated: {err}")
        return None
    else:
        dirty_work, created = DirtyBits.objects.update_or_create(
            slug=ERRATA_SLUG, defaults={"dirty_time": last_update}
        )
        if created:
            log(f"Created DirtyBits(slug='{ERRATA_SLUG}')")
        return dirty_work


def mark_errata_as_processed(when: datetime.datetime):
    n_updated = DirtyBits.objects.filter(
        Q(processed_time__isnull=True) | Q(processed_time__lt=when),
        slug=ERRATA_SLUG,
    ).update(processed_time=when)
    if n_updated > 0:
        log(f"processed_time is now {when.isoformat()}")
    else:
        log("processed_time not updated, no matching record found")


def errata_are_dirty():
    """Does the rfc index need to be updated?"""
    dirty_work = update_errata_dirty_time()  # creates DirtyBits if needed
    if dirty_work is None:
        # A None indicates we could not check the timestamp of errata.json. In that
        # case, we are not likely to be able to read the blob either, so don't try
        # to process it. An error was already logged.
        return False
    display_processed_time = (
        dirty_work.processed_time.isoformat()
        if dirty_work.processed_time is not None
        else "never"
    )
    log(
        f"DirtyBits(slug='{ERRATA_SLUG}'): "
        f"dirty_time={dirty_work.dirty_time.isoformat()} "
        f"processed_time={display_processed_time}"
    )
    return (
        dirty_work.processed_time is None
        or dirty_work.dirty_time >= dirty_work.processed_time
    )
