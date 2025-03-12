# Copyright The IETF Trust 2024 All Rights Reserved
#
# Celery task definitions
#
import datetime

from celery import shared_task
from smtplib import SMTPException

from ietf.message.utils import send_scheduled_message_from_send_queue, retry_send_messages
from ietf.message.models import SendQueue, Message
from ietf.utils import log
from ietf.utils.mail import log_smtp_exception, send_error_email


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


@shared_task
def retry_send_messages_by_pk_task(message_pks, resend=False):
    """Task to retry sending Messages by PK
    
    Sends Messages whose PK is included in the list.
    Only previously unsent messages are sent unless `resend` is true.
    """
    retry_send_messages(
        messages=Message.objects.filter(pk__in=message_pks),
        resend=resend,
    )

@shared_task
def retry_send_messages_by_time_task(
    start_time: str=None,
    end_time: str=None,
    resend=False,
):
    """Task to retry sending Messages by date
    
    Times are ISO-format timestamps. If a timezone is not specified, UTC is used.
    Only previously unsent messages are sent unless `resend` is True.
    
    Start and end time bounds are both inclusive.
    """
    def _parse_time(time_str):
        dt = datetime.datetime.fromisoformat(time_str)
        # Use UTC if not specified
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt

    # Start with everything
    messages = Message.objects.all()
    
    # Apply the start time bound, if given
    if start_time is not None:
        try:
            start_datetime = _parse_time(start_time) 
        except ValueError:
            log.log(
                f"retry_send_messages_by_time_task: "
                f"unable to parse start_time '{start_time}' as an ISO timestamp"
            )
            raise
        messages = messages.filter(time__gte=start_datetime)

    # Apply tne end time bound, if given
    if end_time is not None:
        try:
            end_datetime = _parse_time(end_time) 
        except ValueError:
            log.log(
                f"retry_send_messages_by_time_task: "
                f"unable to parse end_time '{end_time}' as an ISO timestamp"
            )
            raise
        messages = messages.filter(time__lte=end_datetime)

    retry_send_messages(messages=messages, resend=resend)
