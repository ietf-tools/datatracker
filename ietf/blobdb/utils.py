# Copyright The IETF Trust 2026, All Rights Reserved
import json
from functools import partial

from django.db import transaction

from ietf.blobdb.replication import replication_enabled
from ietf.blobdb.tasks import pybob_the_blob_replicator_task


def queue_for_replication(bucket: str, name: str, using: str | None=None):
    """Queue a blob for replication
    
    This is private to the blobdb app. Do not call it directly from other apps.
    """
    if not replication_enabled(bucket):
        return

    # For now, fire a celery task we've arranged to guarantee in-order processing.
    # Later becomes pushing an event onto a queue to a dedicated worker.
    transaction.on_commit(
        partial(
            pybob_the_blob_replicator_task.delay,
            json.dumps(
                {
                    "name": name,
                    "bucket": bucket,
                }
            )
        ),
        using=using,
    )
