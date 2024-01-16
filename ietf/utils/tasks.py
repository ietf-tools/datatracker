# Copyright The IETF Trust 2023, All Rights Reserved
#
# Top-level Celery task definitions
#
from celery import shared_task

from ietf.review.tasks import send_review_reminders_task
from ietf.stats.tasks import fetch_meeting_attendance_task


@shared_task
def daily_task():
    fetch_meeting_attendance_task.delay()
    send_review_reminders_task.delay()

