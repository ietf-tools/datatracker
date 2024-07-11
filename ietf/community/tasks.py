# Copyright The IETF Trust 2024, All Rights Reserved
from celery import shared_task

from ietf.doc.models import DocEvent 
from .utils import notify_event_to_subscribers


@shared_task
def notify_event_to_subscribers_task(event_id):
    event = DocEvent.objects.get(pk=event_id)
    notify_event_to_subscribers(event)
