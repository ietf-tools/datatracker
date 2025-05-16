# Copyright The IETF Trust 2025, All Rights Reserved
from functools import partial
from typing import Optional

from django.db import transaction

import debug  # pyflakes:ignore
import json

from contextlib import contextmanager
from storages.backends.s3 import S3Storage

from django.core.files.base import File

from ietf.blobdb.storage import BlobdbStorage
from ietf.doc.models import StoredObject
from ietf.utils.log import log
from ietf.utils.storage import MetadataFile
from ietf.utils.timezone import timezone


class StoredObjectFile(MetadataFile):
    """Django storage File object that represents a StoredObject"""
    def __init__(self, file, name, mtime=None, content_type="", store=None, doc_name=None, doc_rev=None):
        super().__init__(
            file=file,
            name=name,
            mtime=mtime,
            content_type=content_type,
        )
        self.store = store
        self.doc_name = doc_name
        self.doc_rev = doc_rev

    @classmethod
    def from_storedobject(cls, file, name, store):
        """Alternate constructor for objects that already exist in the StoredObject table"""
        stored_object = StoredObject.objects.filter(store=store, name=name, deleted__isnull=True).first()
        if stored_object is None:
            raise FileNotFoundError(f"StoredObject for {store}:{name} does not exist or was deleted")
        file = cls(file, name, store, doc_name=stored_object.doc_name, doc_rev=stored_object.doc_rev)
        if int(file.custom_metadata["len"]) != stored_object.len:
            raise RuntimeError(f"File length changed unexpectedly for {store}:{name}")
        if file.custom_metadata["sha384"] != stored_object.sha384:
            raise RuntimeError(f"SHA-384 hash changed unexpectedly for {store}:{name}")
        return file


@contextmanager
def maybe_log_timing(enabled, op, **kwargs):
    """If enabled, log elapsed time and additional data from kwargs

    Emits log even if an exception occurs
    """
    before = timezone.now()
    exception = None
    try:
        yield
    except Exception as err:
        exception = err
        raise
    finally:
        if enabled:
            dt = timezone.now() - before
            log(
                json.dumps(
                    {
                        "log": "S3Storage_timing",
                        "seconds": dt.total_seconds(),
                        "op": op,
                        "exception": "" if exception is None else repr(exception),
                        **kwargs,
                    }
                )
            )


class MetadataS3Storage(S3Storage):
    def get_default_settings(self):
        # add a default for the ietf_log_blob_timing boolean
        return super().get_default_settings() | {"ietf_log_blob_timing": False}

    def _save(self, name, content: File):
        with maybe_log_timing(
            self.ietf_log_blob_timing, "_save", bucket_name=self.bucket_name, name=name
        ):
            if not isinstance(content, MetadataFile):
                raise NotImplementedError("Only handle MetadataFile so far")
            return super()._save(name, content)

    def _open(self, name, mode="rb"):
        with maybe_log_timing(
            self.ietf_log_blob_timing,
            "_open",
            bucket_name=self.bucket_name,
            name=name,
            mode=mode,
        ):
            return super()._open(name, mode)

    def delete(self, name):
        with maybe_log_timing(
            self.ietf_log_blob_timing, "delete", bucket_name=self.bucket_name, name=name
        ):
            super().delete(name)

    def _get_write_parameters(self, name, content=None):
        # debug.show('f"getting write parameters for {name}"')
        params = super()._get_write_parameters(name, content)
        # If we have a non-empty explicit content type, use it
        content_type = getattr(content, "content_type", "").strip()
        if content_type != "":
            params["ContentType"] = content_type
        if "Metadata" not in params:
            params["Metadata"] = {}
        if not isinstance(content, MetadataFile):
            raise NotImplementedError("Can only handle content of type MetadataFile")
        params["Metadata"].update(content.custom_metadata)
        return params


class StoredObjectBlobdbStorage(BlobdbStorage):
    ietf_log_blob_timing = True
    warn_if_missing = True  # TODO-BLOBSTORE make this configurable (or remove it)

    def _save_stored_object(self, name, content) -> StoredObject:
        now = timezone.now()
        record, created = StoredObject.objects.get_or_create(
            store=self.bucket_name,
            name=name,
            defaults=dict(
                sha384=content.custom_metadata["sha384"],
                len=int(content.custom_metadata["len"]),
                store_created=now,
                created=now,
                modified=now,
                doc_name=getattr(
                    content,
                    "doc_name",  # Note that these are assumed to be invariant
                    None,  # should be blank?
                ),
                doc_rev=getattr(
                    content,
                    "doc_rev",  # for a given name
                    None,  # should be blank?
                ),
            ),
        )
        if not created:
            record.sha384 = content.custom_metadata["sha384"]
            record.len = int(content.custom_metadata["len"])
            record.modified = now
            record.deleted = None
            record.save()
        return record

    def _delete_stored_object(self, name) -> Optional[StoredObject]:
        existing_record = StoredObject.objects.filter(store=self.bucket_name, name=name)
        if not existing_record.exists() and self.warn_if_missing:
            complaint = (
                f"WARNING: Asked to delete {name} from {self.bucket_name} storage, "
                f"but there was no matching StoredObject"
            )
            log(complaint)
            debug.show("complaint")
        else:
            now = timezone.now()
            # Note that existing_record is a queryset that will have one matching object
            existing_record.filter(deleted__isnull=True).update(deleted=now)
        return existing_record.first()

    def _save(self, name, content):
        """Perform the save operation 
        
        In principle the name could change on save to the blob store. As of now, BlobdbStorage
        will not change it, but allow for that possibility. Callers should be prepared for this.
        """
        saved_name = super()._save(name, content)
        self._save_stored_object(saved_name, content)
        return saved_name

    def delete(self, name):
        self._delete_stored_object(name)
        super().delete(name)
