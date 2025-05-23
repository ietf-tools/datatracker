# Copyright The IETF Trust 2025, All Rights Reserved

import json

from celery import shared_task

from .replication import replicate_blob


@shared_task
def pybob_the_blob_replicator_task(body: str):
    request = json.loads(body)
    bucket = request["bucket"]
    name = request["name"]
    replicate_blob(bucket, name)
