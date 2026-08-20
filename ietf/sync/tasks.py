# Copyright The IETF Trust 2024-2026, All Rights Reserved
#
# Celery task definitions
#
import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
import requests

from celery import shared_task

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ietf.doc.models import (
    DocEvent,
    DocTagName,
    Document,
    RelatedDocument,
    RpcActionHolderOpenEntry,
    RpcAssignmentDocEvent,
    State,
)
from ietf.doc.tasks import rebuild_reference_relations_task
from ietf.doc.utils import add_state_change_event, new_state_change_event, update_action_holders
from ietf.person.models import Person
from ietf.utils.mail import send_mail_text
from ietf.sync import iana
from ietf.sync.errata import (
    errata_are_dirty,
    mark_errata_as_processed,
    update_errata_from_rfceditor,
)
from ietf.sync.rfcindex import (
    create_bcp_txt_index,
    create_fyi_txt_index,
    create_rfc_txt_index,
    create_rfc_xml_index,
    create_std_txt_index,
    rfcindex_is_dirty, mark_rfcindex_as_processed, mark_rfcindex_as_dirty,
)
from ietf.sync.utils import (
    build_from_file_content,
    expand_rfc_number_range_list,
    load_rfcs_into_blobdb,
    rsync_helper,
)
from ietf.utils import log


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

    def batched(l, n):
        """Split list l up in batches of max size n.

        For Python 3.12 or later, replace this with itertools.batched()
        """
        return (l[i : i + n] for i in range(0, len(l), n))

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
        changed_numbers = update_errata_from_rfceditor()
        mark_errata_as_processed(new_processed_time)
        mark_rfcindex_as_dirty()  # ensure any changes are reflected in the indexes
        if changed_numbers:
            update_rfc_json_task.delay(list(changed_numbers))

@shared_task
def update_rfc_json_by_range_list_task(ranges: str) -> None:
    """Regenerate RFC JSON for the RFCs described by a range-list string

    See expand_rfc_number_range_list() for the accepted format (e.g.
    "[1,100,1000-1004]"). Invalid input is logged and otherwise ignored.
    """
    try:
        rfc_numbers = expand_rfc_number_range_list(ranges)
    except ValueError as e:
        log.log(
            f"update_rfc_json_by_range_list_task: ignoring invalid input "
            f"'{ranges}': {e}"
        )
        return
    if rfc_numbers:
        update_rfc_json_task(rfc_numbers)

@shared_task
def update_rfc_json_task(rfc_numbers: list[int]) -> None:
    from ietf.doc.utils_rfc_json import generate_rfc_json
    from ietf.sync.rfcindex import get_publication_std_levels

    try:
        pub_levels = get_publication_std_levels()
    except Exception as e:
        log.log(f"update_rfc_json_task: failed to get publication std levels: {e}")
        return
    for rfc_number in rfc_numbers:
        try:
            generate_rfc_json(rfc_number, pub_levels=pub_levels)
        except Exception as e:
            log.log(f"update_rfc_json_task: failed for RFC {rfc_number}: {e}")


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


# Human-readable labels for the RPC publication queue "Status", mirroring the
# ietf-tools/queue website (website/app/utils/queue.ts, renderAssignmentsByRoles)
# so the datatracker shows the same status text that appears at
# https://queue.rfc-editor.org/. The queue "Status" is not a stored field; it is
# derived from the active assignment roles, pending activities, blocking reasons
# and IANA status carried in the purple pubq queue payload.
RPC_QUEUE_ROLE_LABELS = {
    "first_editor": "In Progress (First Edit)",
    "second_editor": "In Progress (Second Edit)",
    "final_review_editor": "In Final Review",
}
# Roles the queue site does not surface in the Status column.
RPC_QUEUE_HIDDEN_ROLES = {"ref_checker", "publisher"}


def _humanize_slug(slug):
    return slug.replace("_", " ")


def _rpc_role_label(role):
    return RPC_QUEUE_ROLE_LABELS.get(role, _humanize_slug(role))


def _rpc_blocking_reason_label(name):
    # Special case mirrored from the queue site's humanFriendlyBlockingReason().
    if name == "Reference: First Edit Incomplete":
        return "Author Input Required"
    return _humanize_slug(name)


def format_rpc_queue_status(obj):
    """Render the RPC publication queue "Status" for a single queue entry.

    Mirrors renderAssignmentsByRoles() from the ietf-tools/queue website so the
    datatracker presents the same status text. ``obj`` is one entry of the purple
    pubq queue payload. Roles, pending activities and blocking reasons are sorted
    so the result is stable (a change to the string is what triggers a new
    RpcAssignmentDocEvent).
    """
    roles = {
        a["role"] for a in (obj.get("assignment_set") or []) if a.get("role")
    }
    is_blocked = "blocked" in roles

    parts = []

    # IANA hold: iana_status "not_completed" while a first_editor is assigned.
    iana_status = obj.get("iana_status") or {}
    if iana_status.get("slug") == "not_completed" and "first_editor" in roles:
        parts.append("IANA hold")

    # Pending activities (only when not blocked): "Awaiting <role>", skipping any
    # role that is already a current assignment. Note the queue site does NOT hide
    # ref_checker/publisher here (only for current-role badges below), so e.g.
    # "Awaiting Reference Checker" can appear.
    if not is_blocked:
        for activity in sorted(
            obj.get("pending_activities") or [],
            key=lambda a: (a.get("name") or a.get("slug") or ""),
        ):
            slug = activity.get("slug")
            if not slug or slug in roles:
                continue
            parts.append(f"Awaiting {activity.get('name') or _humanize_slug(slug)}")

    # Current assignment roles (ref_checker/publisher hidden). Blocking reason
    # names are appended to the "blocked" role.
    blocking_names = sorted(
        _rpc_blocking_reason_label(br["reason"]["name"])
        for br in (obj.get("blocking_reasons") or [])
        if br.get("reason", {}).get("name")
    )
    for role in sorted(roles - RPC_QUEUE_HIDDEN_ROLES):
        label = _rpc_role_label(role)
        if role == "blocked" and blocking_names:
            label += ": " + ", ".join(blocking_names)
        parts.append(label)

    if not parts:
        return "Awaiting Editor Assignment"
    return ", ".join(parts)


# The datatracker's "(System)" person. The RPC tool substitutes a placeholder
# person of its own whenever no real person was named, and sends that person's
# datatracker id - so an action holder must never be associated with this pk.
# Which pk the RPC tool uses is configurable at its end, hence the separate
# check against the "(System)" person the datatracker actually has.
SYSTEM_PERSON_ID = 1


def _rpc_action_holder_person(holder, system_person):
    """Resolve the datatracker Person for one action holder, if there is one

    Returns None whenever the entry does not name a person the datatracker can
    act on. The RPC tool substitutes its system person when no real person was
    named, and that placeholder must never become an action holder here. Do not
    use "body" to make this decision - the RPC tool's edit path can set or clear
    "body" without touching the person, so it is unreliable in both directions.
    """
    person_id = (holder.get("person") or {}).get("person_id")
    if person_id in (SYSTEM_PERSON_ID, system_person.pk):
        return None
    if holder.get("body"):
        return None  # a body holds the action, not a person
    person = Person.objects.filter(pk=person_id).first()
    if person is None:
        log.log(
            f"process_rpc_queue_task: unknown action holder person {person_id}"
        )
        return None
    if person == system_person or person.pk == SYSTEM_PERSON_ID:
        return None
    return person


def _sync_rpc_action_holders(doc, holders, rfc_number, system_person):
    """Reconcile the open action holder entries for one document"""
    open_purple_ids = []
    for holder in holders:
        if holder.get("completed") is not None:
            # The RPC tool reports completed action holders as well as open
            # ones. Only open ones are kept here, so this line is the only
            # place the datatracker sees a completion happen.
            continue
        RpcActionHolderOpenEntry.objects.update_or_create(
            purple_id=holder["id"],
            defaults=dict(
                document=doc,
                person=_rpc_action_holder_person(holder, system_person),
                body=holder.get("body") or "",
                display_name=holder.get("display_name") or "",
                comment=holder.get("comment") or "",
                rfc_number=rfc_number,
                since_when=parse_datetime(holder["since_when"]),
                deadline=(
                    parse_datetime(holder["deadline"])
                    if holder.get("deadline")
                    else None
                ),
            ),
        )
        open_purple_ids.append(holder["id"])
    # Anything else we were holding for this document has been completed or
    # removed at the RPC tool.
    RpcActionHolderOpenEntry.objects.filter(document=doc).exclude(
        purple_id__in=open_purple_ids
    ).delete()


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

        next_assignments = format_rpc_queue_status(obj)

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

        _sync_rpc_action_holders(
            d, obj.get("actionholder_set") or [], rfc_number, system
        )

        if events:
            d.save_with_history(events)

    for d in (
        Document.objects.exclude(name__in=names)
        .filter(states__type="draft-rfceditor")
        .distinct()
    ):
        d.tags.remove(*iana_ref_tags)
        d.unset_state("draft-rfceditor")
        RpcActionHolderOpenEntry.objects.filter(document=d).delete()
