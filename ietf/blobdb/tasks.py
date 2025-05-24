# Copyright The IETF Trust 2025, All Rights Reserved

import json

from celery import shared_task

from .replication import replicate_blob, ReplicationError


@shared_task(
    autoretry_for=(ReplicationError,), retry_backoff=10, retry_kwargs={"max_retries": 5}
)
def pybob_the_blob_replicator_task(body: str):
    request = json.loads(body)
    bucket = request["bucket"]
    name = request["name"]
    replicate_blob(bucket, name)
