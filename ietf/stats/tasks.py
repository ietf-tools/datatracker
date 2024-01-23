# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task
from django.utils import timezone

from ietf.meeting.models import Meeting
from ietf.stats.utils import fetch_attendance_from_meetings
from ietf.utils import log


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
                "Fetched data for meeting {:>3}: {:4d} processed, {:4d} added, {:4d} in table".format(
                    meeting.number, meeting_stats.processed, meeting_stats.added, meeting_stats.total
                )
            )
