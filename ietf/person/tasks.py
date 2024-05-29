# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime

from celery import shared_task
from django.utils import timezone

from .models import PersonApiKeyEvent


@shared_task
def purge_personal_api_key_events(keep_days):
    now = timezone.now()
    old_events = PersonApiKeyEvent.objects.filter(time__lt=now - datetime.timedelta(days=keep_days))
    old_events.delete()
