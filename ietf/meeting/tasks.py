# Copyright The IETF Trust 2024-2026, All Rights Reserved
#
# Celery task definitions
#
import datetime

from itertools import batched

from celery import shared_task, chain
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.utils import timezone

from ietf.utils import log
from .models import Meeting
from .utils import (
    generate_proceedings_content,
    resolve_materials_for_one_meeting,
    store_blobs_for_one_meeting,
)
from .views import generate_agenda_data
from .utils import fetch_attendance_from_meetings


@shared_task
def agenda_data_refresh(num=None):
    """Refresh agenda data for one plenary meeting

    If `num` is `None`, refreshes data for the current meeting.
    """
    log.log(f"Refreshing agenda data for IETF-{num}")
    generate_agenda_data(num, force_refresh=True)


@shared_task
def agenda_data_refresh_all_task(*, batch_size=10):
    """Refresh agenda data for all plenary meetings

    Executes as a chain of tasks, each computing up to `batch_size` meetings
    in a single task.
    """
    meeting_numbers = sorted(
        Meeting.objects.annotate(
            number_as_int=Cast("number", output_field=IntegerField())
        )
        .filter(type_id="ietf", number_as_int__gt=64)
        .values_list("number_as_int", flat=True)
    )
    # Batch using chained maps rather than celery.chunk so we only use one worker
    # at a time.
    batched_task_chain = chain(
        *(
            agenda_data_refresh.map(nums)
            for nums in batched(meeting_numbers, batch_size)
        )
    )
    batched_task_chain.delay()


@shared_task
def proceedings_content_refresh_task(*, all=False):
    """Refresh meeting proceedings cache

    If `all` is `False`, then refreshes the cache for meetings whose numbers modulo
    24 equal the current hour number (0-23). Scheduling the task once per hour will
    then result in all proceedings being recomputed daily, with no more than two per
    hour (now) or a few per hour in the next decade. That keeps the computation time
    to under a couple minutes on our current production system.

    If `all` is True, refreshes all meetings
    """
    now = timezone.now()

    for meeting in Meeting.objects.filter(type_id="ietf").order_by("number"):
        if meeting.proceedings_format_version == 1:
            continue  # skip v1 proceedings, they're stored externally
        num = meeting.get_number()  # convert str -> int
        if num is None:
            log.log(
                f"Not refreshing proceedings for meeting {meeting.number}: "
                f"type is 'ietf' but get_number() returned None"
            )
        elif all or (num % 24 == now.hour):
            log.log(f"Refreshing proceedings for meeting {meeting.number}...")
            generate_proceedings_content(meeting, force_refresh=True)


@shared_task
def fetch_meeting_attendance_task():
    # fetch most recent two meetings
    meetings = Meeting.objects.filter(type="ietf", date__lte=timezone.now()).order_by(
        "-date"
    )[:2]
    try:
        stats = fetch_attendance_from_meetings(meetings)
    except RuntimeError as err:
        log.log(f"Error in fetch_meeting_attendance_task: {err}")
    else:
        for meeting, meeting_stats in zip(meetings, stats):
            log.log(
                "Fetched data for meeting {:>3}: {:4d} created, {:4d} updated, {:4d} deleted, {:4d} processed".format(
                    meeting.number,
                    meeting_stats["created"],
                    meeting_stats["updated"],
                    meeting_stats["deleted"],
                    meeting_stats["processed"],
                )
            )


def _select_meetings(
    meetings: list[str] | None = None,
    meetings_since: str | None = None,
    meetings_until: str | None = None,
):  # nyah
    """Select meetings by number or date range"""
    # IETF-1 = 1986-01-16
    EARLIEST_MEETING_DATE = datetime.datetime(1986, 1, 1)
    meetings_since_dt: datetime.datetime | None = None
    meetings_until_dt: datetime.datetime | None = None

    if meetings_since == "zero":
        meetings_since_dt = EARLIEST_MEETING_DATE
    elif meetings_since is not None:
        try:
            meetings_since_dt = datetime.datetime.fromisoformat(meetings_since)
        except ValueError:
            log.log(
                "Failed to parse meetings_since='{meetings_since}' with fromisoformat"
            )
            raise

    if meetings_until is not None:
        try:
            meetings_until_dt = datetime.datetime.fromisoformat(meetings_until)
        except ValueError:
            log.log(
                "Failed to parse meetings_until='{meetings_until}' with fromisoformat"
            )
            raise
        if meetings_since_dt is None:
            # if we only got meetings_until, start from the first meeting
            meetings_since_dt = EARLIEST_MEETING_DATE

    if meetings is None:
        if meetings_since_dt is None:
            log.log("No meetings requested, doing nothing.")
            return Meeting.objects.none()
        meetings_qs = Meeting.objects.filter(date__gte=meetings_since_dt)
        if meetings_until_dt is not None:
            meetings_qs = meetings_qs.filter(date__lte=meetings_until_dt)
            log.log(
                "Selecting meetings between "
                f"{meetings_since_dt} and {meetings_until_dt}"
            )
        else:
            log.log(f"Selecting meetings since {meetings_since_dt}")
    else:
        if meetings_since_dt is not None:
            log.log(
                "Ignoring meetings_since and meetings_until "
                "because specific meetings were requested."
            )
        meetings_qs = Meeting.objects.filter(number__in=meetings)
    return meetings_qs


@shared_task
def resolve_meeting_materials_task(
    *,  # only allow kw arguments
    meetings: list[str] | None = None,
    meetings_since: str | None = None,
    meetings_until: str | None = None,
):
    """Run materials resolver on meetings

    Can request a set of meetings by number by passing a list in the meetings arg, or
    by range by passing an iso-format timestamps in meetings_since / meetings_until.
    To select all meetings, set meetings_since="zero" and omit other parameters.
    """
    meetings_qs = _select_meetings(meetings, meetings_since, meetings_until)
    for meeting in meetings_qs.order_by("date"):
        log.log(
            f"Resolving materials for {meeting.type_id} "
            f"meeting {meeting.number} ({meeting.date})..."
        )
        mark = timezone.now()
        try:
            resolve_materials_for_one_meeting(meeting)
        except Exception as err:
            log.log(
                "Exception raised while resolving materials for "
                f"meeting {meeting.number}: {err}"
            )
        else:
            log.log(
                f"Resolved in {(timezone.now() - mark).total_seconds():0.3f} seconds."
            )


@shared_task
def store_meeting_materials_as_blobs_task(
    *,  # only allow kw arguments
    meetings: list[str] | None = None,
    meetings_since: str | None = None,
    meetings_until: str | None = None,
):
    """Push meeting materials into the blob store

    Can request a set of meetings by number by passing a list in the meetings arg, or
    by range by passing an iso-format timestamps in meetings_since / meetings_until.
    To select all meetings, set meetings_since="zero" and omit other parameters.
    """
    meetings_qs = _select_meetings(meetings, meetings_since, meetings_until)
    for meeting in meetings_qs.order_by("date"):
        log.log(
            f"Creating blobs for materials for {meeting.type_id} "
            f"meeting {meeting.number} ({meeting.date})..."
        )
        mark = timezone.now()
        try:
            store_blobs_for_one_meeting(meeting)
        except Exception as err:
            log.log(
                "Exception raised while creating blobs for "
                f"meeting {meeting.number}: {err}"
            )
        else:
            log.log(
                f"Blobs created in {(timezone.now() - mark).total_seconds():0.3f} seconds."
            )
