# Copyright The IETF Trust 2024, All Rights Reserved

from celery import shared_task

from .utils import send_reminders


@shared_task
def send_nomcom_reminders_task():
    send_reminders()
