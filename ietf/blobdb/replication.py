# Copyright The IETF Trust 2025, All Rights Reserved
from collections import namedtuple
from io import BytesIO
from typing import Optional

from django.conf import settings
from django.core.files import File
from django.core.files.storage import storages
from django.db import connections


DEFAULT_SETTINGS = {
    "ENABLED": False,
    "DEST_STORAGE_PATTERN": "r2-{bucket}",
}


class SimpleMetadataFile(File):
    def __init__(self, file, name=None):
        super().__init__(file, name)
        self.custom_metadata = {}
        self.content_type = ""


def get_replication_settings():
    return DEFAULT_SETTINGS | getattr(settings, "BLOBDB_REPLICATION", {})


def validate_replicator_settings():
    replicator_settings = get_replication_settings()
    unknown_settings = set(DEFAULT_SETTINGS.keys()) - set(replicator_settings.keys())
    if len(unknown_settings) > 0:
        raise RuntimeError(
            f"Unrecognized BLOBDB_REPLICATOR settings: {', '.join(str(unknown_settings))}"
        )
    pattern = replicator_settings["DEST_STORAGE_PATTERN"]
    if not isinstance(pattern, str):
        raise RuntimeError(
            f"DEST_STORAGE_PATTERN must be a str, not {type(pattern).__name__}"
        )
    if "{bucket}" not in pattern:
        raise RuntimeError(
            f"DEST_STORAGE_PATTERN must contain the substring '{{bucket}}' (found '{pattern}')"
        )


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


def destination_storage_for(bucket: str):
    pattern = get_replication_settings()["DEST_STORAGE_PATTERN"]
    storage_name = pattern.format(bucket=bucket)
    return storages[storage_name]


def replicate_blob(bucket, name):
    destination_storage = destination_storage_for(bucket)

    blob = fetch_blob_via_sql(bucket, name)
    if blob is None:
        destination_storage.delete(name)
    else:
        # Add metadata expected by the MetadataS3Storage
        file_with_metadata = SimpleMetadataFile(file=BytesIO(blob.content))
        file_with_metadata.content_type = blob.content_type
        file_with_metadata.custom_metadata = {"sha384": blob.checksum}
        if blob.mtime is not None:
            file_with_metadata.custom_metadata["mtime"] = blob.mtime.isoformat()
        destination_storage.save(name, file_with_metadata)
