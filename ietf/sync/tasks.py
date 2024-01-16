# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime
import io
import requests
from celery import shared_task

from django.conf import settings

from ietf.sync.rfceditor import MIN_ERRATA_RESULTS, MIN_INDEX_RESULTS, parse_index, update_docs_from_rfc_index
from ietf.utils import log
from ietf.utils.timezone import date_today


@shared_task
def rfc_editor_index_update_task(full_index=False):
    """Update metadata from the RFC index
    
    Default is to examine only changes in the past 365 days. Call with full_index=True to update
    the full RFC index.
    
    According to comments on the original script, a year's worth took about 20s on production as of
    August 2022
    """
    skip_date = None if full_index else date_today() - datetime.timedelta(days=365)
    log.log(
        "Updating document metadata from RFC index going back to {since}, from {url}".format(
            since=skip_date if skip_date is not None else "the beginning",
            url=settings.RFC_EDITOR_INDEX_URL,
        )
    )
    try:
        response = requests.get(
            settings.RFC_EDITOR_INDEX_URL,
            timeout=30,  # seconds
        )
    except requests.Timeout as exc:
        log.log(f'GET request timed out retrieving RFC editor index: {exc}')
        return  # failed
    rfc_index_xml = response.text
    index_data = parse_index(io.StringIO(rfc_index_xml))
    try:
        response = requests.get(
            settings.RFC_EDITOR_ERRATA_JSON_URL,
            timeout=30,  # seconds
        )
    except requests.Timeout as exc:
        log.log(f'GET request timed out retrieving RFC editor errata: {exc}')
        return  # failed
    errata_data = response.json()   
    if len(index_data) < MIN_INDEX_RESULTS:
        log.log("Not enough index entries, only %s" % len(index_data))
        return  # failed
    if len(errata_data) < MIN_ERRATA_RESULTS:
        log.log("Not enough errata entries, only %s" % len(errata_data))
        return  # failed
    for rfc_number, changes, doc, rfc_published in update_docs_from_rfc_index(
        index_data, errata_data, skip_older_than_date=str(skip_date)
    ):
        for c in changes:
            log.log("RFC%s, %s: %s" % (rfc_number, doc.name, c))
