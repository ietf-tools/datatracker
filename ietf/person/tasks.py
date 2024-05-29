# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime

from celery import shared_task
from django.utils import timezone

from ietf.utils import log
from .models import PersonApiKeyEvent


@shared_task
def purge_personal_api_key_events_task(keep_days):
    keep_since = timezone.now() - datetime.timedelta(days=keep_days)
    old_events = PersonApiKeyEvent.objects.filter(time__lt=keep_since)
    count = len(old_events)
    old_events.delete()
    log.log(f"Deleted {count} PersonApiKeyEvents older than {keep_since}")
