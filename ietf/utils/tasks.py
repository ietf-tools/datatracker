# Copyright The IETF Trust 2024 All Rights Reserved
#
# Celery task definitions
#
from celery import shared_task
from smtplib import SMTPException

from ietf.message.utils import send_scheduled_message_from_send_queue
from ietf.message.models import SendQueue
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
