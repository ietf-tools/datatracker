# Copyright The IETF Trust 2024-2025, All Rights Reserved
#
# Celery task definitions
#
import datetime
import debug  # pyflakes:ignore

from celery import shared_task
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from ietf.utils import log
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
from .models import Document, NewRevisionDocEvent, StoredObject
from .utils import (
    generate_idnits2_rfc_status,
    generate_idnits2_rfcs_obsoleted,
    update_or_create_draft_bibxml_file,
    ensure_draft_bibxml_path_exists,
    investigate_fragment,
)


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
            log.log(f"ERROR: Failed to expire last call for {doc.file_tag()} (id={doc.pk})")
        else:
            log.log(f"Expired last call for {doc.file_tag()} (id={doc.pk})")


@shared_task            
def generate_idnits2_rfc_status_task():
    outpath = Path(settings.DERIVED_DIR) / "idnits2-rfc-status"
    blob = generate_idnits2_rfc_status()
    try:
        outpath.write_text(blob, encoding="utf8") # TODO-BLOBSTORE
    except Exception as e:
        log.log(f"failed to write idnits2-rfc-status: {e}")


@shared_task
def generate_idnits2_rfcs_obsoleted_task():
    outpath = Path(settings.DERIVED_DIR) / "idnits2-rfcs-obsoleted"
    blob = generate_idnits2_rfcs_obsoleted()
    try:
        outpath.write_text(blob, encoding="utf8") # TODO-BLOBSTORE
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
        doc_events = doc_events.filter(time__gte=timezone.now() - datetime.timedelta(days=days))
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
