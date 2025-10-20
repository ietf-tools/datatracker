# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime

from celery import shared_task
from django.utils import timezone

from ietf.utils import log
from .models import Meeting
from .utils import generate_proceedings_content, resolve_materials_for_one_meeting
from .views import generate_agenda_data
from .utils import fetch_attendance_from_meetings


@shared_task
def agenda_data_refresh():
    generate_agenda_data(force_refresh=True)


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
    meetings = Meeting.objects.filter(type="ietf", date__lte=timezone.now()).order_by("-date")[:2]
    try:
        stats = fetch_attendance_from_meetings(meetings)
    except RuntimeError as err:
        log.log(f"Error in fetch_meeting_attendance_task: {err}")
    else:
        for meeting, meeting_stats in zip(meetings, stats):
            log.log(
                "Fetched data for meeting {:>3}: {:4d} created, {:4d} updated, {:4d} deleted, {:4d} processed".format(
                    meeting.number, meeting_stats['created'], meeting_stats['updated'], meeting_stats['deleted'],
                    meeting_stats['processed']
                )
            )


@shared_task
def resolve_meeting_materials_task(
    *, meetings: list[str]=None, meetings_since: str=None, meetings_until: str=None
):
    """Run materials resolver on meetings
    
    Can request a set of meetings by number by passing a list in the meetings arg, or
    by range by passing an iso-format timestamps in meetings_since / meetings_until.
    To select all meetings, set meetings_since="zero" and omit other parameters. 
    """
    # IETF-1 = 1986-01-16
    EARLIEST_MEETING_DATE = datetime.datetime(1986, 1, 1)
    if meetings_since == "zero":
        meetings_since = EARLIEST_MEETING_DATE
    elif meetings_since is not None:
        meetings_since = datetime.datetime.fromisoformat(meetings_since)

    if meetings_until is not None:
        meetings_until = datetime.datetime.fromisoformat(meetings_until)
        if meetings_since is None:
            # if we only got meetings_until, start from the first meeting
            meetings_since = EARLIEST_MEETING_DATE

    if meetings is None:
        if meetings_since is None:
            log.log("No meetings requested, doing nothing.")
            return
        meetings = Meeting.objects.filter(date__gte=meetings_since)
        if meetings_until is not None:
            meetings = meetings.filter(date__lte=meetings_until)
            log.log(
                "Resolving materials for meetings "
                f"between {meetings_since} and {meetings_until}"
            )
        else:
            log.log(f"Resolving materials for meetings since {meetings_since}")
    else:
        if meetings_since is not None:
            log.log("Ignoring meetings_since because specific meetings were requested.")
        meetings = Meeting.objects.filter(number__in=meetings)
    for meeting in meetings.order_by("date"):
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
            log.log(f"Resolved in {(timezone.now() - mark).total_seconds():0.3f} seconds.")
