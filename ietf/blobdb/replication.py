# Copyright The IETF Trust 2025, All Rights Reserved
from collections import namedtuple
from io import BytesIO
from typing import Optional

from django.conf import settings
from django.core.files import File
from django.core.files.storage import storages, InvalidStorageError
from django.db import connections

from ietf.utils import log

DEFAULT_SETTINGS = {
    "ENABLED": False,
    "DEST_STORAGE_PATTERN": "r2-{bucket}",
    "INCLUDE_BUCKETS": (),  # empty means include all
    "EXCLUDE_BUCKETS": (),  # empty means exclude none
    "VERBOSE_LOGGING": False,
}


class SimpleMetadataFile(File):
    def __init__(self, file, name=None):
        super().__init__(file, name)
        self.custom_metadata = {}
        self.content_type = ""


def get_replication_settings():
    return DEFAULT_SETTINGS | getattr(settings, "BLOBDB_REPLICATION", {})


def validate_replication_settings():
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
    include_buckets = replicator_settings["INCLUDE_BUCKETS"]
    if not isinstance(include_buckets, (list, tuple, set)):
        raise RuntimeError("INCLUDE_BUCKETS must be a list, tuple, or set")
    exclude_buckets = replicator_settings["EXCLUDE_BUCKETS"]
    if not isinstance(exclude_buckets, (list, tuple, set)):
        raise RuntimeError("EXCLUDE_BUCKETS must be a list, tuple, or set")


def destination_storage_for(bucket: str):
    pattern = get_replication_settings()["DEST_STORAGE_PATTERN"]
    storage_name = pattern.format(bucket=bucket)
    return storages[storage_name]


def replication_enabled(bucket: str):
    replication_settings = get_replication_settings()
    if not replication_settings["ENABLED"]:
        return False
    # Default is all buckets are included
    included = (
        len(replication_settings["INCLUDE_BUCKETS"]) == 0
        or bucket in replication_settings["INCLUDE_BUCKETS"]
    )
    # Default is no buckets are excluded
    excluded = (
        len(replication_settings["EXCLUDE_BUCKETS"]) > 0
        and bucket in replication_settings["EXCLUDE_BUCKETS"]
    )
    return included and not excluded


def verbose_logging_enabled():
    return bool(get_replication_settings()["VERBOSE_LOGGING"])


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


def replicate_blob(bucket, name):
    """Replicate a Blobdb blob to a Storage"""
    if not replication_enabled(bucket):
        if verbose_logging_enabled():
            log.log(f"Not replicating {bucket}:{name} because replication is not enabled for this {bucket}")
        return

    try:
        destination_storage = destination_storage_for(bucket)
    except InvalidStorageError as e:
        log.log(f"Failed to replicate {bucket}:{name} because destination storage for {bucket} is not configured")
        raise ReplicationError from e

    blob = fetch_blob_via_sql(bucket, name)
    if blob is None:
        if verbose_logging_enabled():
            log.log("Deleting {bucket}:{name} from replica")
        try:
            destination_storage.delete(name)
        except Exception as e:
            log.log("Failed to delete {bucket}:{name} from replica: {e}")
            raise ReplicationError from e
    else:
        # Add metadata expected by the MetadataS3Storage
        file_with_metadata = SimpleMetadataFile(file=BytesIO(blob.content))
        file_with_metadata.content_type = blob.content_type
        file_with_metadata.custom_metadata = {"sha384": blob.checksum}
        if blob.mtime is not None:
            file_with_metadata.custom_metadata["mtime"] = blob.mtime.isoformat()
        if verbose_logging_enabled():
            log.log(f"Saving {bucket}:{name} to replica (sha384: {blob.checksum[:16]}...)")
        try:
            destination_storage.save(name, file_with_metadata)
        except Exception as e:
            log.log("Failed to save {bucket}:{name} to replica: {e}")
            raise ReplicationError from e


class ReplicationError(Exception):
    pass
