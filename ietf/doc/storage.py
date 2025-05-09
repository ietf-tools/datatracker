# Copyright The IETF Trust 2025, All Rights Reserved
import debug  # pyflakes:ignore
import json

from contextlib import contextmanager
from functools import cached_property
from storages.backends.s3 import S3Storage
from typing import Union,  Any

from django.core.files.base import File
from django.core.files.storage import Storage, storages
from django.db import transaction

from ietf.doc.models import StoredObject
from ietf.doc.tasks import stagedblobstorage_commit_save_task, stagedblobstorage_commit_delete_task
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


class StagedBlobStorage(Storage):
    """Storage using an intermediate staging step
    
    Relies on `kind` being the same as its key in Django's STORAGES
    configuration.
    """

    def __init__(
        self,
        kind: str,
        async_commit: bool,
        staging_storage: Union[str, Storage, dict[str, Any]],
        final_storage: Union[str, Storage, dict[str, Any]],
    ):
        self.kind = kind
        self.async_commit = async_commit
        self._staging_storage = staging_storage
        self._final_storage = final_storage

    @cached_property
    def staging_storage(self) -> Storage:
        if isinstance(self._staging_storage, str):
            return storages[self._staging_storage]  # str = alias of another STORAGES entry
        elif isinstance(self._staging_storage, Storage):
            return self._staging_storage  # Storage = actual storage instance
        else:
            return storages.create_storage(params=self._staging_storage)  # dict = def of another Storage

    @cached_property
    def final_storage(self) -> Storage:
        if isinstance(self._final_storage, str):
            return storages[self._final_storage]  # str = alias of another STORAGES entry
        elif isinstance(self._final_storage, Storage):
            return self._final_storage  # Storage = actual storage instance
        else:
            return storages.create_storage(params=self._final_storage)  # dict = def of another Storage

    def _open(self, name, mode="rb"):
        try:
            return self.staging_storage.open(name, mode)
        except FileNotFoundError:
            pass
        return self.final_storage.open(name, mode)

    def _save(self, name, content):
        # Save to staging immediately
        new_name = self.staging_storage.save(name, content)
        if self.async_commit:
            # Queue a task to delete from final storage later
            transaction.on_commit(
                lambda: stagedblobstorage_commit_save_task.delay(
                    kind=self.kind,
                    name=name,
                )
            )
        else:
            self.commit_save(name)  # TODO-BLOBSTORE: deal with name change in this call
        return new_name

    def commit_save(self, name):
        # debug.say(f"StagedBlobStorage.commit_save('{name}') called")
        try:
            with self.staging_storage.open(name) as staged:
                new_name = self.final_storage.save(
                    name=name,
                    content=staged,
                )
        except FileNotFoundError:
            log(f"Failed to commit save of {self.kind}:{name} due to FileNotFoundError from staging storage")
        else:
            if new_name != name:
                log(f"Staged file {self.kind}:{name} was committed as {self.kind}:{new_name}")
            self.staging_storage.delete(name)

    def exists(self, name):        
        return False  # TODO-BLOBSTORE implement this

    def delete(self, name):
        # Immediately delete from staging, if possible
        try:
            self.staging_storage.delete(name)
        except NotImplementedError:
            log(f"Staging storage does not implement delete() for {self.kind}:{name}")
        # Queue a task to delete from final storage later
        if self.async_commit:
            transaction.on_commit(
                lambda: stagedblobstorage_commit_delete_task.delay(
                    kind=self.kind,
                    name=name,
                )
            )
        else:
            self.commit_delete(name)

    def commit_delete(self, name):
        # debug.say(f"StagedBlobStorage.commit_delete('{name}') called")
        try:
            self.final_storage.delete(name)
        except NotImplementedError:
            log(f"Final storage does not implement delete() for {self.kind}:{name}")


class StoredObjectStagedBlobStorage(StagedBlobStorage):
    commit_on_save = False  # files not committed until they're moved to the final_storage
    ietf_log_blob_timing = True
    warn_if_missing = True  # TODO-BLOBSTORE make this configurable (or remove it)

    def _save(self, name, content):
        now = timezone.now()
        record, created = StoredObject.objects.get_or_create(
            store=self.kind,
            name=name,
            defaults=dict(
                sha384=content.custom_metadata["sha384"],
                len=int(content.custom_metadata["len"]),
                store_created=now,
                created=now,
                modified=now,
                committed=None,  # we haven't saved yet
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
            record.committed = None
            record.save()
        new_name = super()._save(name, content)
        if self.commit_on_save:
            record.committed = timezone.now()
            record.save()
        return new_name

    def delete(self, name):
        existing_record = StoredObject.objects.filter(store=self.kind, name=name)
        if not existing_record.exists() and self.warn_if_missing:
            complaint = (
                f"WARNING: Asked to delete {name} from {self.kind} storage, "
                f"but there was no matching StoredObject"
            )
            log(complaint)
            debug.show("complaint")
        else:
            now = timezone.now()
            # Note that existing_record is a queryset that will have one matching object
            existing_record.filter(deleted__isnull=True).update(
                deleted=now,
                committed=now if self.commit_on_save else None,
            )
        super().delete(name)

    def commit_save(self, name):
        super().commit_save(name)
        StoredObject.objects.filter(
            store=self.kind,
            name=name,
            deleted__isnull=True,  # don't "commit" a deleted file on save
            committed__isnull=True,
        ).update(committed=timezone.now())

    def commit_delete(self, name):
        super().commit_delete(name)
        StoredObject.objects.filter(
            store=self.kind,
            name=name,
            deleted__isnull=False,  # only "commit" a deleted file on delete
            committed__isnull=True,
        ).update(committed=timezone.now())
