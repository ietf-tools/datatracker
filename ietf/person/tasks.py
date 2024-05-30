# Copyright The IETF Trust 2024, All Rights Reserved
#
# Celery task definitions
#
import datetime

from celery import shared_task

from django.conf import settings
from django.utils import timezone

from ietf.utils import log
from ietf.utils.mail import send_mail
from .models import PersonalApiKey, PersonApiKeyEvent


@shared_task
def send_apikey_usage_emails_task(days):
    """Send usage emails to Persons who have API keys"""
    earliest = timezone.now() - datetime.timedelta(days=days)
    keys = PersonalApiKey.objects.filter(
        valid=True,
        personapikeyevent__time__gt=earliest,
    ).distinct()
    for key in keys:
        events = PersonApiKeyEvent.objects.filter(key=key, time__gt=earliest)
        count = events.count()
        events = events[:32]
        if count:
            key_name = key.hash()[:8]
            subject = "API key usage for key '%s' for the last %s days" % (
                key_name,
                days,
            )
            to = key.person.email_address()
            frm = settings.DEFAULT_FROM_EMAIL
            send_mail(
                None,
                to,
                frm,
                subject,
                "utils/apikey_usage_report.txt",
                {
                    "person": key.person,
                    "days": days,
                    "key": key,
                    "key_name": key_name,
                    "count": count,
                    "events": events,
                },
            )

@shared_task
def purge_personal_api_key_events_task(keep_days):
    keep_since = timezone.now() - datetime.timedelta(days=keep_days)
    old_events = PersonApiKeyEvent.objects.filter(time__lt=keep_since)
    count = len(old_events)
    old_events.delete()
    log.log(f"Deleted {count} PersonApiKeyEvents older than {keep_since}")
