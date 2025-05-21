# Copyright The IETF Trust 2025, All Rights Reserved
from collections import namedtuple
from io import BytesIO
from typing import Optional

from django.core.files.storage import storages
from django.db import connections
import json

from celery import shared_task

from ietf.utils import log


def fetch_blob_via_sql(bucket: str, name: str) -> Optional[namedtuple]:
    blobdb_connection = connections["blobdb"]
    cursor = blobdb_connection.cursor()
    cursor.execute(
        """
        SELECT content, checksum, mtime, content_type FROM blobdb_blob
        WHERE bucket=%s AND name=%s LIMIT 1
        """,
        [bucket, name],
    )
    row = cursor.fetchone()
    BlobTuple = namedtuple("BlobTuple", [col[0] for col in cursor.description])
    return None if row is None else BlobTuple(*row)


@shared_task
def pybob_the_blob_replicator_task(body: str):
    request = json.loads(body)
    bucket = request["bucket"]
    name = request["name"]
    destination_storage = storages[f"r2-{bucket}"]

    blob = fetch_blob_via_sql(bucket, name)
    if blob is None:
        destination_storage.delete(name)
    else:
        # Add metadata expected by the MetadataS3Storage
        file_with_metadata = BytesIO(blob.content)
        file_with_metadata.content_type = blob.content_type
        file_with_metadata.custom_metadata = {
            "sha384": blob.checksum,
            "mtime": blob.mtime,
        }
        destination_storage.save(name, file_with_metadata)
