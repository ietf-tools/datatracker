# Copyright The IETF Trust 2024, All Rights Reserved
from celery import shared_task

from ietf.doc.models import DocEvent 
from ietf.utils.log import log


@shared_task
def notify_event_to_subscribers_task(event_id):
    from .utils import notify_event_to_subscribers
    event = DocEvent.objects.filter(pk=event_id).first()
    if event is None:
        log(f"Unable to send subscriber notifications because DocEvent {event_id} was not found")
    else:
        notify_event_to_subscribers(event)
