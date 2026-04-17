# Copyright The IETF Trust 2024-2026, All Rights Reserved
#
# Celery task definitions
#
import datetime

import debug  # pyflakes:ignore

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ietf.doc.utils_r2 import rfcs_are_in_r2
from ietf.doc.utils_red import trigger_red_precomputer
from ietf.utils import log, searchindex
from ietf.utils.timezone import datetime_today

from .expire import (
    in_draft_expire_freeze,
    get_expired_drafts,
    expirable_drafts,
    send_expire_notice_for_draft,
    expire_draft,
    clean_up_draft_files,
    get_soon_to_expire_drafts,
    send_expire_warning_for_draft,
)
from .lastcall import get_expired_last_calls, expire_last_call
from .models import Document, NewRevisionDocEvent
from .utils import (
    generate_idnits2_rfc_status,
    generate_idnits2_rfcs_obsoleted,
    rebuild_reference_relations,
    update_or_create_draft_bibxml_file,
    ensure_draft_bibxml_path_exists,
    investigate_fragment,
)
from .utils_bofreq import fixup_bofreq_timestamps
from .utils_errata import signal_update_rfc_metadata


@shared_task
def expire_ids_task():
    try:
        if not in_draft_expire_freeze():
            log.log("Expiring drafts ...")
            for doc in get_expired_drafts():
                # verify expirability -- it might have changed after get_expired_drafts() was run
                # (this whole loop took about 2 minutes on 04 Jan 2018)
                # N.B., re-running expirable_drafts() repeatedly is fairly expensive. Where possible,
                # it's much faster to run it once on a superset query of the objects you are going
                # to test and keep its results. That's not desirable here because it would defeat
                # the purpose of double-checking that a document is still expirable when it is actually
                # being marked as expired.
                if expirable_drafts(
                    Document.objects.filter(pk=doc.pk)
                ).exists() and doc.expires < datetime_today() + datetime.timedelta(1):
                    send_expire_notice_for_draft(doc)
                    expire_draft(doc)
                    log.log(f"  Expired draft {doc.name}-{doc.rev}")

        log.log("Cleaning up draft files")
        clean_up_draft_files()
    except Exception as e:
        log.log("Exception in expire-ids: %s" % e)
        raise


@shared_task
def notify_expirations_task(notify_days=14):
    for doc in get_soon_to_expire_drafts(notify_days):
        send_expire_warning_for_draft(doc)


@shared_task
def expire_last_calls_task():
    for doc in get_expired_last_calls():
        try:
            expire_last_call(doc)
        except Exception:
            log.log(
                f"ERROR: Failed to expire last call for {doc.file_tag()} (id={doc.pk})"
            )
        else:
            log.log(f"Expired last call for {doc.file_tag()} (id={doc.pk})")


@shared_task
def generate_idnits2_rfc_status_task():
    outpath = Path(settings.DERIVED_DIR) / "idnits2-rfc-status"
    blob = generate_idnits2_rfc_status()
    try:
        outpath.write_text(blob, encoding="utf8")  # TODO-BLOBSTORE
    except Exception as e:
        log.log(f"failed to write idnits2-rfc-status: {e}")


@shared_task
def generate_idnits2_rfcs_obsoleted_task():
    outpath = Path(settings.DERIVED_DIR) / "idnits2-rfcs-obsoleted"
    blob = generate_idnits2_rfcs_obsoleted()
    try:
        outpath.write_text(blob, encoding="utf8")  # TODO-BLOBSTORE
    except Exception as e:
        log.log(f"failed to write idnits2-rfcs-obsoleted: {e}")


@shared_task
def generate_draft_bibxml_files_task(days=7, process_all=False):
    """Generate bibxml files for recently updated docs

    If process_all is False (the default), processes only docs with new revisions
    in the last specified number of days.
    """
    if not process_all and days < 1:
        raise ValueError("Must call with days >= 1 or process_all=True")
    ensure_draft_bibxml_path_exists()
    doc_events = NewRevisionDocEvent.objects.filter(
        type="new_revision",
        doc__type_id="draft",
    ).order_by("time")
    if not process_all:
        doc_events = doc_events.filter(
            time__gte=timezone.now() - datetime.timedelta(days=days)
        )
    for event in doc_events:
        try:
            update_or_create_draft_bibxml_file(event.doc, event.rev)
        except Exception as err:
            log.log(f"Error generating bibxml for {event.doc.name}-{event.rev}: {err}")


@shared_task(ignore_result=False)
def investigate_fragment_task(name_fragment: str):
    return {
        "name_fragment": name_fragment,
        "results": investigate_fragment(name_fragment),
    }


@shared_task
def rebuild_reference_relations_task(doc_names: list[str]):
    log.log(f"Task: Rebuilding reference relations for {doc_names}")
    for doc in Document.objects.filter(name__in=doc_names, type__in=["rfc", "draft"]):
        filenames = dict()
        base = (
            settings.RFC_PATH
            if doc.type_id == "rfc"
            else settings.INTERNET_ALL_DRAFTS_ARCHIVE_DIR
        )
        stem = doc.name if doc.type_id == "rfc" else f"{doc.name}-{doc.rev}"
        for ext in ["xml", "txt"]:
            path = Path(base) / f"{stem}.{ext}"
            if path.is_file():
                filenames[ext] = str(path)
        if len(filenames) > 0:
            rebuild_reference_relations(doc, filenames)
        else:
            log.log(f"Found no content for {stem}")


@shared_task
def fixup_bofreq_timestamps_task():  # pragma: nocover
    fixup_bofreq_timestamps()


@shared_task
def signal_update_rfc_metadata_task(rfc_number_list=()):
    signal_update_rfc_metadata(rfc_number_list)


@shared_task(bind=True)
def trigger_red_precomputer_task(self, rfc_number_list=()):
    if not rfcs_are_in_r2(rfc_number_list):
        log.log(f"Objects are not yet in R2 for RFCs {rfc_number_list}")
        try:
            countdown = getattr(settings, "RED_PRECOMPUTER_TRIGGER_RETRY_DELAY", 10)
            max_retries = getattr(settings, "RED_PRECOMPUTER_TRIGGER_MAX_RETRIES", 12)
            self.retry(countdown=countdown, max_retries=max_retries)
        except MaxRetriesExceededError:
            log.log(f"Gave up waiting for objects in R2 for RFCs {rfc_number_list}")
    else:
        trigger_red_precomputer(rfc_number_list)


@shared_task(bind=True)
def update_rfc_searchindex_task(self, rfc_number: int):
    """Update the search index for one RFC"""
    if not searchindex.enabled():
        log.log("Search indexing is not enabled, skipping")
        return

    rfc = Document.objects.filter(type_id="rfc", rfc_number=rfc_number).first()
    if rfc is None:
        log.log(
            f"ERROR: Document for rfc{rfc_number} not found, not updating search index"
        )
        return
    try:
        searchindex.update_or_create_rfc_entry(rfc)
    except Exception as err:
        log.log(f"Search index update for {rfc.name} failed ({err})")
        if isinstance(err, searchindex.RETRYABLE_ERROR_CLASSES):
            searchindex_settings = searchindex.get_settings()
            self.retry(
                countdown=searchindex_settings["TASK_RETRY_DELAY"],
                max_retries=searchindex_settings["TASK_MAX_RETRIES"],
            )


@shared_task
def rebuild_searchindex_task(*, batchsize=40, drop_collection=False):
    if drop_collection:
        searchindex.delete_collection()
        searchindex.create_collection()
    searchindex.update_or_create_rfc_entries(
        Document.objects.filter(type_id="rfc").order_by("-rfc_number"),
        batchsize=batchsize,
    )
