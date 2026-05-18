# Copyright The IETF Trust 2024-2026, All Rights Reserved
#
# Celery task definitions
#
import datetime
import io
from itertools import batched
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from ietf.doc.models import DocEvent, DocTagName, Document, RelatedDocument, RpcAssignmentDocEvent, State
from ietf.doc.tasks import rebuild_reference_relations_task
from ietf.doc.utils import add_state_change_event, new_state_change_event, update_action_holders
from ietf.person.models import Person
from ietf.utils.mail import send_mail_text
from ietf.sync import iana
from ietf.sync import rfceditor
from ietf.sync.bibxml import recreate_rfc_bibxml
from ietf.sync.errata import (
    errata_are_dirty,
    mark_errata_as_processed,
    update_errata_from_rfceditor,
)
from ietf.sync.rfceditor import MIN_QUEUE_RESULTS, parse_queue, update_drafts_from_queue
from ietf.sync.rfcindex import (
    create_bcp_txt_index,
    create_fyi_txt_index,
    create_rfc_txt_index,
    create_rfc_xml_index,
    create_std_txt_index,
    rfcindex_is_dirty,
    mark_rfcindex_as_processed,
    mark_rfcindex_as_dirty,
)
from ietf.sync.utils import build_from_file_content, load_rfcs_into_blobdb, rsync_helper
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
        log.log(f"GET request timed out retrieving RFC editor index: {exc}")
        return  # failed
    rfc_index_xml = response.text
    index_data = rfceditor.parse_index(io.StringIO(rfc_index_xml))
    try:
        response = requests.get(
            settings.RFC_EDITOR_ERRATA_JSON_URL,
            timeout=30,  # seconds
        )
    except requests.Timeout as exc:
        log.log(f"GET request timed out retrieving RFC editor errata: {exc}")
        return  # failed
    errata_data = response.json()
    if len(index_data) < rfceditor.MIN_INDEX_RESULTS:
        log.log("Not enough index entries, only %s" % len(index_data))
        return  # failed
    if len(errata_data) < rfceditor.MIN_ERRATA_RESULTS:
        log.log("Not enough errata entries, only %s" % len(errata_data))
        return  # failed
    newly_published = set()
    for rfc_number, changes, doc, rfc_published in rfceditor.update_docs_from_rfc_index(
        index_data, errata_data, skip_older_than_date=skip_date
    ):
        for c in changes:
            log.log("RFC%s, %s: %s" % (rfc_number, doc.name, c))
        if rfc_published:
            newly_published.add(rfc_number)
    if len(newly_published) > 0:
        rsync_rfcs_from_rfceditor_task.delay(list(newly_published))


@shared_task
def rfc_editor_queue_updates_task():
    log.log(f"Updating RFC Editor queue states from {settings.RFC_EDITOR_QUEUE_URL}")
    try:
        response = requests.get(
            settings.RFC_EDITOR_QUEUE_URL,
            timeout=30,  # seconds
        )
    except requests.Timeout as exc:
        log.log(f"GET request timed out retrieving RFC editor queue: {exc}")
        return  # failed
    drafts, warnings = parse_queue(io.StringIO(response.text))
    for w in warnings:
        log.log(f"Warning: {w}")

    if len(drafts) < MIN_QUEUE_RESULTS:
        log.log("Not enough results, only %s" % len(drafts))
        return  # failed

    changed, warnings = update_drafts_from_queue(drafts)
    for w in warnings:
        log.log(f"Warning: {w}")

    for c in changed:
        log.log(f"Updated {c}")


@shared_task
def iana_changes_update_task():
    # compensate to avoid we ask for something that happened now and then
    # don't get it back because our request interval is slightly off
    CLOCK_SKEW_COMPENSATION = 5  # seconds

    # actually the interface accepts 24 hours, but then we get into
    # trouble with daylights savings - meh
    MAX_INTERVAL_ACCEPTED_BY_IANA = datetime.timedelta(hours=23)

    start = (
        timezone.now()
        - datetime.timedelta(hours=23)
        + datetime.timedelta(
            seconds=CLOCK_SKEW_COMPENSATION,
        )
    )
    end = start + datetime.timedelta(hours=23)

    t = start
    while t < end:
        # the IANA server doesn't allow us to fetch more than a certain
        # period, so loop over the requested period and make multiple
        # requests if necessary

        text = iana.fetch_changes_json(
            settings.IANA_SYNC_CHANGES_URL,
            t,
            min(end, t + MAX_INTERVAL_ACCEPTED_BY_IANA),
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


@shared_task
def iana_protocols_update_task():
    # Earliest date for which we have data suitable to update (was described as
    # "this needs to be the date where this tool is first deployed" in the original
    # iana-protocols-updates script)"
    rfc_must_published_later_than = datetime.datetime(
        2012,
        11,
        26,
        tzinfo=datetime.UTC,
    )

    try:
        response = requests.get(
            settings.IANA_SYNC_PROTOCOLS_URL,
            timeout=30,
        )
    except requests.Timeout as exc:
        log.log(f"GET request timed out retrieving IANA protocols page: {exc}")
        return

    rfc_numbers = iana.parse_protocol_page(response.text)

    for batch in batched(rfc_numbers, 100):
        updated = iana.update_rfc_log_from_protocol_page(
            batch,
            rfc_must_published_later_than,
        )

        for d in updated:
            log.log("Added history entry for %s" % d.display_name())


@shared_task
def fix_subseries_docevents_task():
    """Repairs DocEvents related to bugs around removing docs from subseries

    Removes bogus and repairs the date of non-bogus DocEvents
    about removing RFCs from subseries

    This is designed to be a one-shot task that should be removed
    after running it. It is intended to be safe if it runs more than once.
    """
    log.log("Repairing DocEvents related to bugs around removing docs from subseries")
    bogus_event_descs = [
        "Removed rfc8499 from bcp218",
        "Removed rfc7042 from bcp184",
        "Removed rfc9499 from bcp238",
        "Removed rfc5033 from std74",
        "Removed rfc3228 from bcp55",
        "Removed rfc8109 from std85",
    ]
    DocEvent.objects.filter(
        type="sync_from_rfc_editor", desc__in=bogus_event_descs
    ).delete()
    needs_moment_fix = [
        "Removed rfc8499 from bcp219",
        "Removed rfc7042 from bcp141",
        "Removed rfc5033 from bcp133",
        "Removed rfc3228 from bcp57",
    ]
    # Assumptions (which have been manually verified):
    # 1) each of the above RFCs is obsoleted by exactly one other RFC
    # 2) each of the obsoleting RFCs has exactly one published_rfc docevent
    for desc in needs_moment_fix:
        obsoleted_rfc_name = desc.split(" ")[1]
        obsoleting_rfc = RelatedDocument.objects.get(
            relationship_id="obs", target__name=obsoleted_rfc_name
        ).source
        obsoleting_time = obsoleting_rfc.docevent_set.get(type="published_rfc").time
        DocEvent.objects.filter(type="sync_from_rfc_editor", desc=desc).update(
            time=obsoleting_time
        )


@shared_task
def rsync_rfcs_from_rfceditor_task(rfc_numbers: list[int]):
    log.log(f"Rsyncing rfcs from rfc-editor: {rfc_numbers}")
    from_file = None
    with NamedTemporaryFile(mode="w", delete_on_close=False) as fp:
        fp.write(build_from_file_content(rfc_numbers))
        fp.close()
        from_file = Path(fp.name)
        rsync_helper(
            [
                "-a",
                "--ignore-existing",
                f"--include-from={from_file}",
                "--exclude=*",
                "rsync.rfc-editor.org::rfcs/",
                f"{settings.RFC_PATH}",
            ]
        )
    load_rfcs_into_blobdb(rfc_numbers)

    rebuild_reference_relations_task.delay([f"rfc{num}" for num in rfc_numbers])


@shared_task
def load_rfcs_into_blobdb_task(start: int, end: int):
    """Move file content for rfcs from rfc{start} to rfc{end} inclusive

    As this is expected to be removed once the blobdb is populated, it
    will truncate its work to a coded max end.
    This will not overwrite any existing blob content, and will only
    log a small complaint if asked to load a non-exsiting RFC.
    """
    # Protect us from ourselves
    if end < start:
        return
    if start < 1:
        start = 1
    if end > 11000:  # Arbitrarily chosen
        end = 11000
    load_rfcs_into_blobdb(list(range(start, end + 1)))


@shared_task
def update_errata_from_rfceditor_task():
    if errata_are_dirty():
        # new_processed_time is the *start* of processing so that any changes after
        # this point will trigger another refresh
        new_processed_time = timezone.now()
        update_errata_from_rfceditor()
        mark_errata_as_processed(new_processed_time)
        mark_rfcindex_as_dirty()  # ensure any changes are reflected in the indexes


@shared_task
def refresh_rfc_index_task():
    if rfcindex_is_dirty():
        # new_processed_time is the *start* of processing so that any changes after
        # this point will trigger another refresh
        new_processed_time = timezone.now()

        try:
            create_rfc_txt_index()
        except Exception as e:
            log.log(f"Error: failure in creating rfc-index.txt. {e}")
            pass

        try:
            create_rfc_xml_index()
        except Exception as e:
            log.log(f"Error: failure in creating rfc-index.xml. {e}")
            pass

        try:
            create_bcp_txt_index()
        except Exception as e:
            log.log(f"Error: failure in creating bcp-index.txt. {e}")
            pass

        try:
            create_std_txt_index()
        except Exception as e:
            log.log(f"Error: failure in creating std-index.txt. {e}")
            pass

        try:
            create_fyi_txt_index()
        except Exception as e:
            log.log(f"Error: failure in creating fyi-index.txt. {e}")
            pass

        mark_rfcindex_as_processed(new_processed_time)


@shared_task
def process_rpc_queue_task(data: list):
    in_progress_state = State.objects.get(
        used=True, type="draft-rfceditor", slug="in_progress"
    )
    blocked_state = State.objects.get(used=True, type="draft-rfceditor", slug="blocked")
    system = Person.objects.get(name="(System)")
    iana_ref_tags = list(DocTagName.objects.filter(slug__in=["iana", "ref"]))

    names = [obj["name"] for obj in data]
    docs_in_db = {
        d.name: d for d in Document.objects.filter(type="draft", name__in=names)
    }

    for obj in data:
        name = obj["name"]
        if name not in docs_in_db:
            log.log(f"process_rpc_queue_task: unknown document {name}")
            continue

        d = docs_in_db[name]
        events = []
        prev_state = d.get_state("draft-rfceditor")

        # Same check as ietf.sync.rfceditor.update_drafts_from_queue:
        # if this document just arrived at the RFC Editor for the first time, record it.
        if (
            d.get_state_slug("draft-iesg") == "ann"
            and not prev_state
            and not d.latest_event(DocEvent, type="rfc_editor_received_announcement")
        ):
            e = DocEvent(
                doc=d, rev=d.rev, by=system, type="rfc_editor_received_announcement"
            )
            e.desc = "Announcement was received by RFC Editor"
            e.save()
            send_mail_text(
                None,
                "iesg-secretary@ietf.org",
                None,
                "%s in RFC Editor queue" % d.name,
                "The announcement for %s has been received by the RFC Editor." % d.name,
            )
            prev_iesg_state = State.objects.get(
                used=True, type="draft-iesg", slug="ann"
            )
            next_iesg_state = State.objects.get(
                used=True, type="draft-iesg", slug="rfcqueue"
            )
            d.set_state(next_iesg_state)
            e = add_state_change_event(d, system, prev_iesg_state, next_iesg_state)
            if e:
                events.append(e)
            e = update_action_holders(d, prev_iesg_state, next_iesg_state)
            if e:
                events.append(e)

        is_blocked = any(a["role"] == "blocked" for a in obj.get("assignment_set", []))
        next_state = blocked_state if is_blocked else in_progress_state

        if prev_state != next_state:
            d.set_state(next_state)
            e = new_state_change_event(d, system, prev_state, next_state)
            if e:
                e.save()
                events.append(e)

        roles = sorted(a["role"] for a in obj.get("assignment_set", []))
        next_assignments = ", ".join(roles)
        blocking_names = sorted(
            br["reason"]["name"] for br in obj.get("blocking_reasons", [])
        )
        if blocking_names:
            next_assignments += ": " + ", ".join(blocking_names)

        if next_assignments == "":
            next_assignments = "Awaiting Editor Assignment"

        prev_assignments_event = d.latest_event(
            RpcAssignmentDocEvent, type="changed_rpc_assignments"
        )
        prev_assignments = (
            prev_assignments_event.assignments if prev_assignments_event else None
        )

        if next_assignments != prev_assignments:
            e = RpcAssignmentDocEvent(
                doc=d,
                rev=d.rev,
                by=system,
                type="changed_rpc_assignments",
                assignments=next_assignments,
            )
            e.desc = f"RPC status changed to {next_assignments}"
            if prev_assignments is not None and prev_assignments != "":
                e.desc += f" from {prev_assignments}"
            e.save()
            events.append(e)

        rfc_number = obj.get("rfc_number")
        if obj.get("final_approval") and rfc_number:
            d.documenturl_set.update_or_create(
                tag_id="auth48",
                defaults=dict(
                    url=f"{settings.RFC_EDITOR_QUEUE_SITE_BASE_URL}/final-review/rfc{rfc_number}/"
                ),
            )
        else:
            d.documenturl_set.filter(tag_id="auth48").delete()

        d.tags.remove(*iana_ref_tags)

        if events:
            d.save_with_history(events)

    for d in (
        Document.objects.exclude(name__in=names)
        .filter(states__type="draft-rfceditor")
        .distinct()
    ):
        d.tags.remove(*iana_ref_tags)
        d.unset_state("draft-rfceditor")


@shared_task
def recreate_rfc_bibxml_task():
    recreate_rfc_bibxml()