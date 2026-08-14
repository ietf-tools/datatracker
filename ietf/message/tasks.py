# Copyright The IETF Trust 2024 All Rights Reserved
#
# Celery task definitions
#
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
def retry_send_messages_by_pk_task(message_pks: list, resend=False):
    """Task to retry sending Messages by PK
    
    Sends Messages whose PK is included in the list.
    Only previously unsent messages are sent unless `resend` is true.
    """
    log.log(
        "retry_send_messages_by_pk_task: "
        "retrying send of Message PKs [{}] (resend={})".format(
            ", ".join(str(pk) for pk in message_pks),
            resend,
        )
    )
    retry_send_messages(
        messages=Message.objects.filter(pk__in=message_pks),
        resend=resend,
    )
