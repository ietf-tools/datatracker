# Copyright The IETF Trust 2020-2025, All Rights Reserved
"""Django Storage classes"""
import datetime
from hashlib import sha384
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import FileSystemStorage
from ietf.doc.storage_utils import store_file
from .log import log


class NoLocationMigrationFileSystemStorage(FileSystemStorage):

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        kwargs["location"] = None  # don't record location in migrations
        return path, args, kwargs


class BlobShadowFileSystemStorage(NoLocationMigrationFileSystemStorage):
    """FileSystemStorage that shadows writes to the blob store as well

    Strips directories from the filename when naming the blob.
    """

    def __init__(
        self,
        *,  # disallow positional arguments
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

        if settings.ENABLE_BLOBSTORAGE:
            try:
                # Retrieve the content and write to the blob store
                blob_name = Path(saved_name).name  # strips path
                with self.open(saved_name, "rb") as f:
                    store_file(self.kind, blob_name, f, allow_overwrite=True)
            except Exception as err:
                log(f"Blobstore Error: Failed to shadow {saved_name} at {self.kind}:{blob_name}: {repr(err)}")
                if settings.SERVER_MODE == "development":
                    raise
        return saved_name  # includes the path!

    def deconstruct(self):
        path, args, kwargs = super().deconstruct()
        kwargs["kind"] = ""  # don't record "kind" in migrations
        return path, args, kwargs


class MetadataFile(File):
    """File that includes metadata"""

    def __init__(self, file, name=None, mtime: Optional[datetime.datetime]=None, content_type=""):
        super().__init__(file=file, name=name)
        self.mtime = mtime
        self.content_type = content_type
        self._custom_metadata = None

    @property
    def custom_metadata(self):
        if self._custom_metadata is None:
            self._custom_metadata = self._compute_custom_metadata()
        return self._custom_metadata

    def _compute_custom_metadata(self):
        try:
            self.file.seek(0)
        except AttributeError:  # TODO-BLOBSTORE
            raise NotImplementedError("cannot handle unseekable content")
        content_bytes = self.file.read()
        if not isinstance(
            content_bytes, bytes
        ):  # TODO-BLOBSTORE: This is sketch-development only -remove before committing
            raise Exception(f"Expected bytes - got {type(content_bytes)}")
        self.file.seek(0)
        return {
            "len": f"{len(content_bytes)}",
            "sha384": f"{sha384(content_bytes).hexdigest()}",
            "mtime": None if self.mtime is None else self.mtime.isoformat(),
        }
