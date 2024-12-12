# Copyright The IETF Trust 2024, All Rights Reserved

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from ietf.doc.models import DocEvent
from .tasks import notify_event_to_subscribers_task


def notify_of_event(event: DocEvent):
    """Send subscriber notification emails for a 'draft'-related DocEvent

    If the event is attached to a draft of type 'doc', queues a task to send notification emails to
    community list subscribers. No emails will be sent when SERVER_MODE is 'test'.
    """
    if event.doc.type_id != "draft":
        return

    if getattr(event, "skip_community_list_notification", False):
        return

    # kludge alert: queuing a celery task in response to a signal can cause unexpected attempts to
    # start a Celery task during tests. To prevent this, don't queue a celery task if we're running
    # tests.
    if settings.SERVER_MODE != "test":
        # Wrap in on_commit in case a transaction is open
        transaction.on_commit(
            lambda: notify_event_to_subscribers_task.delay(event_id=event.pk)
        )


# dispatch_uid ensures only a single signal receiver binding is made
@receiver(post_save, dispatch_uid="notify_of_events_receiver_uid")
def notify_of_events_receiver(sender, instance, **kwargs):
    """Call notify_of_event after saving a new DocEvent"""
    if not isinstance(instance, DocEvent):
        return

    if not kwargs.get("created", False):
        return  # only notify on creation

    notify_of_event(instance)
