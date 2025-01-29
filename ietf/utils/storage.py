# Copyright The IETF Trust 2020-2025, All Rights Reserved
"""Django Storage classes"""
from pathlib import Path

from django.core.files.storage import FileSystemStorage
from ietf.doc.storage_utils import store_file
from .log import log


class NoLocationMigrationFileSystemStorage(FileSystemStorage):

    def deconstruct(obj):  # pylint: disable=no-self-argument
        path, args, kwargs = FileSystemStorage.deconstruct(obj)
        kwargs["location"] = None
        return path, args, kwargs


class BlobShadowFileSystemStorage(NoLocationMigrationFileSystemStorage):
    """FileSystemStorage that shadows writes to the blob store as well
    
    Strips directories from the filename when naming the blob.
    """

    def __init__(
        self,
        kind: str,
        location=None,
        base_url=None,
        file_permissions_mode=None,
        directory_permissions_mode=None,
    ):
        self.kind = kind
        super().__init__(
            location, base_url, file_permissions_mode, directory_permissions_mode
        )

    def save(self, name, content, max_length=None):
        # Write content to the filesystem - this deals with chunks, etc...
        saved_name = super().save(name, content, max_length)

        # Retrieve the content and write to the blob store
        blob_name = Path(saved_name).name  # strips path
        try:
            with self.open(saved_name, "rb") as f:
                store_file(self.kind, blob_name, f, allow_overwrite=True)
        except Exception as err:
            log(f"Failed to shadow {saved_name} at {self.kind}:{blob_name}: {err}")
        return saved_name  # includes the path!
