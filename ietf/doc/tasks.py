# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import os
import datetime
import debug  # pyflakes:ignore

from django.conf import settings

from celery import shared_task

from ietf.utils import log
from ietf.utils.timezone import datetime_today
from ietf.doc.utils import generate_idnits2_rfcs_obsoleted
from ietf.doc.utils import generate_idnits2_rfc_status
from ietf.doc.utils import bibxml_for_all_drafts
from ietf.doc.utils import bibxml_for_recent_drafts

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
from .models import Document


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
def generate_idnits2_rfcs_obsoleted_task():
    filename = os.path.join(settings.DERIVED_DIR, 'idnits2-rfcs-obsoleted')
    blob = generate_idnits2_rfcs_obsoleted()
    try:
        f = open(filename, 'wb')
        f.write(blob.encode('utf-8'))
    except Exception as e:
        log.log('failed to write idnits2-rfcs-obsoleted: ' + str(e))
        raise e


@shared_task
def generate_idnits2_rfc_status_task():
    filename = os.path.join(settings.DERIVED_DIR, 'idnits2-rfc-status')
    blob = generate_idnits2_rfc_status()
    try:
        f = open(filename, 'wb')
        f.write(blob.encode('utf-8'))
    except Exception as e:
        log.log('failed to write idnits2-rfc-status: ' + str(e))
        raise e


@shared_task
def generate_bibxml_files_for_all_drafts_task():
    bibxmldir = os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids')
    if not os.path.exists(bibxmldir):
        log.log('%s directory needs to be created' % bibxmldir)
        print(bibxmldir)
        raise FileNotFoundError(bibxmldir)
    bibxml_for_all_drafts(bibxmldir)


@shared_task
def generate_bibxml_files_for_recent_drafts_task(days=7):
    bibxmldir = os.path.join(settings.BIBXML_BASE_PATH, 'bibxml-ids')
    if not os.path.exists(bibxmldir):
        log.log('%s directory needs to be created' % bibxmldir)
        raise FileNotFoundError(bibxmldir)
    bibxml_for_recent_drafts(bibxmldir, days=days)
