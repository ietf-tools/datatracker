# Copyright The IETF Trust 2024 All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task
from smtplib import SMTPException

from ietf.message.utils import send_scheduled_message_from_send_queue
from ietf.message.models import SendQueue
from ietf.review.tasks import send_review_reminders_task
from ietf.stats.tasks import fetch_meeting_attendance_task
from ietf.sync.tasks import rfc_editor_index_update_task
from ietf.utils import log
from ietf.utils.mail import log_smtp_exception, send_error_email


@shared_task
def every_15m_task():
    """Queue four-times-hourly tasks for execution"""
    # todo decide whether we want this to be a meta-task or to individually schedule the tasks
    send_scheduled_mail_task.delay()
    # Parse the last year of RFC index data to get new RFCs. Needed until
    # https://github.com/ietf-tools/datatracker/issues/3734 is addressed.
    rfc_editor_index_update_task.delay(full_index=False)


@shared_task
def daily_task():
    """Queue daily tasks for execution"""
    fetch_meeting_attendance_task.delay()
    send_review_reminders_task.delay()
    # Run an extended version of the rfc editor update to catch changes
    # with backdated timestamps
    rfc_editor_index_update_task.delay(full_index=True)


@shared_task
def send_scheduled_mail_task():
    """Send scheduled email
    
    This is equivalent to `ietf/bin/send-scheduled-mail all`, which was the only form used in the cron job.
    """
    needs_sending = SendQueue.objects.filter(sent_at=None).select_related("message")
    for s in needs_sending:
        try:
            send_scheduled_message_from_send_queue(s)
            log.log('Sent scheduled message %s "%s"' % (s.id, s.message.subject))
        except SMTPException as e:
            log_smtp_exception(e)
            send_error_email(e)
