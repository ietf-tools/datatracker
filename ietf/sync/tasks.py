# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime
import io
import requests
from celery import shared_task

from django.conf import settings
from django.utils import timezone

from ietf.sync import iana
from ietf.sync import rfceditor
from ietf.utils import log
from ietf.utils.timezone import date_today


@shared_task
def rfc_editor_index_update_task(full_index=False):
    """Update metadata from the RFC index
    
    Default is to examine only changes in the past 365 days. Call with full_index=True to update
    the full RFC index.
    
    According to comments on the original script, a year's worth took about 20s on production as of
    August 2022
    
    The original rfc-editor-index-update script had a long-disabled provision for running the
    rebuild_reference_relations scripts after the update. That has not been brought over
    at all because it should be implemented as its own task if it is needed.
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
    index_data = rfceditor.parse_index(io.StringIO(rfc_index_xml))
    try:
        response = requests.get(
            settings.RFC_EDITOR_ERRATA_JSON_URL,
            timeout=30,  # seconds
        )
    except requests.Timeout as exc:
        log.log(f'GET request timed out retrieving RFC editor errata: {exc}')
        return  # failed
    errata_data = response.json()   
    if len(index_data) < rfceditor.MIN_INDEX_RESULTS:
        log.log("Not enough index entries, only %s" % len(index_data))
        return  # failed
    if len(errata_data) < rfceditor.MIN_ERRATA_RESULTS:
        log.log("Not enough errata entries, only %s" % len(errata_data))
        return  # failed
    for rfc_number, changes, doc, rfc_published in rfceditor.update_docs_from_rfc_index(
        index_data, errata_data, skip_older_than_date=skip_date
    ):
        for c in changes:
            log.log("RFC%s, %s: %s" % (rfc_number, doc.name, c))


@shared_task
def iana_changes_updates_task():
    # compensate to avoid we ask for something that happened now and then
    # don't get it back because our request interval is slightly off
    CLOCK_SKEW_COMPENSATION = 5  # seconds

    # actually the interface accepts 24 hours, but then we get into
    # trouble with daylights savings - meh
    MAX_INTERVAL_ACCEPTED_BY_IANA = datetime.timedelta(hours=23)

    start = (
        timezone.now() 
        - datetime.timedelta(hours=23) 
        + datetime.timedelta(seconds=CLOCK_SKEW_COMPENSATION,)
    )
    end = start + datetime.timedelta(hours=23)

    t = start
    while t < end:
        # the IANA server doesn't allow us to fetch more than a certain
        # period, so loop over the requested period and make multiple
        # requests if necessary

        text = iana.fetch_changes_json(
            settings.IANA_SYNC_CHANGES_URL, t, min(end, t + MAX_INTERVAL_ACCEPTED_BY_IANA)
        )
        log.log(f"Retrieved the JSON: {text}")

        changes = iana.parse_changes_json(text)
        added_events, warnings = iana.update_history_with_changes(
            changes, send_email=True
        )

        for e in added_events:
            log.log(
                f"Added event for {e.doc_id} {e.time}: {e.desc} (parsed json: {e.json})"
            )

        for w in warnings:
            log.log(f"WARNING: {w}")

        t += MAX_INTERVAL_ACCEPTED_BY_IANA
